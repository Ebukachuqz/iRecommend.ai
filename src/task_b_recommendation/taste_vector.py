from __future__ import annotations

from typing import Any

from supabase import Client

from src.constants import PERSONA_TRAIN_SPLIT
from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.embeddings import DEFAULT_EMBEDDING_MODEL


def parse_embedding(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, list):
        return [float(item) for item in value]
    text = str(value).strip().strip("[]")
    return [float(part) for part in text.split(",") if part.strip()]


def weighted_average(vectors: list[list[float]], weights: list[float]) -> list[float]:
    if not vectors:
        return []
    dimension = len(vectors[0])
    total_weight = sum(weights)
    if total_weight <= 0:
        return []
    return [
        sum(vector[index] * weight for vector, weight in zip(vectors, weights)) / total_weight
        for index in range(dimension)
    ]


def fetch_liked_training_reviews(user_id: str, client: Client | None = None) -> list[dict[str, Any]]:
    client = client or get_supabase_client()
    response = (
        client.table("amazon_reviews")
        .select("parent_asin,rating")
        .eq("user_id", user_id)
        .eq("task_split", PERSONA_TRAIN_SPLIT)
        .gte("rating", 4)
        .execute()
    )
    return list(response.data or [])


def fetch_product_embeddings(parent_asins: list[str], client: Client | None = None) -> dict[str, list[float]]:
    client = client or get_supabase_client()
    if not parent_asins:
        return {}
    response = (
        client.table("product_embeddings")
        .select("parent_asin,embedding")
        .in_("parent_asin", list(dict.fromkeys(parent_asins)))
        .execute()
    )
    return {
        row["parent_asin"]: parse_embedding(row.get("embedding"))
        for row in response.data or []
        if row.get("embedding") is not None
    }


def build_user_taste_vector(user_id: str, client: Client | None = None) -> tuple[list[float], list[str]]:
    reviews = fetch_liked_training_reviews(user_id, client=client)
    parent_asins = [review["parent_asin"] for review in reviews if review.get("parent_asin")]
    embeddings_by_asin = fetch_product_embeddings(parent_asins, client=client)
    vectors: list[list[float]] = []
    weights: list[float] = []
    sources: list[str] = []
    for review in reviews:
        parent_asin = review.get("parent_asin")
        embedding = embeddings_by_asin.get(parent_asin)
        if not parent_asin or not embedding:
            continue
        vectors.append(embedding)
        weights.append(max(0.0, float(review.get("rating") or 0) - 3.0))
        sources.append(parent_asin)
    return weighted_average(vectors, weights), sources


def store_user_taste_vector(
    user_id: str,
    category: str,
    embedding: list[float],
    source_parent_asins: list[str],
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    client: Client | None = None,
) -> None:
    client = client or get_supabase_client()
    client.table("user_taste_vectors").upsert(
        {
            "user_id": user_id,
            "category": category,
            "embedding": embedding,
            "embedding_model": embedding_model,
            "source_parent_asins": source_parent_asins,
        },
        on_conflict="user_id,category",
    ).execute()


def build_and_store_user_taste_vector(
    user_id: str,
    category: str,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    client: Client | None = None,
) -> tuple[list[float], list[str]]:
    embedding, sources = build_user_taste_vector(user_id, client=client)
    if embedding:
        store_user_taste_vector(user_id, category, embedding, sources, embedding_model=embedding_model, client=client)
    return embedding, sources


def fetch_user_taste_vector(user_id: str, category: str, client: Client | None = None) -> dict[str, Any] | None:
    client = client or get_supabase_client()
    response = (
        client.table("user_taste_vectors")
        .select("*")
        .eq("user_id", user_id)
        .eq("category", category)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None
