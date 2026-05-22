import argparse

from src.ingestion.ingest_amazon import ingest_category


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Amazon Reviews 2023 into Supabase.")
    parser.add_argument("--category", default=None)
    parser.add_argument("--min-user-reviews", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-reviews", type=int, default=None)
    args = parser.parse_args()

    result = ingest_category(
        category=args.category,
        min_user_reviews=args.min_user_reviews,
        batch_size=args.batch_size,
        max_reviews=args.max_reviews,
    )
    print(result)


if __name__ == "__main__":
    main()
