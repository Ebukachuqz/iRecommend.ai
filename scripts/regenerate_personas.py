import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from src.personas.generator import PersonaGenerator, log_persona_generation


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

    log_persona_generation(
        f"Starting persona regeneration: category={args.category}, users={len(user_ids)}, limit={args.limit}"
    )
    generator = PersonaGenerator()
    success_count = 0
    failure_count = 0
    for index, user_id in enumerate(user_ids, start=1):
        log_persona_generation(f"Processing user {index}/{len(user_ids)}: user_id={user_id}")
        try:
            result = generator.regenerate_persona(user_id=user_id, category=args.category, store=True)
        except Exception as exc:
            failure_count += 1
            log_persona_generation(f"Persona generation failed: user_id={user_id}, error={exc}")
            continue
        success_count += 1
        summary = {"user_id": user_id, "source_review_count": len(result["source_review_ids"])}
        log_persona_generation(f"Persona generation succeeded: {summary}")
        print(summary)
    log_persona_generation(
        f"Persona regeneration complete: succeeded={success_count}, failed={failure_count}, total={len(user_ids)}"
    )


if __name__ == "__main__":
    main()
