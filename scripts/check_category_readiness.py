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


PAGE_SIZE = 1000
IN_FILTER_CHUNK = 500


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


def fetch_category_products(client: Any, category: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = (
            client.table("amazon_product_metadata")
            .select("parent_asin,category,main_category,categories")
            .range(start, end)
            .execute()
        )
        batch = list(response.data or [])
        rows.extend([row for row in batch if row.get("parent_asin") and product_matches_category(row, category)])
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def fetch_reviews_for_parent_asins(client: Any, parent_asins: list[str]) -> list[dict[str, Any]]:
    if not parent_asins:
        return []
    rows: list[dict[str, Any]] = []
    for asin_chunk in chunked(parent_asins, IN_FILTER_CHUNK):
        start = 0
        while True:
            end = start + PAGE_SIZE - 1
            response = (
                client.table("amazon_reviews")
                .select("review_id,user_id,parent_asin,task_split")
                .in_("parent_asin", asin_chunk)
                .range(start, end)
                .execute()
            )
            batch = list(response.data or [])
            rows.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            start += PAGE_SIZE
    return rows


def count_table_rows_for_category_parent_asins(client: Any, table: str, parent_asins: list[str], id_col: str) -> int:
    if not parent_asins:
        return 0
    seen: set[str] = set()
    for asin_chunk in chunked(parent_asins, IN_FILTER_CHUNK):
        start = 0
        while True:
            end = start + PAGE_SIZE - 1
            response = (
                client.table(table)
                .select(id_col)
                .in_("parent_asin", asin_chunk)
                .range(start, end)
                .execute()
            )
            batch = list(response.data or [])
            for row in batch:
                value = row.get(id_col)
                if value:
                    seen.add(str(value))
            if len(batch) < PAGE_SIZE:
                break
            start += PAGE_SIZE
    return len(seen)


def fetch_user_personas_for_category(client: Any, category: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = (
            client.table("user_personas")
            .select("user_id,category")
            .eq("category", category)
            .range(start, end)
            .execute()
        )
        batch = list(response.data or [])
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def fetch_user_preference_vectors_for_category(client: Any, category: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = (
            client.table("user_preference_vectors")
            .select("user_id,category")
            .eq("category", category)
            .range(start, end)
            .execute()
        )
        batch = list(response.data or [])
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def compute_category_readiness(client: Any, category: str) -> dict[str, Any]:
    products = fetch_category_products(client, category)
    parent_asins = sorted({str(row["parent_asin"]) for row in products})

    reviews = fetch_reviews_for_parent_asins(client, parent_asins)
    split_counts = Counter(str(row.get("task_split") or PERSONA_TRAIN_SPLIT) for row in reviews)
    by_user: dict[str, Counter[str]] = {}
    for row in reviews:
        user_id = str(row.get("user_id") or "")
        if not user_id:
            continue
        by_user.setdefault(user_id, Counter())
        by_user[user_id][str(row.get("task_split") or PERSONA_TRAIN_SPLIT)] += 1

    personas = fetch_user_personas_for_category(client, category)
    preference_vectors = fetch_user_preference_vectors_for_category(client, category)
    users_with_personas = {str(row["user_id"]) for row in personas if row.get("user_id")}
    users_with_preference_vectors = {str(row["user_id"]) for row in preference_vectors if row.get("user_id")}

    users_with_persona_and_task_a_holdout = [
        user_id
        for user_id, counts in by_user.items()
        if user_id in users_with_personas and counts.get(TASK_A_HOLDOUT_SPLIT, 0) > 0
    ]
    users_with_persona_preference_and_task_b_holdout = [
        user_id
        for user_id, counts in by_user.items()
        if user_id in users_with_personas
        and user_id in users_with_preference_vectors
        and counts.get(TASK_B_HOLDOUT_SPLIT, 0) > 0
    ]

    product_embeddings_count = count_table_rows_for_category_parent_asins(
        client, "product_embeddings", parent_asins, "parent_asin"
    )

    task_a_ready = len(users_with_persona_and_task_a_holdout) > 0
    task_b_ready = len(users_with_persona_preference_and_task_b_holdout) > 0 and product_embeddings_count > 0

    return {
        "category": category,
        "product_metadata_rows": len(parent_asins),
        "review_rows_joined": len(reviews),
        "persona_train_reviews": int(split_counts.get(PERSONA_TRAIN_SPLIT, 0)),
        "task_a_holdout_reviews": int(split_counts.get(TASK_A_HOLDOUT_SPLIT, 0)),
        "task_b_holdout_reviews": int(split_counts.get(TASK_B_HOLDOUT_SPLIT, 0)),
        "user_personas": len(personas),
        "product_embeddings": product_embeddings_count,
        "user_preference_vectors": len(preference_vectors),
        "users_with_personas": len(users_with_personas),
        "users_with_persona_and_task_a_holdout": len(users_with_persona_and_task_a_holdout),
        "users_with_persona_preference_and_task_b_holdout": len(users_with_persona_preference_and_task_b_holdout),
        "task_a_smoke_ready": task_a_ready,
        "task_b_smoke_ready": task_b_ready,
    }


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Check whether a category is ready for Task A/Task B smoke tests.")
    parser.add_argument("--category", default=settings.default_category)
    args = parser.parse_args()

    client = get_supabase_client()
    result = compute_category_readiness(client, args.category)
    print(result)


if __name__ == "__main__":
    main()
