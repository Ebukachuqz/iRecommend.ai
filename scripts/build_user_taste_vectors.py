from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.task_b_recommendation.embeddings import DEFAULT_EMBEDDING_MODEL
from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.taste_vector import (
    build_and_store_user_taste_vector,
    fetch_user_taste_vector,
)


PAGE_SIZE = 1000


def fetch_persona_user_ids(category: str, client=None) -> list[str]:
    client = client or get_supabase_client()
    user_ids: set[str] = set()
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = (
            client.table("user_personas")
            .select("user_id")
            .eq("category", category)
            .range(start, end)
            .execute()
        )
        batch = list(response.data or [])
        user_ids.update(str(row["user_id"]) for row in batch if row.get("user_id"))
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return sorted(user_ids)


def build_one(user_id: str, category: str, embedding_model: str, client=None) -> dict:
    embedding, sources = build_and_store_user_taste_vector(
        user_id,
        category,
        embedding_model=embedding_model,
        client=client,
    )
    return {
        "user_id": user_id,
        "category": category,
        "source_parent_asins": len(sources),
        "stored": bool(embedding),
    }


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Build a user taste vector from persona_train liked reviews.")
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--category", default=settings.default_category)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    client = get_supabase_client()

    if args.user_id:
        print(build_one(args.user_id, args.category, args.model, client=client))
        return

    user_ids = fetch_persona_user_ids(args.category, client=client)
    if args.limit and args.limit > 0:
        user_ids = user_ids[: args.limit]

    users_considered = len(user_ids)
    built_count = 0
    skipped_existing = 0
    skipped_no_sources = 0
    failed_count = 0

    for index, user_id in enumerate(user_ids, start=1):
        print(f"[taste-vector] Processing user {index}/{users_considered}: user_id={user_id}")
        try:
            if not args.force:
                existing = fetch_user_taste_vector(user_id, args.category, client=client)
                if existing:
                    skipped_existing += 1
                    print(f"[taste-vector] Skip existing: user_id={user_id}")
                    continue

            result = build_one(user_id, args.category, args.model, client=client)
            if not result["stored"]:
                skipped_no_sources += 1
                print(f"[taste-vector] Skip no sources: user_id={user_id}")
                continue
            built_count += 1
            print(f"[taste-vector] Built: {result}")
        except Exception as exc:
            failed_count += 1
            print(f"[taste-vector] Failed: user_id={user_id}, error={exc}")

    print(
        {
            "category": args.category,
            "users_considered": users_considered,
            "built_count": built_count,
            "skipped_existing": skipped_existing,
            "skipped_no_sources": skipped_no_sources,
            "failed_count": failed_count,
        }
    )


if __name__ == "__main__":
    main()
