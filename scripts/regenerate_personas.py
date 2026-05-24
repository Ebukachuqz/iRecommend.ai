import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from src.personas.generator import PersonaGenerator, log_persona_generation
from src.utils.run_summary import build_run_summary, save_run_summary


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
    parser.add_argument("--max-reviews-per-user", type=int, default=10)
    parser.add_argument("--output-dir", default="outputs/personas")
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
    total_review_count_available = 0
    total_review_count_used = 0
    user_review_counts: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for index, user_id in enumerate(user_ids, start=1):
        log_persona_generation(f"Processing user {index}/{len(user_ids)}: user_id={user_id}")
        try:
            result = generator.regenerate_persona(
                user_id=user_id,
                category=args.category,
                max_reviews=args.max_reviews_per_user,
                store=True,
            )
        except Exception as exc:
            failure_count += 1
            failures.append({"user_id": user_id, "error": str(exc)})
            log_persona_generation(f"Persona generation failed: user_id={user_id}, error={exc}")
            continue
        success_count += 1
        review_count_available = int(result.get("review_count_available") or len(result["source_review_ids"]))
        review_count_used = int(result.get("review_count_used") or len(result["source_review_ids"]))
        total_review_count_available += review_count_available
        total_review_count_used += review_count_used
        user_review_counts.append(
            {
                "user_id": user_id,
                "review_count_available": review_count_available,
                "review_count_used": review_count_used,
                "source_review_ids": result["source_review_ids"],
            }
        )
        summary = {
            "user_id": user_id,
            "source_review_count": len(result["source_review_ids"]),
            "review_count_available": review_count_available,
            "review_count_used": review_count_used,
        }
        log_persona_generation(f"Persona generation succeeded: {summary}")
        print(summary)
    log_persona_generation(
        f"Persona regeneration complete: succeeded={success_count}, failed={failure_count}, total={len(user_ids)}"
    )
    result_payload = {
        "category": args.category,
        "limit": args.limit,
        "max_reviews_per_user": args.max_reviews_per_user,
        "model_name": generator.settings.groq_model,
        "prompt_version": generator.settings.persona_prompt_version,
        "users_considered": len(user_ids),
        "personas_generated": success_count,
        "personas_upserted": success_count,
        "review_count_available": total_review_count_available,
        "review_count_used": total_review_count_used,
        "user_review_counts": user_review_counts,
        "skipped_users": 0,
        "failed_users": failure_count,
        "failure_reasons": failures,
        "dry_run": False,
    }
    summary = build_run_summary(
        category=args.category,
        mode="upsert",
        args=vars(args),
        result=result_payload,
    )
    summary_path = save_run_summary(
        args.output_dir,
        args.category,
        "upsert",
        summary,
        timestamp=summary["timestamp"],
    )
    log_persona_generation(f"Run summary saved: {summary_path}")


if __name__ == "__main__":
    main()
