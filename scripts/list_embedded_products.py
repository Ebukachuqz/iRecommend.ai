from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from scripts.check_category_readiness import fetch_category_products, chunked


PAGE_SIZE = 1000
IN_FILTER_CHUNK = 500


def fetch_product_embeddings(client: Any, parent_asins: list[str]) -> list[dict[str, Any]]:
    if not parent_asins:
        return []
    rows: list[dict[str, Any]] = []
    for asin_chunk in chunked(parent_asins, IN_FILTER_CHUNK):
        start = 0
        while True:
            end = start + PAGE_SIZE - 1
            response = (
                client.table("product_embeddings")
                .select("parent_asin,embedding_model,created_at")
                .in_("parent_asin", asin_chunk)
                .range(start, end)
                .execute()
            )
            batch = list(response.data or [])
            rows.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            start += PAGE_SIZE
    return rows


def fetch_metadata_brief(client: Any, parent_asins: list[str]) -> dict[str, dict[str, Any]]:
    if not parent_asins:
        return {}
    response = (
        client.table("amazon_product_metadata")
        .select("parent_asin,title,category,main_category")
        .in_("parent_asin", list(dict.fromkeys(parent_asins)))
        .execute()
    )
    return {str(row["parent_asin"]): row for row in response.data or []}


def list_embedded_products(client: Any, category: str, limit: int) -> list[dict[str, Any]]:
    products = fetch_category_products(client, category)
    parent_asins = sorted({str(row["parent_asin"]) for row in products})
    embeddings = fetch_product_embeddings(client, parent_asins)
    embeddings = sorted(embeddings, key=lambda row: str(row.get("created_at") or ""), reverse=True)
    if limit and limit > 0:
        embeddings = embeddings[:limit]
    metadata = fetch_metadata_brief(client, [str(row.get("parent_asin") or "") for row in embeddings])
    rows: list[dict[str, Any]] = []
    for row in embeddings:
        parent_asin = str(row.get("parent_asin") or "")
        meta = metadata.get(parent_asin, {})
        rows.append(
            {
                "parent_asin": parent_asin,
                "title": meta.get("title") or "",
                "category": meta.get("category") or "",
                "main_category": meta.get("main_category") or "",
                "embedding_model": row.get("embedding_model"),
                "created_at": row.get("created_at"),
            }
        )
    return rows


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="List embedded products for a category.")
    parser.add_argument("--category", default=settings.default_category)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    client = get_supabase_client()
    rows = list_embedded_products(client, args.category, args.limit)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
