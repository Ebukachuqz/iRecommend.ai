from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.supabase_client import get_supabase_client
from src.evaluation.utils import (
    VALID_CATEGORIES,
    fetch_all_paginated,
    resolve_category_for_reviews,
)
from src.task_a_simulation.service import simulate_review_for_specific_holdout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_candidates(category: str, limit: int, supabase):
    reviews = fetch_all_paginated(
        supabase,
        "amazon_reviews",
        filters=[("task_split", "eq", "task_a_holdout")],
    )
    resolve_category_for_reviews(reviews, supabase)

    filtered = [r for r in reviews if r.get("category") == category]
    return filtered[:limit]


def fetch_existing_simulation_review_ids(review_ids: list[str], supabase) -> set[str]:
    if not review_ids:
        return set()
    existing = set()
    chunk_size = 500
    for start in range(0, len(review_ids), chunk_size):
        chunk = review_ids[start : start + chunk_size]
        rows = fetch_all_paginated(
            supabase,
            "simulation_results",
            select="holdout_review_id",
            filters=[("holdout_review_id", "in_", chunk)],
        )
        existing.update(r["holdout_review_id"] for r in rows if r.get("holdout_review_id"))
    return existing


def fetch_persona_user_ids(category: str, supabase) -> set[str]:
    rows = fetch_all_paginated(
        supabase,
        "user_personas",
        select="user_id",
        filters=[("category", "eq", category)],
    )
    return set(r["user_id"] for r in rows)


def run_batch(args: argparse.Namespace) -> dict:
    supabase = get_supabase_client()
    category = args.category
    limit = args.limit
    dry_run = args.dry_run

    logger.info("Fetching task_a_holdout candidates for %s (limit=%d)", category, limit)
    candidates = fetch_candidates(category, limit, supabase)
    logger.info("Found %d candidates", len(candidates))

    review_ids = [r["review_id"] for r in candidates]
    existing = fetch_existing_simulation_review_ids(review_ids, supabase)
    persona_users = fetch_persona_user_ids(category, supabase)

    stats = {
        "category": category,
        "candidates_found": len(candidates),
        "attempted": 0,
        "created": 0,
        "skipped_existing": 0,
        "skipped_no_persona": 0,
        "failed": 0,
        "dry_run": dry_run,
    }

    for i, review in enumerate(candidates, 1):
        rid = review["review_id"]
        uid = review["user_id"]
        asin = review["parent_asin"]
        prefix = f"[{i}/{len(candidates)}]"

        if rid in existing:
            logger.info("%s skipped_existing review_id=%s user_id=%s", prefix, rid, uid)
            stats["skipped_existing"] += 1
            continue

        if uid not in persona_users:
            logger.info("%s skipped_no_persona review_id=%s user_id=%s", prefix, rid, uid)
            stats["skipped_no_persona"] += 1
            continue

        stats["attempted"] += 1
        logger.info("%s processing review_id=%s user_id=%s parent_asin=%s", prefix, rid, uid, asin)

        if dry_run:
            logger.info("%s dry_run — would simulate", prefix)
            stats["created"] += 1
            continue

        try:
            simulate_review_for_specific_holdout(
                user_id=uid,
                holdout_review=review,
                category=category,
                client=supabase,
            )
            logger.info("%s created", prefix)
            stats["created"] += 1
        except Exception as exc:
            logger.error("%s failed: %s", prefix, exc)
            stats["failed"] += 1

    logger.info("--- Summary ---")
    for k, v in stats.items():
        logger.info("  %s: %s", k, v)

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch Task A simulation for evaluation preparation."
    )
    parser.add_argument("--category", required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    if args.category not in VALID_CATEGORIES:
        parser.error(f"Invalid category: {args.category!r}. Must be one of {VALID_CATEGORIES}")

    run_batch(args)


if __name__ == "__main__":
    main()
