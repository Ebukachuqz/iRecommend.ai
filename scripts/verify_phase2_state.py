from __future__ import annotations

from collections import Counter
from typing import Any

from src.db.supabase_client import get_supabase_client


PAGE_SIZE = 1000


def can_select(client: Any, table_name: str, columns: str) -> tuple[bool, str | None]:
    try:
        client.table(table_name).select(columns).limit(1).execute()
    except Exception as exc:
        return False, str(exc)
    return True, None


def require_selectable(client: Any, table_name: str, columns: str, checks: list[str]) -> None:
    ok, error = can_select(client, table_name, columns)
    if ok:
        checks.append(f"OK: {table_name} exposes {columns}")
        return
    raise RuntimeError(f"{table_name} is missing required columns {columns}: {error}")


def require_not_selectable(client: Any, table_name: str, columns: str, checks: list[str]) -> None:
    ok, _error = can_select(client, table_name, columns)
    if not ok:
        checks.append(f"OK: {table_name} does not expose {columns}")
        return
    raise RuntimeError(f"{table_name} unexpectedly exposes {columns}")


def fetch_task_split_counts(client: Any) -> Counter[str]:
    counts: Counter[str] = Counter()
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = client.table("amazon_reviews").select("task_split").range(start, end).execute()
        rows = list(response.data or [])
        counts.update(str(row.get("task_split") or "NULL") for row in rows)
        if len(rows) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return counts


def fetch_one_persona(client: Any) -> dict[str, Any] | None:
    response = (
        client.table("user_personas")
        .select("user_id,category,source_review_ids")
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def verify_persona_sources(client: Any, checks: list[str]) -> None:
    persona = fetch_one_persona(client)
    if not persona:
        checks.append("SKIP: no user_personas rows available for source_review_ids check")
        return

    source_review_ids = list(persona.get("source_review_ids") or [])
    if not source_review_ids:
        checks.append("SKIP: sampled persona has no source_review_ids")
        return

    response = (
        client.table("amazon_reviews")
        .select("review_id,task_split")
        .in_("review_id", source_review_ids)
        .execute()
    )
    split_by_review_id = {row["review_id"]: row.get("task_split") for row in response.data or []}
    missing = [review_id for review_id in source_review_ids if review_id not in split_by_review_id]
    leaked = {
        review_id: split
        for review_id, split in split_by_review_id.items()
        if split != "persona_train"
    }
    if missing or leaked:
        raise RuntimeError(
            "Persona source_review_ids check failed: "
            f"missing={missing}, non_persona_train={leaked}"
        )

    checks.append(
        "OK: sampled persona source_review_ids all resolve to task_split='persona_train'"
    )


def main() -> None:
    client = get_supabase_client()
    checks: list[str] = []

    require_selectable(client, "amazon_reviews", "task_split", checks)
    require_not_selectable(client, "amazon_reviews", "category", checks)
    require_selectable(
        client,
        "user_personas",
        "category,review_count,average_rating,source_review_ids,persona_version,model_name,prompt_version",
        checks,
    )

    counts = fetch_task_split_counts(client)
    verify_persona_sources(client, checks)

    for check in checks:
        print(check)
    print({"task_split_counts": dict(sorted(counts.items()))})


if __name__ == "__main__":
    main()
