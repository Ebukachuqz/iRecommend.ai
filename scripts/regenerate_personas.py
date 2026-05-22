import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from src.personas.generator import PersonaGenerator


def fetch_user_ids() -> list[str]:
    client = get_supabase_client()
    user_ids: set[str] = set()
    start = 0
    page_size = 1000
    while True:
        end = start + page_size - 1
        response = (
            client.table("amazon_reviews")
            .select("user_id")
            .eq("task_split", "persona_train")
            .range(start, end)
            .execute()
        )
        batch = list(response.data or [])
        user_ids.update(row["user_id"] for row in batch)
        if len(batch) < page_size:
            break
        start += page_size
    return sorted(user_ids)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Regenerate personas from persona_train reviews.")
    parser.add_argument("--category", default=settings.default_category)
    parser.add_argument("--user-id", action="append", dest="user_ids")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    user_ids = args.user_ids or fetch_user_ids()
    if args.limit:
        user_ids = user_ids[: args.limit]

    generator = PersonaGenerator()
    for user_id in user_ids:
        result = generator.regenerate_persona(user_id=user_id, category=args.category, store=True)
        print({"user_id": user_id, "source_review_count": len(result["source_review_ids"])})


if __name__ == "__main__":
    main()
