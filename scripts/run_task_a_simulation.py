from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.task_a_simulation.service import (
    list_unseen_products,
    simulate_review_for_holdout,
    simulate_review_for_product,
)


def print_json(payload: object) -> None:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    elif isinstance(payload, list):
        payload = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in payload
        ]
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task A review simulation.")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--category", default="All_Beauty")
    parser.add_argument("--parent-asin")
    parser.add_argument("--use-holdout", action="store_true")
    parser.add_argument("--nigerian-mode", action="store_true")
    parser.add_argument("--list-unseen", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    if args.list_unseen:
        products = list_unseen_products(args.user_id, limit=args.limit)
        print_json(products)
        return

    if args.use_holdout:
        output = simulate_review_for_holdout(
            args.user_id,
            category=args.category,
            nigerian_mode=args.nigerian_mode,
        )
        print_json(output)
        return

    if not args.parent_asin:
        parser.error("--parent-asin is required unless --use-holdout or --list-unseen is set")

    output = simulate_review_for_product(
        args.user_id,
        args.parent_asin,
        category=args.category,
        nigerian_mode=args.nigerian_mode,
    )
    print_json(output)


if __name__ == "__main__":
    main()
