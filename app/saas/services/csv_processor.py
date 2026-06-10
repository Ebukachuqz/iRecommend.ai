from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from supabase import Client

from app.saas.db import get_saas_client
from app.saas.services.persona_generator import MerchantPersonaGenerator


REQUIRED_REVIEW_FIELDS = {"customer_id", "rating", "review_text"}
OPTIONAL_REVIEW_FIELDS = {"product_name", "category", "date"}
REVIEW_FIELDS = REQUIRED_REVIEW_FIELDS | OPTIONAL_REVIEW_FIELDS

REQUIRED_PRODUCT_FIELDS = {"product_name", "category"}
OPTIONAL_PRODUCT_FIELDS = {"product_id", "price", "description", "features"}
PRODUCT_FIELDS = REQUIRED_PRODUCT_FIELDS | OPTIONAL_PRODUCT_FIELDS


@dataclass
class ProcessingSummary:
    customers_detected: int = 0
    valid_rows: int = 0
    skipped_invalid_rows: int = 0
    skipped_insufficient_reviews: int = 0
    failed_personas: int = 0
    error_samples: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        if len(self.error_samples) < 8:
            self.error_samples.append(message[:300])

    def to_dict(self) -> dict[str, Any]:
        return {
            "customers_detected": self.customers_detected,
            "valid_rows": self.valid_rows,
            "skipped_invalid_rows": self.skipped_invalid_rows,
            "skipped_insufficient_reviews": self.skipped_insufficient_reviews,
            "failed_personas": self.failed_personas,
            "error_samples": self.error_samples,
        }


def count_csv_rows(file_content: bytes) -> int:
    text = file_content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return sum(1 for _ in reader)


def normalize_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    normalized = {}
    for merchant_column, field_name in mapping.items():
        field = str(field_name or "").strip()
        column = str(merchant_column or "").strip()
        if not column or not field or field == "skip":
            continue
        normalized[column] = field
    return normalized


def validate_review_mapping(mapping: dict[str, str]) -> None:
    mapped_fields = set(mapping.values())
    missing = REQUIRED_REVIEW_FIELDS - mapped_fields
    if missing:
        raise ValueError(f"Missing required review mappings: {', '.join(sorted(missing))}.")


def validate_product_mapping(mapping: dict[str, str]) -> None:
    mapped_fields = set(mapping.values())
    missing = REQUIRED_PRODUCT_FIELDS - mapped_fields
    if missing:
        raise ValueError(f"Missing required product mappings: {', '.join(sorted(missing))}.")


def parse_rating(value: Any) -> float | None:
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    if rating < 1 or rating > 5:
        return None
    return rating


def parse_price(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        price = float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return price if price >= 0 else None


def parse_features(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    separators = ["\n", ";", "|"]
    for separator in separators:
        if separator in text:
            return [item.strip() for item in text.split(separator) if item.strip()]
    return [item.strip() for item in text.split(",") if item.strip()]


def map_review_row(row: dict[str, Any], mapping: dict[str, str], org_id: str) -> tuple[dict[str, Any] | None, str | None]:
    mapped: dict[str, Any] = {}
    mapped_columns = set()
    for merchant_column, field_name in mapping.items():
        if field_name not in REVIEW_FIELDS:
            continue
        mapped_columns.add(merchant_column)
        mapped[field_name] = row.get(merchant_column)

    customer_id = str(mapped.get("customer_id") or "").strip()
    review_text = str(mapped.get("review_text") or "").strip()
    rating = parse_rating(mapped.get("rating"))
    if not customer_id:
        return None, "Missing customer_id."
    if rating is None:
        return None, f"Invalid rating for customer {customer_id}."
    if not review_text:
        return None, f"Missing review_text for customer {customer_id}."

    extra_fields = {
        key: value
        for key, value in row.items()
        if key not in mapped_columns and value not in (None, "")
    }
    return (
        {
            "organisation_id": org_id,
            "customer_id": customer_id,
            "rating": rating,
            "review_text": review_text,
            "product_name": str(mapped.get("product_name") or "").strip() or None,
            "category": str(mapped.get("category") or "").strip() or None,
            "review_date": str(mapped.get("date") or "").strip() or None,
            "extra_fields": extra_fields,
        },
        None,
    )


def map_product_row(row: dict[str, Any], mapping: dict[str, str], org_id: str) -> tuple[dict[str, Any] | None, str | None]:
    mapped: dict[str, Any] = {}
    mapped_columns = set()
    for merchant_column, field_name in mapping.items():
        if field_name not in PRODUCT_FIELDS:
            continue
        mapped_columns.add(merchant_column)
        mapped[field_name] = row.get(merchant_column)

    product_name = str(mapped.get("product_name") or "").strip()
    category = str(mapped.get("category") or "").strip()
    if not product_name:
        return None, "Missing product_name."
    if not category:
        return None, f"Missing category for product {product_name}."

    extra_fields = {
        key: value
        for key, value in row.items()
        if key not in mapped_columns and value not in (None, "")
    }
    return (
        {
            "organisation_id": org_id,
            "product_id": str(mapped.get("product_id") or "").strip() or None,
            "product_name": product_name,
            "category": category,
            "price": parse_price(mapped.get("price")),
            "description": str(mapped.get("description") or "").strip() or None,
            "features": parse_features(mapped.get("features")),
            "extra_fields": extra_fields,
        },
        None,
    )


class MerchantCsvProcessor:
    def __init__(self, client: Client | None = None, persona_generator: MerchantPersonaGenerator | None = None) -> None:
        self.client = client or get_saas_client()
        self.persona_generator = persona_generator or MerchantPersonaGenerator(self.client)

    def update_upload(
        self,
        upload_id: str,
        *,
        status: str | None = None,
        processed_rows: int | None = None,
        personas_generated: int | None = None,
        processing_summary: ProcessingSummary | None = None,
        error_message: str | None = None,
        completed: bool = False,
    ) -> None:
        payload: dict[str, Any] = {}
        if status is not None:
            payload["status"] = status
        if processed_rows is not None:
            payload["processed_rows"] = processed_rows
        if personas_generated is not None:
            payload["personas_generated"] = personas_generated
        if processing_summary is not None:
            payload["processing_summary"] = processing_summary.to_dict()
        if error_message is not None:
            payload["error_message"] = error_message
        if completed:
            payload["completed_at"] = datetime.now(timezone.utc).isoformat()
        if payload:
            self.client.table("csv_uploads").update(payload).eq("id", upload_id).execute()

    def fetch_customer_reviews(self, org_id: str, customer_id: str) -> list[dict[str, Any]]:
        response = (
            self.client.table("merchant_reviews")
            .select("*")
            .eq("organisation_id", org_id)
            .eq("customer_id", customer_id)
            .execute()
        )
        return list(response.data or [])

    def insert_product_batch(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        try:
            self.client.table("merchant_products").insert(batch).execute()
        except Exception:
            stripped = [{key: value for key, value in row.items() if key != "extra_fields"} for row in batch]
            self.client.table("merchant_products").insert(stripped).execute()

    def process_reviews_csv(
        self,
        *,
        file_content: bytes,
        column_mapping: dict[str, Any],
        org_id: str,
        upload_id: str,
    ) -> None:
        summary = ProcessingSummary()
        processed_rows = 0
        personas_generated = 0
        affected_customers: set[str] = set()

        try:
            mapping = normalize_mapping(column_mapping)
            validate_review_mapping(mapping)
            self.update_upload(upload_id, status="processing", processing_summary=summary)

            text = file_content.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            batch: list[dict[str, Any]] = []
            for row in reader:
                processed_rows += 1
                payload, error = map_review_row(row, mapping, org_id)
                if error or payload is None:
                    summary.skipped_invalid_rows += 1
                    summary.add_error(f"Row {processed_rows}: {error or 'Invalid row.'}")
                else:
                    batch.append(payload)
                    summary.valid_rows += 1
                    affected_customers.add(payload["customer_id"])
                    summary.customers_detected = len(affected_customers)

                if len(batch) >= 100:
                    self.client.table("merchant_reviews").insert(batch).execute()
                    batch = []
                if processed_rows % 10 == 0:
                    self.update_upload(
                        upload_id,
                        processed_rows=processed_rows,
                        processing_summary=summary,
                    )

            if batch:
                self.client.table("merchant_reviews").insert(batch).execute()

            summary.customers_detected = len(affected_customers)
            self.update_upload(upload_id, processed_rows=processed_rows, processing_summary=summary)

            for customer_id in sorted(affected_customers):
                reviews = self.fetch_customer_reviews(org_id, customer_id)
                if len(reviews) < 3:
                    summary.skipped_insufficient_reviews += 1
                    self.update_upload(upload_id, processing_summary=summary)
                    continue

                persona, mode, error = self.persona_generator.generate_with_fallback(customer_id, reviews, org_id)
                if mode == "fallback":
                    summary.failed_personas += 1
                    summary.add_error(f"Persona fallback for customer {customer_id}: {error or 'LLM generation failed.'}")
                self.persona_generator.upsert_persona(org_id, customer_id, persona, len(reviews))
                personas_generated += 1
                self.update_upload(
                    upload_id,
                    personas_generated=personas_generated,
                    processing_summary=summary,
                )
                time.sleep(0.4)

            self.update_upload(
                upload_id,
                status="complete",
                processed_rows=processed_rows,
                personas_generated=personas_generated,
                processing_summary=summary,
                completed=True,
            )
        except Exception as exc:
            summary.add_error(str(exc))
            self.update_upload(
                upload_id,
                status="failed",
                processed_rows=processed_rows,
                personas_generated=personas_generated,
                processing_summary=summary,
                error_message=str(exc),
            )

    def process_products_csv(
        self,
        *,
        file_content: bytes,
        column_mapping: dict[str, Any],
        org_id: str,
        upload_id: str,
    ) -> None:
        summary = ProcessingSummary()
        processed_rows = 0

        try:
            mapping = normalize_mapping(column_mapping)
            validate_product_mapping(mapping)
            self.update_upload(upload_id, status="processing", processing_summary=summary)

            text = file_content.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            batch: list[dict[str, Any]] = []
            for row in reader:
                processed_rows += 1
                payload, error = map_product_row(row, mapping, org_id)
                if error or payload is None:
                    summary.skipped_invalid_rows += 1
                    summary.add_error(f"Row {processed_rows}: {error or 'Invalid product row.'}")
                else:
                    batch.append(payload)
                    summary.valid_rows += 1

                if len(batch) >= 100:
                    self.insert_product_batch(batch)
                    batch = []
                if processed_rows % 10 == 0:
                    self.update_upload(
                        upload_id,
                        processed_rows=processed_rows,
                        processing_summary=summary,
                    )

            if batch:
                self.insert_product_batch(batch)

            self.update_upload(
                upload_id,
                status="complete",
                processed_rows=processed_rows,
                processing_summary=summary,
                completed=True,
            )
        except Exception as exc:
            summary.add_error(str(exc))
            self.update_upload(
                upload_id,
                status="failed",
                processed_rows=processed_rows,
                processing_summary=summary,
                error_message=str(exc),
            )
