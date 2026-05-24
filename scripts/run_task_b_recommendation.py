from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.task_b_recommendation.schema import RecommendationRequest
from src.task_b_recommendation.service import recommend, recommend_for_user


def print_json(payload: object) -> None:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task B persona-aware recommendations.")
    parser.add_argument("--user-id")
    parser.add_argument("--category", default="All_Beauty")
    parser.add_argument("--request")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--session-id")
    parser.add_argument("--cold-start", action="store_true")
    args = parser.parse_args()

    if args.cold_start and not args.user_id:
        output = recommend(
            RecommendationRequest(
                category=args.category,
                request=args.request,
                limit=args.limit,
                session_id=args.session_id,
                cold_start=True,
            )
        )
    else:
        if not args.user_id:
            parser.error("--user-id is required unless --cold-start is used")
        output = recommend_for_user(
            args.user_id,
            category=args.category,
            request=args.request,
            limit=args.limit,
            session_id=args.session_id,
            cold_start=args.cold_start,
        )
    print_json(output)


if __name__ == "__main__":
    main()
