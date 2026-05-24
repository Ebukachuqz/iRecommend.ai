from __future__ import annotations

from abc import ABC, abstractmethod


class VectorStore(ABC):
    @abstractmethod
    def upsert_product_embedding(
        self,
        parent_asin: str,
        embedding: list[float],
        embedding_model: str,
        product_text: str,
    ) -> None:
        pass

    @abstractmethod
    def search_products(
        self,
        query_embedding: list[float],
        limit: int,
        exclude_parent_asins: set[str] | None = None,
    ) -> list[dict]:
        pass

    @abstractmethod
    def get_product_embedding(self, parent_asin: str) -> dict | None:
        pass

    def search_similar_users(
        self,
        query_embedding: list[float],
        category: str,
        limit: int,
        exclude_user_id: str | None = None,
    ) -> list[dict]:
        return []
