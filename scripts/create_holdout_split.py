from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

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


def fetch_reviews(category: str, page_size: int = 1000) -> list[dict[str, Any]]:
    client = get_supabase_client()
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + page_size - 1
        response = (
            client.table("amazon_reviews")
            .select("review_id,user_id,rating,timestamp,category")
            .eq("category", category)
            .range(start, end)
            .execute()
        )
        batch = list(response.data or [])
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows


def build_holdout_updates(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in reviews:
        by_user[str(review["user_id"])].append(review)

    updates: list[dict[str, Any]] = []
    for user_reviews in by_user.values():
        ordered = sorted(user_reviews, key=lambda item: parse_timestamp(item.get("timestamp")), reverse=True)
        for index, review in enumerate(ordered):
            split = PERSONA_TRAIN_SPLIT
            used_for_persona = True
            if index == 0:
                split = TASK_A_HOLDOUT_SPLIT
                used_for_persona = False
            elif index == 1 and float(review.get("rating") or 0) >= 4:
                split = TASK_B_HOLDOUT_SPLIT
                used_for_persona = False
            elif index == 1:
                used_for_persona = False
            updates.append(
                {
                    "review_id": review["review_id"],
                    "task_split": split,
                    "used_for_persona": used_for_persona,
                }
            )
    return updates


def apply_updates(updates: list[dict[str, Any]], batch_size: int = 500) -> None:
    client = get_supabase_client()
    grouped: dict[tuple[str, bool], list[str]] = defaultdict(list)
    for update in updates:
        grouped[(update["task_split"], update["used_for_persona"])].append(update["review_id"])

    for (task_split, used_for_persona), review_ids in grouped.items():
        for start in range(0, len(review_ids), batch_size):
            batch_ids = review_ids[start : start + batch_size]
            (
                client.table("amazon_reviews")
                .update({"task_split": task_split, "used_for_persona": used_for_persona})
                .in_("review_id", batch_ids)
                .execute()
            )


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Create chronological holdout splits in Supabase.")
    parser.add_argument("--category", default=settings.default_category)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    reviews = fetch_reviews(args.category)
    updates = build_holdout_updates(reviews)
    counts: dict[str, int] = defaultdict(int)
    for update in updates:
        counts[update["task_split"]] += 1

    if not args.dry_run:
        apply_updates(updates, batch_size=args.batch_size)

    print({"category": args.category, "dry_run": args.dry_run, "review_count": len(reviews), "splits": dict(counts)})


if __name__ == "__main__":
    main()
