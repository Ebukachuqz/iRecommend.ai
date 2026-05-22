from typing import Any

from supabase import Client

from src.constants import PERSONA_TRAIN_SPLIT


def fetch_persona(client: Client, user_id: str, category: str) -> dict[str, Any] | None:
    response = (
        client.table("user_personas")
        .select("*")
        .eq("user_id", user_id)
        .eq("category", category)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def fetch_product(client: Client, parent_asin: str) -> dict[str, Any] | None:
    response = (
        client.table("amazon_product_metadata")
        .select("*")
        .eq("parent_asin", parent_asin)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def fetch_persona_train_reviews(client: Client, user_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("amazon_reviews")
        .select("*")
        .eq("user_id", user_id)
        .eq("task_split", PERSONA_TRAIN_SPLIT)
        .eq("used_for_persona", True)
        .order("timestamp", desc=False)
        .execute()
    )
    return list(response.data or [])
