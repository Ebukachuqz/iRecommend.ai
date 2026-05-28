import argparse
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from src.personas.generator import PersonaGenerator, log_persona_generation
from src.utils.run_summary import build_run_summary, save_run_summary

PAGE_SIZE = 1000
IN_FILTER_CHUNK = 500


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_category_parent_asins(category: str, client: Any) -> list[str]:
    parent_asins: set[str] = set()
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = (
            client.table("amazon_product_metadata")
            .select("parent_asin")
            .eq("category", category)
            .range(start, end)
            .execute()
        )
        batch = list(response.data or [])
        parent_asins.update(str(row["parent_asin"]) for row in batch if row.get("parent_asin"))
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return sorted(parent_asins)


def fetch_user_ids(category: str, client: Any | None = None) -> list[str]:
    client = client or get_supabase_client()
    category_parent_asins = fetch_category_parent_asins(category, client)
    if not category_parent_asins:
        return []
    user_ids: set[str] = set()
    for asin_chunk in chunked(category_parent_asins, IN_FILTER_CHUNK):
        start = 0
        while True:
            end = start + PAGE_SIZE - 1
            response = (
                client.table("amazon_reviews")
                .select("user_id")
                .eq("task_split", "persona_train")
                .in_("parent_asin", asin_chunk)
                .range(start, end)
                .execute()
            )
            batch = list(response.data or [])
            user_ids.update(str(row["user_id"]) for row in batch if row.get("user_id"))
            if len(batch) < PAGE_SIZE:
                break
            start += PAGE_SIZE
    return sorted(user_ids)


def fetch_existing_persona_user_ids(category: str, client: Any | None = None) -> set[str]:
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
    return user_ids


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Generate personas from persona_train reviews.")
    parser.add_argument("--category", default=settings.default_category)
    parser.add_argument("--user-id", action="append", dest="user_ids")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-reviews-per-user", type=int, default=10)
    parser.add_argument("--force", action="store_true", help="Regenerate personas even if they already exist.")
    parser.add_argument("--output-dir", default="outputs/personas")
    args = parser.parse_args()

    client = get_supabase_client()
    user_ids = args.user_ids or fetch_user_ids(args.category, client=client)
    existing_user_ids = set() if args.force else fetch_existing_persona_user_ids(args.category, client=client)
    users_to_process = [user_id for user_id in user_ids if user_id not in existing_user_ids]
    if args.limit:
        users_to_process = users_to_process[: args.limit]

    log_persona_generation(
        "Starting persona generation: "
        f"category={args.category}, candidates={len(user_ids)}, to_process={len(users_to_process)}, "
        f"existing_skipped={len(user_ids) - len(users_to_process)}, limit={args.limit}, force={args.force}"
    )
    generator = PersonaGenerator()
    success_count = 0
    failure_count = 0
    skipped_existing = len(user_ids) - len(users_to_process)
    total_review_count_available = 0
    total_review_count_used = 0
    user_review_counts: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for index, user_id in enumerate(users_to_process, start=1):
        log_persona_generation(f"Processing user {index}/{len(users_to_process)}: user_id={user_id}")
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
        log_persona_generation(f"Persona generated: {summary}")
        print(summary)
    log_persona_generation(
        "Persona generation complete: "
        f"succeeded={success_count}, failed={failure_count}, skipped_existing={skipped_existing}, "
        f"total_candidates={len(user_ids)}, processed={len(users_to_process)}"
    )
    result_payload = {
        "category": args.category,
        "limit": args.limit,
        "force": args.force,
        "max_reviews_per_user": args.max_reviews_per_user,
        "model_name": generator.settings.groq_model,
        "prompt_version": generator.settings.persona_prompt_version,
        "users_considered": len(users_to_process),
        "users_in_category": len(user_ids),
        "personas_generated": success_count,
        "personas_upserted": success_count,
        "review_count_available": total_review_count_available,
        "review_count_used": total_review_count_used,
        "user_review_counts": user_review_counts,
        "skipped_users": skipped_existing,
        "skipped_existing": skipped_existing,
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
