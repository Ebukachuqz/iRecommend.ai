from __future__ import annotations

import gzip
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from itertools import islice
from typing import Any

from datasets import load_dataset
from supabase import Client

from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from src.ingestion.data_models import AmazonProductMetadata, AmazonReview, parse_amazon_timestamp


DATASET_NAME = "McAuley-Lab/Amazon-Reviews-2023"

METADATA_KEEP_COLUMNS = [
    "parent_asin",
    "title",
    "main_category",
    "categories",
    "features",
    "description",
    "images",
    "bought_together",
    "price",
    "average_rating",
    "rating_number",
    "store",
    "details",
]

PROBLEMATIC_METADATA_COLUMNS = [
    "videos",
    "video",
    "variants",
]


class IngestionUploadError(RuntimeError):
    """Raised when a database upsert fails with a reviewer-readable message."""


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


def dedupe_rows_by_key(rows: Iterable[dict[str, Any]], key: str) -> tuple[list[dict[str, Any]], int]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    skipped = 0
    for row in rows:
        value = row.get(key)
        if value in (None, ""):
            unique.append(row)
            continue
        value_key = str(value)
        if value_key in seen:
            skipped += 1
            continue
        seen.add(value_key)
        unique.append(row)
    return unique, skipped


def stream_reviews(category: str) -> Iterable[dict[str, Any]]:
    return load_dataset(
        DATASET_NAME,
        review_config_name(category),
        split="full",
        streaming=True,
        trust_remote_code=True,
    )


def prune_metadata_columns(dataset: Any) -> Any:
    """Keep only metadata fields needed by ingestion before iterating."""

    column_names = list(getattr(dataset, "column_names", []) or [])
    keep_columns = [column for column in METADATA_KEEP_COLUMNS if not column_names or column in column_names]
    if hasattr(dataset, "select_columns"):
        try:
            return dataset.select_columns(keep_columns)
        except Exception:
            pass

    if hasattr(dataset, "remove_columns"):
        if column_names:
            drop_columns = [column for column in column_names if column not in METADATA_KEEP_COLUMNS]
            if drop_columns:
                try:
                    return dataset.remove_columns(drop_columns)
                except Exception:
                    pass
        for column in PROBLEMATIC_METADATA_COLUMNS:
            try:
                dataset = dataset.remove_columns([column])
            except Exception:
                pass
    return dataset


def is_metadata_cast_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "unsupported cast" in message and "struct" in message


def iter_jsonl_metadata_file(file_obj: Any, *, gzip_compressed: bool = False) -> Iterator[dict[str, Any]]:
    stream = gzip.GzipFile(fileobj=file_obj) if gzip_compressed else file_obj
    with stream:
        for line in stream:
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            try:
                row = json.loads(line)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(row, dict):
                yield row


def stream_metadata_jsonl_fallback(category: str) -> Iterable[dict[str, Any]]:
    """Read raw Amazon metadata JSONL when Hugging Face feature casting fails."""

    from huggingface_hub import HfFileSystem

    fs = HfFileSystem()
    base_path = f"datasets/{DATASET_NAME}/raw/meta_categories/meta_{category}.jsonl"
    candidate_paths = [base_path, f"{base_path}.gz"]
    last_error: Exception | None = None
    for path in candidate_paths:
        try:
            file_obj = fs.open(path, "rb")
        except Exception as exc:  # noqa: BLE001 - try the next known storage suffix
            last_error = exc
            continue
        return iter_jsonl_metadata_file(file_obj, gzip_compressed=path.endswith(".gz"))
    raise RuntimeError(f"Unable to open raw Amazon metadata JSONL for category {category}.") from last_error


class MetadataIterableWithFallback:
    def __init__(self, primary: Iterable[dict[str, Any]], fallback_factory: Callable[[], Iterable[dict[str, Any]]]) -> None:
        self.primary = primary
        self.fallback_factory = fallback_factory

    def __iter__(self) -> Iterator[dict[str, Any]]:
        try:
            yield from self.primary
        except Exception as exc:  # noqa: BLE001 - narrow by predicate below
            if not is_metadata_cast_error(exc):
                raise
            log_ingestion(
                "Hugging Face metadata streaming hit a nested-field cast error; "
                "falling back to raw JSONL metadata streaming."
            )
            yield from self.fallback_factory()


def stream_metadata(category: str) -> Iterable[dict[str, Any]]:
    return stream_metadata_jsonl_fallback(category)


def stream_metadata_via_datasets(category: str) -> Iterable[dict[str, Any]]:
    dataset = load_dataset(
        DATASET_NAME,
        metadata_config_name(category),
        split="full",
        streaming=True,
        trust_remote_code=True,
    )
    return MetadataIterableWithFallback(
        prune_metadata_columns(dataset),
        fallback_factory=lambda: stream_metadata_jsonl_fallback(category),
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


def normalize_details_value(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value if value else None
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) and parsed else None
    return None


def normalize_optional_metadata_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    return []


def is_valid_review(review: dict[str, Any]) -> bool:
    parent_asin = review_parent_asin(review)
    return all(
        [
            has_value(review.get("user_id")),
            has_value(parent_asin),
            has_value(review.get("rating")),
            has_value(review.get("title")),
            has_value(review.get("text")),
        ]
    )


def is_valid_metadata(item: dict[str, Any], category: str, require_rating_number: bool = False) -> bool:
    details = normalize_details_value(item.get("details"))
    has_required_fields = all(
        [
            has_value(item.get("parent_asin")),
            has_value(item.get("title")),
            has_value(item.get("main_category")) or has_value(item.get("categories")) or has_value(category),
            has_value(item.get("features")),
            has_value(item.get("description")),
            parse_price(item.get("price")) is not None,
            has_value(item.get("average_rating")),
            has_value(item.get("store")),
            details is not None,
        ]
    )
    if not has_required_fields:
        return False
    if require_rating_number and not has_value(item.get("rating_number")):
        return False
    return True


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
    details = normalize_details_value(item.get("details")) or {}
    images = normalize_optional_metadata_list(item.get("images") or item.get("image"))
    bought_together = normalize_optional_metadata_list(item.get("bought_together"))
    normalized = AmazonProductMetadata(
        parent_asin=str(item["parent_asin"]),
        category=category,
        title=item.get("title"),
        main_category=item.get("main_category"),
        categories=item.get("categories") or [],
        features=item.get("features") or [],
        description=item.get("description") or [],
        images=images,
        bought_together=bought_together,
        price=parse_price(item.get("price")),
        average_rating=item.get("average_rating"),
        rating_number=item.get("rating_number"),
        store=item.get("store"),
        details=details,
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


def format_upsert_error(exc: Exception, table_name: str, conflict_key: str, batch_label: str | None = None) -> str:
    raw_message = str(exc)
    prefix = f"Failed to upsert {table_name}"
    if batch_label:
        prefix = f"{prefix} ({batch_label})"
    explanation = ""
    if "ON CONFLICT DO UPDATE command cannot affect row a second time" in raw_message:
        explanation = (
            f" This usually means the same {conflict_key} appeared more than once in one upload batch. "
            "The ingestion code deduplicates rows by the upsert key before upload; if this still appears, "
            "inspect the prepared batch for duplicate conflict keys."
        )
    return f"{prefix}. Supabase/Postgres said: {raw_message}.{explanation}"


def upsert_reviews(client: Client, reviews: list[dict[str, Any]], batch_label: str | None = None) -> int:
    unique_reviews, skipped_duplicates = dedupe_rows_by_key(reviews, "review_id")
    if skipped_duplicates:
        log_ingestion(f"Skipped {skipped_duplicates:,} duplicate review_id rows before upsert.")
    if not unique_reviews:
        return 0
    try:
        client.table("amazon_reviews").upsert(unique_reviews, on_conflict="review_id").execute()
    except Exception as exc:
        raise IngestionUploadError(format_upsert_error(exc, "amazon_reviews", "review_id", batch_label)) from exc
    return len(unique_reviews)


def upsert_metadata(client: Client, metadata: list[dict[str, Any]], batch_label: str | None = None) -> int:
    unique_metadata, skipped_duplicates = dedupe_rows_by_key(metadata, "parent_asin")
    if skipped_duplicates:
        log_ingestion(f"Skipped {skipped_duplicates:,} duplicate parent_asin metadata rows before upsert.")
    if not unique_metadata:
        return 0
    try:
        client.table("amazon_product_metadata").upsert(unique_metadata, on_conflict="parent_asin").execute()
    except Exception as exc:
        raise IngestionUploadError(
            format_upsert_error(exc, "amazon_product_metadata", "parent_asin", batch_label)
        ) from exc
    return len(unique_metadata)


def log_ingestion(message: str) -> None:
    print(f"[ingestion] {message}")


def limited(items: Iterable[dict[str, Any]], limit: int | None) -> Iterator[dict[str, Any]]:
    yield from items if limit is None else islice(items, limit)


ReviewSource = Iterable[dict[str, Any]] | Callable[[], Iterable[dict[str, Any]]]


def iter_reviews(reviews: ReviewSource, limit: int | None) -> Iterator[dict[str, Any]]:
    source = reviews() if callable(reviews) else reviews
    yield from limited(source, limit)


def iter_unique_valid_reviews(reviews: ReviewSource, limit: int | None) -> Iterator[dict[str, Any]]:
    seen_review_ids: set[str] = set()
    for review in iter_reviews(reviews, limit):
        if not is_valid_review(review):
            continue
        review_id = stable_review_id(review)
        if review_id in seen_review_ids:
            continue
        seen_review_ids.add(review_id)
        yield review


def select_eligible_users_from_counts(counts: Counter[str], min_reviews: int, max_users: int) -> list[str]:
    eligible = [(user_id, count) for user_id, count in counts.items() if count >= min_reviews]
    ordered = sorted(eligible, key=lambda item: (-item[1], item[0]))
    selected = ordered if max_users == 0 else ordered[:max_users]
    return [user_id for user_id, _count in selected]


def build_ingestion_plan(
    reviews: ReviewSource,
    metadata: Iterable[dict[str, Any]],
    category: str,
    min_reviews: int = 15,
    max_users: int = 100,
    extra_products: int = 1000,
    review_limit: int | None = None,
    require_rating_number: bool = False,
) -> dict[str, Any]:
    candidate_parent_asins: set[str] = set()
    valid_review_rows = 0
    skipped_invalid_reviews = 0
    duplicate_review_ids_skipped = 0
    seen_review_ids: set[str] = set()
    for review in iter_reviews(reviews, review_limit):
        if is_valid_review(review):
            review_id = stable_review_id(review)
            if review_id in seen_review_ids:
                duplicate_review_ids_skipped += 1
                continue
            seen_review_ids.add(review_id)
            valid_review_rows += 1
            if parent_asin := review_parent_asin(review):
                candidate_parent_asins.add(parent_asin)
        else:
            skipped_invalid_reviews += 1

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

        if not is_valid_metadata(item, category, require_rating_number=require_rating_number):
            skipped_sparse_metadata += 1
            continue

        valid_metadata_rows += 1
        if parent_asin in candidate_parent_asins:
            reviewed_metadata_by_asin[parent_asin] = item
        elif extra_products > 0 and len(extra_metadata_by_asin) < extra_products:
            extra_metadata_by_asin[parent_asin] = item

    user_pair_counts: Counter[str] = Counter()
    valid_review_product_pairs = 0
    for review in iter_unique_valid_reviews(reviews, review_limit):
        parent_asin = review_parent_asin(review)
        if parent_asin and parent_asin in reviewed_metadata_by_asin:
            user_pair_counts[str(review["user_id"])] += 1
            valid_review_product_pairs += 1

    selected_user_ids = set(
        select_eligible_users_from_counts(user_pair_counts, min_reviews=min_reviews, max_users=max_users)
    )
    selected_reviews = []
    for review in iter_unique_valid_reviews(reviews, review_limit):
        parent_asin = review_parent_asin(review)
        if parent_asin and parent_asin in reviewed_metadata_by_asin and str(review["user_id"]) in selected_user_ids:
            selected_reviews.append(review)

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
        "valid_review_rows": valid_review_rows,
        "valid_review_product_pairs": valid_review_product_pairs,
        "skipped_invalid_reviews": skipped_invalid_reviews,
        "skipped_sparse_metadata": skipped_sparse_metadata,
        "duplicate_review_ids_skipped": duplicate_review_ids_skipped,
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
    require_rating_number: bool = False,
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
        lambda: stream_reviews(category),
        stream_metadata(category),
        category=category,
        min_reviews=effective_min_reviews,
        max_users=max_users,
        extra_products=extra_products,
        review_limit=effective_review_limit,
        require_rating_number=require_rating_number,
    )

    normalized_reviews, upload_duplicate_review_ids_skipped = dedupe_rows_by_key(
        (normalize_review(review) for review in plan["reviews_to_upload"]),
        "review_id",
    )
    normalized_metadata, duplicate_metadata_parent_asins_skipped = dedupe_rows_by_key(
        (normalize_metadata(item, category) for item in plan["metadata_to_upload"]),
        "parent_asin",
    )
    duplicate_review_ids_skipped = plan["duplicate_review_ids_skipped"] + upload_duplicate_review_ids_skipped
    if duplicate_review_ids_skipped:
        log_ingestion(f"Skipped {duplicate_review_ids_skipped:,} duplicate review_id rows during planning.")
    if duplicate_metadata_parent_asins_skipped:
        log_ingestion(
            f"Skipped {duplicate_metadata_parent_asins_skipped:,} duplicate parent_asin metadata rows during planning."
        )

    log_ingestion(
        "Prepared upload: "
        f"category={category}, dry_run={dry_run}, "
        f"reviews={len(normalized_reviews)}, metadata_rows={len(normalized_metadata)}, "
        f"selected_users={len(plan['selected_user_ids'])}, extra_products_added={len(plan['extra_metadata'])}"
    )

    uploaded_reviews = 0
    uploaded_metadata = 0
    if not dry_run:
        client = client or get_supabase_client()
        log_ingestion("Review upsert starting.")
        for batch_index, batch in enumerate(batched(normalized_reviews, batch_size), start=1):
            log_ingestion(f"Upserting review batch {batch_index}: {len(batch):,} rows")
            uploaded_reviews += upsert_reviews(client, batch, batch_label=f"review batch {batch_index}")
        log_ingestion(f"Review upsert complete: {uploaded_reviews:,} rows")

        log_ingestion("Metadata upsert starting.")
        for batch_index, batch in enumerate(batched(normalized_metadata, batch_size), start=1):
            log_ingestion(f"Upserting metadata batch {batch_index}: {len(batch):,} rows")
            uploaded_metadata += upsert_metadata(client, batch, batch_label=f"metadata batch {batch_index}")
        log_ingestion(f"Metadata upsert complete: {uploaded_metadata:,} rows")
    else:
        log_ingestion("Dry run enabled; no Supabase upserts will be performed.")
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
        "duplicate_review_ids_skipped": duplicate_review_ids_skipped,
        "duplicate_metadata_parent_asins_skipped": duplicate_metadata_parent_asins_skipped,
        "dry_run": dry_run,
    }

    if verify and not dry_run:
        client = client or get_supabase_client()
        log_ingestion("DB verification starting.")
        verification = verify_uploaded_counts(
            client,
            [review["review_id"] for review in normalized_reviews],
            [metadata["parent_asin"] for metadata in normalized_metadata],
            min_reviews=effective_min_reviews,
            batch_size=batch_size,
        )
        result.update(verification)
        log_ingestion(
            "DB verification result: "
            f"users_with_min_reviews={verification['db_users_with_min_reviews']}, "
            f"reviews_with_matching_metadata={verification['db_reviews_with_matching_metadata']}, "
            f"reviews_missing_metadata={verification['db_reviews_missing_metadata']}"
        )
    elif verify:
        result.update(
            {
                "db_users_with_min_reviews": 0,
                "db_reviews_with_matching_metadata": 0,
                "db_reviews_missing_metadata": 0,
            }
        )

    log_ingestion(f"Final result: {result}")
    return result
