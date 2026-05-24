from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.constants import TASK_A_HOLDOUT_SPLIT, TASK_B_HOLDOUT_SPLIT
from src.db.supabase_client import get_supabase_client


def fetch_user_holdout_rows(client: Any, user_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("amazon_reviews")
        .select("task_split,parent_asin,rating,title,review_id")
        .eq("user_id", user_id)
        .in_("task_split", [TASK_A_HOLDOUT_SPLIT, TASK_B_HOLDOUT_SPLIT])
        .order("timestamp", desc=True)
        .execute()
    )
    return list(response.data or [])


def fetch_metadata_titles(client: Any, parent_asins: list[str]) -> dict[str, str]:
    if not parent_asins:
        return {}
    response = (
        client.table("amazon_product_metadata")
        .select("parent_asin,title")
        .in_("parent_asin", list(dict.fromkeys(parent_asins)))
        .execute()
    )
    return {str(row["parent_asin"]): str(row.get("title") or "") for row in response.data or []}


def list_user_holdouts(client: Any, user_id: str, category: str | None = None) -> list[dict[str, Any]]:
    rows = fetch_user_holdout_rows(client, user_id)
    titles = fetch_metadata_titles(client, [str(row["parent_asin"]) for row in rows if row.get("parent_asin")])
    output: list[dict[str, Any]] = []
    for row in rows:
        parent_asin = str(row.get("parent_asin") or "")
        output.append(
            {
                "task_split": row.get("task_split"),
                "parent_asin": parent_asin,
                "product_title": titles.get(parent_asin, ""),
                "rating": row.get("rating"),
                "review_title": row.get("title"),
                "review_id": row.get("review_id"),
            }
        )
    return output


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="List a user's holdout reviews (Task A + Task B).")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--category", default=settings.default_category)
    args = parser.parse_args()

    client = get_supabase_client()
    rows = list_user_holdouts(client, args.user_id, category=args.category)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()

