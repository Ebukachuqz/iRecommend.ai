import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.ingest_amazon import ingest_category


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Amazon Reviews 2023 into Supabase.")
    parser.add_argument("--category", default=None)
    parser.add_argument("--min-reviews", "--min-user-reviews", dest="min_reviews", type=int, default=15)
    parser.add_argument("--max-users", type=int, default=100)
    parser.add_argument("--extra-products", type=int, default=1000)
    parser.add_argument("--review-limit", "--max-reviews", dest="review_limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    result = ingest_category(
        category=args.category,
        min_reviews=args.min_reviews,
        max_users=args.max_users,
        extra_products=args.extra_products,
        review_limit=args.review_limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        verify=args.verify,
    )
    print(result)


if __name__ == "__main__":
    main()
