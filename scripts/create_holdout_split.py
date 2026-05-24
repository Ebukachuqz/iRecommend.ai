from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from math import floor
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.constants import PERSONA_TRAIN_SPLIT, TASK_A_HOLDOUT_SPLIT, TASK_B_HOLDOUT_SPLIT
from src.db.supabase_client import get_supabase_client


def parse_timestamp(value: Any) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def category_values(item: dict[str, Any]) -> set[str]:
    values = {str(item.get("category") or "").strip(), str(item.get("main_category") or "").strip()}
    categories = item.get("categories") or []
    if isinstance(categories, list):
        for value in categories:
            if isinstance(value, list):
                values.update(str(part).strip() for part in value)
            else:
                values.add(str(value).strip())
    return {value for value in values if value}


def product_matches_category(item: dict[str, Any], category: str) -> bool:
    return category in category_values(item)


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_category_parent_asins(category: str, page_size: int = 1000) -> set[str]:
    client = get_supabase_client()
    parent_asins: set[str] = set()
    start = 0
    while True:
        end = start + page_size - 1
        response = (
            client.table("amazon_product_metadata")
            .select("parent_asin,category,main_category,categories")
            .range(start, end)
            .execute()
        )
        rows = list(response.data or [])
        for row in rows:
            parent_asin = row.get("parent_asin")
            if parent_asin and product_matches_category(row, category):
                parent_asins.add(str(parent_asin))
        if len(rows) < page_size:
            break
        start += page_size
    return parent_asins


def fetch_reviews(category: str | None = None, page_size: int = 1000) -> list[dict[str, Any]]:
    client = get_supabase_client()
    category_parent_asins = fetch_category_parent_asins(category, page_size=page_size) if category else None
    if category is not None and not category_parent_asins:
        return []

    rows: list[dict[str, Any]] = []
    asin_chunks = chunked(sorted(category_parent_asins), 500) if category_parent_asins is not None else [None]
    for asin_chunk in asin_chunks:
        start = 0
        while True:
            end = start + page_size - 1
            query = (
                client.table("amazon_reviews")
                .select("review_id,user_id,parent_asin,rating,timestamp,task_split")
                .range(start, end)
            )
            if asin_chunk is not None:
                query = query.in_("parent_asin", asin_chunk)
            response = query.execute()
            batch = list(response.data or [])
            rows.extend(batch)
            if len(batch) < page_size:
                break
            start += page_size
    return rows


def split_counts(total_reviews: int) -> tuple[int, int, int]:
    if total_reviews <= 0:
        return 0, 0, 0
    if total_reviews == 1:
        return 1, 0, 0
    if total_reviews == 2:
        return 1, 1, 0
    train_count = floor(0.70 * total_reviews)
    remaining = total_reviews - train_count
    if total_reviews >= 3 and remaining < 2:
        train_count = total_reviews - 2
        remaining = 2
    if remaining <= 0:
        return total_reviews, 0, 0
    task_a_count = remaining // 2
    task_b_count = remaining - task_a_count
    if total_reviews >= 3:
        task_a_count = max(task_a_count, 1)
        task_b_count = max(task_b_count, 1)
        train_count = total_reviews - task_a_count - task_b_count
    return train_count, task_a_count, task_b_count


def build_holdout_updates(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in reviews:
        by_user[str(review["user_id"])].append(review)

    updates: list[dict[str, Any]] = []
    for user_id in sorted(by_user):
        ordered = sorted(
            by_user[user_id],
            key=lambda item: (parse_timestamp(item.get("timestamp")), str(item.get("review_id") or "")),
        )
        train_count, task_a_count, _task_b_count = split_counts(len(ordered))
        task_a_start = train_count
        task_b_start = train_count + task_a_count
        for index, review in enumerate(ordered):
            if index < task_a_start:
                split = PERSONA_TRAIN_SPLIT
            elif index < task_b_start:
                split = TASK_A_HOLDOUT_SPLIT
            else:
                split = TASK_B_HOLDOUT_SPLIT
            updates.append(
                {
                    "review_id": review["review_id"],
                    "task_split": split,
                }
            )
    return updates


def existing_split_counts(reviews: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for review in reviews:
        split = review.get("task_split") or PERSONA_TRAIN_SPLIT
        counts[str(split)] += 1
    return dict(counts)


def ensure_overwrite_allowed(reviews: list[dict[str, Any]], overwrite: bool) -> None:
    if overwrite:
        return
    existing = existing_split_counts(reviews)
    already_split = any(
        existing.get(split, 0) > 0
        for split in (TASK_A_HOLDOUT_SPLIT, TASK_B_HOLDOUT_SPLIT)
    )
    if already_split:
        raise ValueError(
            "This category already has holdout splits. Pass --overwrite to intentionally re-split it."
        )


def apply_updates(updates: list[dict[str, Any]], batch_size: int = 500) -> None:
    client = get_supabase_client()
    grouped: dict[str, list[str]] = defaultdict(list)
    for update in updates:
        grouped[update["task_split"]].append(update["review_id"])

    for task_split, review_ids in grouped.items():
        for start in range(0, len(review_ids), batch_size):
            batch_ids = review_ids[start : start + batch_size]
            (
                client.table("amazon_reviews")
                .update({"task_split": task_split})
                .in_("review_id", batch_ids)
                .execute()
            )


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Create per-user ratio holdout splits in Supabase.")
    parser.add_argument("--category", default=settings.default_category)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    reviews = fetch_reviews(category=args.category)
    ensure_overwrite_allowed(reviews, overwrite=args.overwrite)
    updates = build_holdout_updates(reviews)
    counts: dict[str, int] = defaultdict(int)
    for update in updates:
        counts[update["task_split"]] += 1

    if not args.dry_run:
        apply_updates(updates, batch_size=args.batch_size)

    print(
        {
            "category": args.category,
            "dry_run": args.dry_run,
            "overwrite": args.overwrite,
            "review_count": len(reviews),
            "splits": dict(counts),
        }
    )


if __name__ == "__main__":
    main()
