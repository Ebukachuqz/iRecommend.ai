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


def normalize_review(review: dict[str, Any], category: str) -> dict[str, Any]:
    parent_asin = review.get("parent_asin") or review.get("asin")
    normalized = AmazonReview(
        review_id=stable_review_id(review),
        user_id=str(review["user_id"]),
        parent_asin=str(parent_asin),
        category=category,
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


def ingest_category(
    category: str | None = None,
    min_user_reviews: int = 10,
    batch_size: int = 500,
    max_reviews: int | None = None,
    client: Client | None = None,
) -> dict[str, int]:
    """Stream Amazon Reviews data into Supabase for users with enough history."""

    settings = get_settings()
    category = category or settings.default_category
    client = client or get_supabase_client()

    counts = count_users(stream_reviews(category), max_reviews=max_reviews)
    eligible_users = {user_id for user_id, count in counts.items() if count >= min_user_reviews}

    parent_asins: set[str] = set()
    normalized_reviews: Iterator[dict[str, Any]] = (
        normalize_review(review, category)
        for review in stream_reviews(category)
        if review.get("user_id") in eligible_users and (review.get("parent_asin") or review.get("asin"))
    )

    uploaded_reviews = 0
    for batch in batched(normalized_reviews, batch_size):
        parent_asins.update(item["parent_asin"] for item in batch)
        upsert_reviews(client, batch)
        uploaded_reviews += len(batch)

    normalized_metadata: Iterator[dict[str, Any]] = (
        normalize_metadata(item, category)
        for item in stream_metadata(category)
        if item.get("parent_asin") in parent_asins
    )

    uploaded_metadata = 0
    for batch in batched(normalized_metadata, batch_size):
        upsert_metadata(client, batch)
        uploaded_metadata += len(batch)

    return {
        "eligible_users": len(eligible_users),
        "uploaded_reviews": uploaded_reviews,
        "uploaded_metadata": uploaded_metadata,
    }
