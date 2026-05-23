from typing import Any

from supabase import Client

from src.constants import PERSONA_TRAIN_SPLIT, TASK_A_HOLDOUT_SPLIT
from src.db.supabase_client import get_supabase_client


def resolve_client(client: Client | None = None) -> Client:
    return client or get_supabase_client()


def fetch_persona(user_id: str, category: str, client: Client | None = None) -> dict[str, Any] | None:
    client = resolve_client(client)
    response = (
        client.table("user_personas")
        .select("*")
        .eq("user_id", user_id)
        .eq("category", category)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def fetch_user_persona_summaries(
    category: str,
    limit: int = 20,
    client: Client | None = None,
) -> list[dict[str, Any]]:
    client = resolve_client(client)
    response = (
        client.table("user_personas")
        .select("user_id, category, review_count, average_rating, persona_version, persona")
        .eq("category", category)
        .limit(limit)
        .execute()
    )
    return list(response.data or [])


def check_table_reachable(table_name: str, client: Client | None = None) -> bool:
    client = resolve_client(client)
    client.table(table_name).select("*").limit(1).execute()
    return True


def fetch_product(parent_asin: str, client: Client | None = None) -> dict[str, Any] | None:
    client = resolve_client(client)
    response = (
        client.table("amazon_product_metadata")
        .select("*")
        .eq("parent_asin", parent_asin)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def fetch_persona_train_reviews(user_id: str, client: Client | None = None) -> list[dict[str, Any]]:
    client = resolve_client(client)
    response = (
        client.table("amazon_reviews")
        .select("*")
        .eq("user_id", user_id)
        .eq("task_split", PERSONA_TRAIN_SPLIT)
        .order("timestamp", desc=False)
        .execute()
    )
    return list(response.data or [])


def fetch_task_a_holdout_review(user_id: str, client: Client | None = None) -> dict[str, Any] | None:
    client = resolve_client(client)
    response = (
        client.table("amazon_reviews")
        .select("*")
        .eq("user_id", user_id)
        .eq("task_split", TASK_A_HOLDOUT_SPLIT)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def fetch_reviewed_parent_asins(user_id: str, client: Client | None = None, page_size: int = 1000) -> set[str]:
    client = resolve_client(client)
    parent_asins: set[str] = set()
    start = 0
    while True:
        end = start + page_size - 1
        response = (
            client.table("amazon_reviews")
            .select("parent_asin")
            .eq("user_id", user_id)
            .range(start, end)
            .execute()
        )
        rows = list(response.data or [])
        parent_asins.update(str(row["parent_asin"]) for row in rows if row.get("parent_asin"))
        if len(rows) < page_size:
            break
        start += page_size
    return parent_asins


def fetch_unseen_products(
    user_id: str,
    limit: int = 20,
    client: Client | None = None,
    page_size: int = 1000,
    max_pages: int = 10,
) -> list[dict[str, Any]]:
    client = resolve_client(client)
    reviewed_parent_asins = fetch_reviewed_parent_asins(user_id, client=client)
    unseen: list[dict[str, Any]] = []
    start = 0
    pages = 0
    while len(unseen) < limit and pages < max_pages:
        end = start + page_size - 1
        response = client.table("amazon_product_metadata").select("*").range(start, end).execute()
        rows = list(response.data or [])
        for product in rows:
            parent_asin = product.get("parent_asin")
            if parent_asin and parent_asin not in reviewed_parent_asins:
                unseen.append(product)
                if len(unseen) >= limit:
                    break
        if len(rows) < page_size:
            break
        pages += 1
        start += page_size
    return unseen


def store_simulation_result(payload: dict[str, Any], client: Client | None = None) -> dict[str, Any]:
    client = resolve_client(client)
    response = client.table("simulation_results").insert(payload).execute()
    return response.data[0] if response.data else payload
