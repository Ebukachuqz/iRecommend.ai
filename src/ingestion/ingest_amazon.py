from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable, Iterator
from typing import Any

from datasets import load_dataset
from supabase import Client

from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from src.ingestion.data_models import AmazonProductMetadata, AmazonReview, parse_amazon_timestamp


DATASET_NAME = "McAuley-Lab/Amazon-Reviews-2023"


def review_config_name(category: str) -> str:
    return f"raw_review_{category}"


def metadata_config_name(category: str) -> str:
    return f"raw_meta_{category}"


def stable_review_id(review: dict[str, Any]) -> str:
    parts = [
        str(review.get("user_id", "")),
        str(review.get("parent_asin") or review.get("asin") or ""),
        str(review.get("timestamp", "")),
        str(review.get("rating", "")),
        str(review.get("title", "")),
        str(review.get("text", ""))[:200],
    ]
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()


def batched(items: Iterable[dict[str, Any]], batch_size: int) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def stream_reviews(category: str) -> Iterable[dict[str, Any]]:
    return load_dataset(
        DATASET_NAME,
        review_config_name(category),
        split="full",
        streaming=True,
        trust_remote_code=True,
    )


def stream_metadata(category: str) -> Iterable[dict[str, Any]]:
    return load_dataset(
        DATASET_NAME,
        metadata_config_name(category),
        split="full",
        streaming=True,
        trust_remote_code=True,
    )


def count_users(reviews: Iterable[dict[str, Any]], max_reviews: int | None = None) -> Counter[str]:
    counts: Counter[str] = Counter()
    for index, review in enumerate(reviews, start=1):
        user_id = review.get("user_id")
        if user_id:
            counts[str(user_id)] += 1
        if max_reviews and index >= max_reviews:
            break
    return counts


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def review_parent_asin(review: dict[str, Any]) -> str | None:
    parent_asin = review.get("parent_asin") or review.get("asin")
    return str(parent_asin).strip() if has_value(parent_asin) else None


def is_valid_review(review: dict[str, Any]) -> bool:
    parent_asin = review_parent_asin(review)
    return all(
        [
            has_value(review.get("user_id")),
            has_value(parent_asin),
            has_value(review.get("rating")),
            has_value(review.get("title")),
            has_value(review.get("text")),
            parse_amazon_timestamp(review.get("timestamp")) is not None,
        ]
    )


def is_valid_metadata(item: dict[str, Any], category: str) -> bool:
    return all(
        [
            has_value(item.get("parent_asin")),
            has_value(item.get("title")),
            has_value(category) or has_value(item.get("main_category")) or has_value(item.get("category")),
            has_value(item.get("features")),
            has_value(item.get("description")),
            parse_price(item.get("price")) is not None,
            has_value(item.get("average_rating")),
            has_value(item.get("rating_number")),
            has_value(item.get("store")),
            has_value(item.get("details")),
        ]
    )


def normalize_review(review: dict[str, Any]) -> dict[str, Any]:
    parent_asin = review.get("parent_asin") or review.get("asin")
    normalized = AmazonReview(
        review_id=stable_review_id(review),
        user_id=str(review["user_id"]),
        parent_asin=str(parent_asin),
        rating=review.get("rating"),
        title=review.get("title"),
        text=review.get("text"),
        timestamp=parse_amazon_timestamp(review.get("timestamp")),
        verified_purchase=review.get("verified_purchase"),
        helpful_vote=review.get("helpful_vote"),
        raw_review=review,
    )
    return normalized.model_dump(mode="json")


def normalize_metadata(item: dict[str, Any], category: str) -> dict[str, Any]:
    normalized = AmazonProductMetadata(
        parent_asin=str(item["parent_asin"]),
        category=category,
        title=item.get("title"),
        main_category=item.get("main_category"),
        categories=item.get("categories") or [],
        features=item.get("features") or [],
        description=item.get("description") or [],
        price=parse_price(item.get("price")),
        average_rating=item.get("average_rating"),
        rating_number=item.get("rating_number"),
        store=item.get("store"),
        details=item.get("details") or {},
        raw_metadata=item,
    )
    return normalized.model_dump(mode="json")


def parse_price(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def upsert_reviews(client: Client, reviews: list[dict[str, Any]]) -> None:
    if reviews:
        client.table("amazon_reviews").upsert(reviews, on_conflict="review_id").execute()


def upsert_metadata(client: Client, metadata: list[dict[str, Any]]) -> None:
    if metadata:
        client.table("amazon_product_metadata").upsert(metadata, on_conflict="parent_asin").execute()


def limited(items: Iterable[dict[str, Any]], limit: int | None) -> Iterator[dict[str, Any]]:
    for index, item in enumerate(items, start=1):
        if limit is not None and index > limit:
            break
        yield item


def select_eligible_users(valid_pairs: list[dict[str, Any]], min_reviews: int, max_users: int) -> list[str]:
    counts: Counter[str] = Counter(str(review["user_id"]) for review in valid_pairs)
    eligible = [(user_id, count) for user_id, count in counts.items() if count >= min_reviews]
    ordered = sorted(eligible, key=lambda item: (-item[1], item[0]))
    selected = ordered if max_users == 0 else ordered[:max_users]
    return [user_id for user_id, _count in selected]


def build_ingestion_plan(
    reviews: Iterable[dict[str, Any]],
    metadata: Iterable[dict[str, Any]],
    category: str,
    min_reviews: int = 15,
    max_users: int = 100,
    extra_products: int = 1000,
    review_limit: int | None = None,
) -> dict[str, Any]:
    raw_reviews = list(limited(reviews, review_limit))

    valid_reviews: list[dict[str, Any]] = []
    skipped_invalid_reviews = 0
    for review in raw_reviews:
        if is_valid_review(review):
            valid_reviews.append(review)
        else:
            skipped_invalid_reviews += 1

    candidate_parent_asins = {parent_asin for review in valid_reviews if (parent_asin := review_parent_asin(review))}
    reviewed_metadata_by_asin: dict[str, dict[str, Any]] = {}
    extra_metadata_by_asin: dict[str, dict[str, Any]] = {}
    seen_metadata_asins: set[str] = set()
    skipped_sparse_metadata = 0
    valid_metadata_rows = 0

    for item in metadata:
        if not has_value(item.get("parent_asin")):
            skipped_sparse_metadata += 1
            continue
        parent_asin = str(item["parent_asin"]).strip()
        if parent_asin in seen_metadata_asins:
            continue
        seen_metadata_asins.add(parent_asin)

        if not is_valid_metadata(item, category):
            skipped_sparse_metadata += 1
            continue

        valid_metadata_rows += 1
        if parent_asin in candidate_parent_asins:
            reviewed_metadata_by_asin[parent_asin] = item
        elif extra_products > 0 and len(extra_metadata_by_asin) < extra_products:
            extra_metadata_by_asin[parent_asin] = item

    valid_pairs = [
        review
        for review in valid_reviews
        if (parent_asin := review_parent_asin(review)) and parent_asin in reviewed_metadata_by_asin
    ]

    selected_user_ids = set(select_eligible_users(valid_pairs, min_reviews=min_reviews, max_users=max_users))
    selected_reviews = [review for review in valid_pairs if str(review["user_id"]) in selected_user_ids]

    selected_parent_asins = {review_parent_asin(review) for review in selected_reviews}
    selected_parent_asins.discard(None)
    metadata_to_upload = [
        reviewed_metadata_by_asin[parent_asin]
        for parent_asin in sorted(selected_parent_asins)
        if parent_asin in reviewed_metadata_by_asin
    ]

    uploaded_parent_asins = {item["parent_asin"] for item in metadata_to_upload}
    extra_metadata = [
        item
        for parent_asin, item in extra_metadata_by_asin.items()
        if parent_asin not in uploaded_parent_asins
    ]

    return {
        "category": category,
        "min_reviews": min_reviews,
        "max_users": max_users,
        "extra_products_requested": extra_products,
        "selected_user_ids": sorted(selected_user_ids),
        "reviews_to_upload": selected_reviews,
        "metadata_to_upload": metadata_to_upload + extra_metadata,
        "extra_metadata": extra_metadata,
        "valid_metadata_rows": valid_metadata_rows,
        "valid_review_rows": len(valid_reviews),
        "valid_review_product_pairs": len(valid_pairs),
        "skipped_invalid_reviews": skipped_invalid_reviews,
        "skipped_sparse_metadata": skipped_sparse_metadata,
    }


def fetch_rows_by_values(
    client: Client,
    table_name: str,
    columns: str,
    column_name: str,
    values: Iterable[str],
    batch_size: int = 500,
) -> list[dict[str, Any]]:
    unique_values = list(dict.fromkeys(value for value in values if value))
    rows: list[dict[str, Any]] = []
    for start in range(0, len(unique_values), batch_size):
        batch_values = unique_values[start : start + batch_size]
        if not batch_values:
            continue
        response = client.table(table_name).select(columns).in_(column_name, batch_values).execute()
        rows.extend(response.data or [])
    return rows


def verify_uploaded_counts(
    client: Client,
    review_ids: Iterable[str],
    parent_asins: Iterable[str],
    min_reviews: int,
    batch_size: int = 500,
) -> dict[str, int]:
    uploaded_reviews = fetch_rows_by_values(
        client,
        "amazon_reviews",
        "review_id,user_id,parent_asin",
        "review_id",
        review_ids,
        batch_size=batch_size,
    )
    uploaded_metadata = fetch_rows_by_values(
        client,
        "amazon_product_metadata",
        "parent_asin",
        "parent_asin",
        parent_asins,
        batch_size=batch_size,
    )
    metadata_asins = {row["parent_asin"] for row in uploaded_metadata}
    matching_reviews = [row for row in uploaded_reviews if row.get("parent_asin") in metadata_asins]
    missing_reviews = [row for row in uploaded_reviews if row.get("parent_asin") not in metadata_asins]
    user_counts = Counter(str(row["user_id"]) for row in matching_reviews if row.get("user_id"))
    return {
        "db_users_with_min_reviews": sum(1 for count in user_counts.values() if count >= min_reviews),
        "db_reviews_with_matching_metadata": len(matching_reviews),
        "db_reviews_missing_metadata": len(missing_reviews),
    }


def ingest_category(
    category: str | None = None,
    min_user_reviews: int | None = None,
    batch_size: int = 500,
    max_reviews: int | None = None,
    min_reviews: int | None = None,
    max_users: int = 100,
    extra_products: int = 1000,
    review_limit: int | None = None,
    dry_run: bool = False,
    verify: bool = False,
    client: Client | None = None,
) -> dict[str, Any]:
    """Ingest an evaluation-ready cohort with strict review-product validation."""

    settings = get_settings()
    category = category or settings.default_category
    effective_min_reviews = min_reviews if min_reviews is not None else min_user_reviews
    effective_min_reviews = 15 if effective_min_reviews is None else effective_min_reviews
    effective_review_limit = review_limit if review_limit is not None else max_reviews

    plan = build_ingestion_plan(
        stream_reviews(category),
        stream_metadata(category),
        category=category,
        min_reviews=effective_min_reviews,
        max_users=max_users,
        extra_products=extra_products,
        review_limit=effective_review_limit,
    )

    normalized_reviews = [normalize_review(review) for review in plan["reviews_to_upload"]]
    normalized_metadata = [normalize_metadata(item, category) for item in plan["metadata_to_upload"]]

    uploaded_reviews = 0
    uploaded_metadata = 0
    if not dry_run:
        client = client or get_supabase_client()
        for batch in batched(normalized_reviews, batch_size):
            upsert_reviews(client, batch)
            uploaded_reviews += len(batch)

        for batch in batched(normalized_metadata, batch_size):
            upsert_metadata(client, batch)
            uploaded_metadata += len(batch)
    else:
        uploaded_reviews = 0
        uploaded_metadata = 0

    result: dict[str, Any] = {
        "category": category,
        "min_reviews": effective_min_reviews,
        "max_users": max_users,
        "extra_products_requested": extra_products,
        "valid_metadata_rows": plan["valid_metadata_rows"],
        "valid_review_rows": plan["valid_review_rows"],
        "valid_review_product_pairs": plan["valid_review_product_pairs"],
        "selected_eligible_users": len(plan["selected_user_ids"]),
        "uploaded_reviews": uploaded_reviews,
        "uploaded_metadata": uploaded_metadata,
        "extra_products_added": len(plan["extra_metadata"]),
        "skipped_invalid_reviews": plan["skipped_invalid_reviews"],
        "skipped_sparse_metadata": plan["skipped_sparse_metadata"],
        "dry_run": dry_run,
    }

    if verify and not dry_run:
        client = client or get_supabase_client()
        result.update(
            verify_uploaded_counts(
                client,
                [review["review_id"] for review in normalized_reviews],
                [metadata["parent_asin"] for metadata in normalized_metadata],
                min_reviews=effective_min_reviews,
                batch_size=batch_size,
            )
        )
    elif verify:
        result.update(
            {
                "db_users_with_min_reviews": 0,
                "db_reviews_with_matching_metadata": 0,
                "db_reviews_missing_metadata": 0,
            }
        )

    return result
