from __future__ import annotations

from typing import Any

from supabase import Client

from src.db.queries import fetch_reviewed_parent_asins
from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.embeddings import embed_text
from src.task_b_recommendation.pgvector_store import SupabasePgVectorStore
from src.task_b_recommendation.schema import RecommendationCandidate, RecommendationIntent
from src.task_b_recommendation.taste_vector import fetch_user_taste_vector, parse_embedding
from src.task_b_recommendation.vector_store import VectorStore


def fetch_products_by_parent_asins(parent_asins: list[str], client: Client | None = None) -> dict[str, dict[str, Any]]:
    client = client or get_supabase_client()
    if not parent_asins:
        return {}
    response = (
        client.table("amazon_product_metadata")
        .select("*")
        .in_("parent_asin", list(dict.fromkeys(parent_asins)))
        .execute()
    )
    return {row["parent_asin"]: row for row in response.data or []}


def fetch_quality_fallback_products(
    user_id: str | None,
    limit: int,
    client: Client | None = None,
) -> list[RecommendationCandidate]:
    client = client or get_supabase_client()
    reviewed = fetch_reviewed_parent_asins(user_id, client=client) if user_id else set()
    response = (
        client.table("amazon_product_metadata")
        .select("*")
        .order("average_rating", desc=True)
        .order("rating_number", desc=True)
        .limit(limit * 3)
        .execute()
    )
    candidates: list[RecommendationCandidate] = []
    for product in response.data or []:
        parent_asin = product.get("parent_asin")
        if not parent_asin or parent_asin in reviewed:
            continue
        candidates.append(
            RecommendationCandidate(
                parent_asin=parent_asin,
                title=product.get("title"),
                product=product,
                semantic_similarity=0.0,
                retrieval_source="quality_fallback",
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def add_vector_matches(
    candidates_by_asin: dict[str, RecommendationCandidate],
    matches: list[dict[str, Any]],
    retrieval_source: str,
    reviewed: set[str],
    client: Client,
) -> None:
    products = fetch_products_by_parent_asins([match["parent_asin"] for match in matches], client=client)
    for match in matches:
        parent_asin = match.get("parent_asin")
        product = products.get(parent_asin)
        if not parent_asin or parent_asin in reviewed or not product:
            continue

        similarity = float(match.get("similarity") or 0)
        existing = candidates_by_asin.get(parent_asin)
        if existing:
            existing.semantic_similarity = max(existing.semantic_similarity, similarity)
            continue

        candidates_by_asin[parent_asin] = RecommendationCandidate(
            parent_asin=parent_asin,
            title=product.get("title"),
            product=product,
            semantic_similarity=similarity,
            retrieval_source=retrieval_source,
        )


def retrieve_candidates(
    user_id: str | None,
    category: str,
    intent: RecommendationIntent,
    limit: int = 50,
    client: Client | None = None,
    vector_store: VectorStore | None = None,
) -> list[RecommendationCandidate]:
    client = client or get_supabase_client()
    reviewed = fetch_reviewed_parent_asins(user_id, client=client) if user_id else set()
    vector_store = vector_store or SupabasePgVectorStore(client=client)
    vector_row = fetch_user_taste_vector(user_id, category, client=client) if user_id else None
    candidates_by_asin: dict[str, RecommendationCandidate] = {}

    if vector_row and vector_row.get("embedding"):
        try:
            matches = vector_store.search_products(
                parse_embedding(vector_row["embedding"]),
                limit=limit * 2,
                exclude_parent_asins=reviewed,
            )
        except Exception:
            matches = []
        add_vector_matches(candidates_by_asin, matches, "taste_vector", reviewed, client)

    retrieval_query = intent.retrieval_query.strip()
    if retrieval_query:
        try:
            matches = vector_store.search_products(
                embed_text(retrieval_query),
                limit=limit * 2,
                exclude_parent_asins=reviewed,
            )
        except Exception:
            matches = []
        add_vector_matches(candidates_by_asin, matches, "request_query", reviewed, client)

    candidates = list(candidates_by_asin.values())
    if len(candidates) < limit:
        seen = {candidate.parent_asin for candidate in candidates}
        fallback = fetch_quality_fallback_products(user_id, limit=limit, client=client)
        for candidate in fallback:
            if candidate.parent_asin in seen:
                continue
            candidates.append(candidate)
            seen.add(candidate.parent_asin)
            if len(candidates) >= limit:
                break

    return candidates[:limit]
