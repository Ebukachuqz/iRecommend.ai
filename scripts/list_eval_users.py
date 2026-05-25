from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.constants import PERSONA_TRAIN_SPLIT, TASK_A_HOLDOUT_SPLIT, TASK_B_HOLDOUT_SPLIT
from src.db.supabase_client import get_supabase_client
from scripts.check_category_readiness import (
    fetch_category_products,
    fetch_reviews_for_parent_asins,
    fetch_user_personas_for_category,
    fetch_user_preference_vectors_for_category,
)


def compute_user_split_counts(reviews: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    by_user: dict[str, Counter[str]] = {}
    for row in reviews:
        user_id = str(row.get("user_id") or "")
        if not user_id:
            continue
        by_user.setdefault(user_id, Counter())
        by_user[user_id][str(row.get("task_split") or PERSONA_TRAIN_SPLIT)] += 1
    return by_user


def list_eval_users(
    client: Any,
    category: str,
    limit: int,
    *,
    require_persona: bool = False,
    require_preference_vector: bool = False,
    task: str = "both",
) -> list[dict[str, Any]]:
    products = fetch_category_products(client, category)
    parent_asins = sorted({str(row["parent_asin"]) for row in products})
    reviews = fetch_reviews_for_parent_asins(client, parent_asins)
    by_user = compute_user_split_counts(reviews)

    personas = fetch_user_personas_for_category(client, category)
    preference_vectors = fetch_user_preference_vectors_for_category(client, category)
    users_with_personas = {str(row["user_id"]) for row in personas if row.get("user_id")}
    users_with_preference = {str(row["user_id"]) for row in preference_vectors if row.get("user_id")}

    rows: list[dict[str, Any]] = []
    for user_id in sorted(by_user):
        counts = by_user[user_id]
        has_persona = user_id in users_with_personas
        has_preference_vector = user_id in users_with_preference
        row = {
            "user_id": user_id,
            "category": category,
            "has_persona": has_persona,
            "has_preference_vector": has_preference_vector,
            "persona_train_count": int(counts.get(PERSONA_TRAIN_SPLIT, 0)),
            "task_a_holdout_count": int(counts.get(TASK_A_HOLDOUT_SPLIT, 0)),
            "task_b_holdout_count": int(counts.get(TASK_B_HOLDOUT_SPLIT, 0)),
        }
        rows.append(row)

    def allowed(item: dict[str, Any]) -> bool:
        if require_persona and not item["has_persona"]:
            return False
        if require_preference_vector and not item["has_preference_vector"]:
            return False
        if task == "task_a":
            return item["task_a_holdout_count"] > 0 and item["has_persona"]
        if task == "task_b":
            # For Task B, preference vectors are optional unless explicitly required via --require-preference-vector.
            return item["task_b_holdout_count"] > 0 and item["has_persona"]
        if task == "both":
            return item["task_a_holdout_count"] > 0 and item["task_b_holdout_count"] > 0 and item["has_persona"]
        raise ValueError("task must be one of task_a, task_b, both")

    filtered = [row for row in rows if allowed(row)]
    if limit and limit > 0:
        filtered = filtered[:limit]
    return filtered


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="List evaluation-ready users for a category.")
    parser.add_argument("--category", default=settings.default_category)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--require-persona", action="store_true")
    parser.add_argument("--require-preference-vector", action="store_true")
    parser.add_argument("--task", choices=["task_a", "task_b", "both"], default="both")
    args = parser.parse_args()

    client = get_supabase_client()
    rows = list_eval_users(
        client,
        args.category,
        args.limit,
        require_persona=args.require_persona,
        require_preference_vector=args.require_preference_vector,
        task=args.task,
    )
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
