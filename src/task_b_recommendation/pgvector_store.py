from __future__ import annotations

from typing import Any

from supabase import Client

from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.vector_store import VectorStore


class SupabasePgVectorStore(VectorStore):
    def __init__(self, client: Client | None = None) -> None:
        self.client = client or get_supabase_client()

    def upsert_product_embedding(
        self,
        parent_asin: str,
        embedding: list[float],
        embedding_model: str,
        product_text: str,
    ) -> None:
        self.client.table("product_embeddings").upsert(
            {
                "parent_asin": parent_asin,
                "embedding": embedding,
                "embedding_model": embedding_model,
                "product_text": product_text,
            },
            on_conflict="parent_asin",
        ).execute()

    def search_products(
        self,
        query_embedding: list[float],
        limit: int,
        exclude_parent_asins: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        response = self.client.rpc(
            "match_product_embeddings",
            {
                "query_embedding": query_embedding,
                "match_count": limit,
                "exclude_parent_asins": list(exclude_parent_asins or []),
            },
        ).execute()
        return list(response.data or [])

    def get_product_embedding(self, parent_asin: str) -> dict[str, Any] | None:
        response = (
            self.client.table("product_embeddings")
            .select("*")
            .eq("parent_asin", parent_asin)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
