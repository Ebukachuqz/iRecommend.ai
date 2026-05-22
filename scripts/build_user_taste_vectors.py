from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.task_b_recommendation.embeddings import DEFAULT_EMBEDDING_MODEL
from src.task_b_recommendation.taste_vector import build_and_store_user_taste_vector


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a user taste vector from persona_train liked reviews.")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--category", default="All_Beauty")
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    args = parser.parse_args()

    embedding, sources = build_and_store_user_taste_vector(
        args.user_id,
        args.category,
        embedding_model=args.model,
    )
    print(
        {
            "user_id": args.user_id,
            "category": args.category,
            "source_parent_asins": len(sources),
            "stored": bool(embedding),
        }
    )


if __name__ == "__main__":
    main()
