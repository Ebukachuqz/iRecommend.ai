from __future__ import annotations

from typing import Any

from app.saas.services.csv_processor import MerchantCsvProcessor, map_product_row, map_review_row
from app.saas.services.persona_generator import build_fallback_persona, compute_review_stats


def test_map_review_row_preserves_unmapped_columns_as_extra_fields() -> None:
    row = {
        "cust_id": "C-1",
        "stars": "4",
        "comment": "Very sturdy.",
        "product": "Desk lamp",
        "segment": "office",
    }
    mapping = {
        "cust_id": "customer_id",
        "stars": "rating",
        "comment": "review_text",
        "product": "product_name",
    }

    payload, error = map_review_row(row, mapping, "org-1")

    assert error is None
    assert payload is not None
    assert payload["customer_id"] == "C-1"
    assert payload["rating"] == 4.0
    assert payload["extra_fields"] == {"segment": "office"}


def test_map_product_row_preserves_optional_fields_and_extra_fields() -> None:
    row = {
        "sku": "SKU-1",
        "name": "Air purifier",
        "dept": "Home",
        "cost": "$79.99",
        "bullets": "HEPA filter, Quiet mode",
        "warehouse": "Lagos",
    }
    mapping = {
        "sku": "product_id",
        "name": "product_name",
        "dept": "category",
        "cost": "price",
        "bullets": "features",
    }

    payload, error = map_product_row(row, mapping, "org-1")

    assert error is None
    assert payload is not None
    assert payload["product_name"] == "Air purifier"
    assert payload["category"] == "Home"
    assert payload["price"] == 79.99
    assert payload["features"] == ["HEPA filter", "Quiet mode"]
    assert payload["extra_fields"] == {"warehouse": "Lagos"}


def test_compute_review_stats_and_fallback_persona_are_valid() -> None:
    reviews = [
        {"rating": 5, "review_text": "Excellent battery life", "product_name": "Phone", "category": "Electronics"},
        {"rating": 4, "review_text": "Good value", "product_name": "Cable", "category": "Electronics"},
        {"rating": 2, "review_text": "Broke quickly", "product_name": "Charger", "category": "Accessories"},
    ]

    stats = compute_review_stats(reviews)
    persona = build_fallback_persona("C-1", reviews)

    assert stats["review_count"] == 3
    assert stats["rating_distribution"] == {"1": 0, "2": 1, "3": 0, "4": 1, "5": 1}
    assert persona["extra_persona_signals"]["generation_mode"] == "fallback"
    assert persona["rating_behavior"]["average_rating"] == stats["average_rating"]


class FakeResponse:
    def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
        self.data = data or []
        self.count = len(self.data)


class FakeTable:
    def __init__(self, client: "FakeClient", name: str) -> None:
        self.client = client
        self.name = name
        self.filters: dict[str, Any] = {}
        self.pending_insert: list[dict[str, Any]] = []
        self.pending_update: dict[str, Any] = {}

    def insert(self, rows: list[dict[str, Any]] | dict[str, Any]) -> "FakeTable":
        self.pending_insert = rows if isinstance(rows, list) else [rows]
        return self

    def update(self, payload: dict[str, Any]) -> "FakeTable":
        self.pending_update = payload
        return self

    def select(self, *_args: Any, **_kwargs: Any) -> "FakeTable":
        return self

    def eq(self, key: str, value: Any) -> "FakeTable":
        self.filters[key] = value
        return self

    def execute(self) -> FakeResponse:
        if self.pending_insert:
            self.client.rows.setdefault(self.name, []).extend(self.pending_insert)
            return FakeResponse(self.pending_insert)
        if self.pending_update:
            self.client.updates.append((self.name, dict(self.pending_update), dict(self.filters)))
            return FakeResponse([])
        rows = self.client.rows.get(self.name, [])
        for key, value in self.filters.items():
            rows = [row for row in rows if row.get(key) == value]
        return FakeResponse(rows)


class FakeClient:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {
            "merchant_reviews": [
                {"organisation_id": "org-1", "customer_id": "C-1", "rating": 5, "review_text": "Existing good"},
                {"organisation_id": "org-1", "customer_id": "C-1", "rating": 4, "review_text": "Existing useful"},
            ],
            "merchant_products": [],
        }
        self.updates: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def table(self, name: str) -> FakeTable:
        return FakeTable(self, name)


class FakePersonaGenerator:
    def __init__(self) -> None:
        self.review_counts: list[int] = []
        self.upserted: list[tuple[str, str, int]] = []

    def generate_with_fallback(self, customer_id: str, reviews: list[dict[str, Any]], org_id: str) -> tuple[dict[str, Any], str, None]:
        self.review_counts.append(len(reviews))
        return {"extra_persona_signals": {"generation_mode": "fallback"}}, "fallback", None

    def upsert_persona(self, org_id: str, customer_id: str, persona: dict[str, Any], review_count: int) -> None:
        self.upserted.append((org_id, customer_id, review_count))


def test_processor_generates_persona_from_all_stored_reviews_for_affected_customer() -> None:
    fake_client = FakeClient()
    fake_generator = FakePersonaGenerator()
    processor = MerchantCsvProcessor(client=fake_client, persona_generator=fake_generator)  # type: ignore[arg-type]
    csv_content = b"customer_id,rating,review_text\nC-1,3,New upload row\n"

    processor.process_reviews_csv(
        file_content=csv_content,
        column_mapping={"customer_id": "customer_id", "rating": "rating", "review_text": "review_text"},
        org_id="org-1",
        upload_id="upload-1",
    )

    assert fake_generator.review_counts == [3]
    assert fake_generator.upserted == [("org-1", "C-1", 3)]
    complete_updates = [payload for table, payload, _ in fake_client.updates if table == "csv_uploads" and payload.get("status") == "complete"]
    assert complete_updates
    assert complete_updates[-1]["processing_summary"]["customers_detected"] == 1


def test_processor_uploads_products_without_generating_personas() -> None:
    fake_client = FakeClient()
    fake_generator = FakePersonaGenerator()
    processor = MerchantCsvProcessor(client=fake_client, persona_generator=fake_generator)  # type: ignore[arg-type]
    csv_content = b"sku,name,category,price,features\nP-1,Desk lamp,Office,25.50,\"metal,LED\"\n"

    processor.process_products_csv(
        file_content=csv_content,
        column_mapping={
            "sku": "product_id",
            "name": "product_name",
            "category": "category",
            "price": "price",
            "features": "features",
        },
        org_id="org-1",
        upload_id="upload-products-1",
    )

    assert fake_generator.upserted == []
    assert fake_client.rows["merchant_products"][0]["product_name"] == "Desk lamp"
    assert fake_client.rows["merchant_products"][0]["features"] == ["metal", "LED"]
    complete_updates = [payload for table, payload, _ in fake_client.updates if table == "csv_uploads" and payload.get("status") == "complete"]
    assert complete_updates
    assert complete_updates[-1]["processed_rows"] == 1
    assert complete_updates[-1]["processing_summary"]["valid_rows"] == 1
