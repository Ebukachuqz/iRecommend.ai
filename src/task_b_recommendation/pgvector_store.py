from __future__ import annotations

import random
import time
from typing import Any

import httpx
from supabase import Client

from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.vector_store import VectorStore


def _is_transient_network_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException)):
        return True
    # Fallback: Windows can surface some resets as OSError with winerror 10054.
    winerror = getattr(exc, "winerror", None)
    if winerror == 10054:
        return True
    return False


def _execute_with_retries(builder: Any, *, max_attempts: int = 5) -> Any:
    attempt = 0
    delay_s = 0.5
    while True:
        attempt += 1
        try:
            return builder.execute()
        except Exception as exc:  # noqa: BLE001 - narrow by predicate
            if attempt >= max_attempts or not _is_transient_network_error(exc):
                raise
            # Exponential backoff with small jitter. Keep it simple: this is for transient resets.
            jitter = random.random() * 0.25
            time.sleep(delay_s + jitter)
            delay_s = min(delay_s * 2.0, 8.0)


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
        builder = self.client.table("product_embeddings").upsert(
            {
                "parent_asin": parent_asin,
                "embedding": embedding,
                "embedding_model": embedding_model,
                "product_text": product_text,
            },
            on_conflict="parent_asin",
        )
        _execute_with_retries(builder)

    def search_products(
        self,
        query_embedding: list[float],
        limit: int,
        exclude_parent_asins: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        builder = self.client.rpc(
            "match_product_embeddings",
            {
                "query_embedding": query_embedding,
                "match_count": limit,
                "exclude_parent_asins": list(exclude_parent_asins or []),
            },
        )
        response = _execute_with_retries(builder)
        return list(response.data or [])

    def get_product_embedding(self, parent_asin: str) -> dict[str, Any] | None:
        builder = (
            self.client.table("product_embeddings")
            .select("*")
            .eq("parent_asin", parent_asin)
            .limit(1)
        )
        response = _execute_with_retries(builder)
        return response.data[0] if response.data else None

    def search_similar_users(
        self,
        query_embedding: list[float],
        category: str,
        limit: int,
        exclude_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        builder = self.client.rpc(
            "match_user_taste_vectors",
            {
                "query_embedding": query_embedding,
                "target_category": category,
                "match_count": limit,
                "exclude_user_id": exclude_user_id,
            },
        )
        response = _execute_with_retries(builder)
        return list(response.data or [])
