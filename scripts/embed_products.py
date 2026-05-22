from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.embeddings import DEFAULT_EMBEDDING_MODEL, embed_texts
from src.task_b_recommendation.pgvector_store import SupabasePgVectorStore
from src.task_b_recommendation.product_text import build_product_text


def fetch_products(limit: int | None, page_size: int) -> list[dict]:
    client = get_supabase_client()
    products: list[dict] = []
    start = 0
    while limit is None or len(products) < limit:
        end = start + page_size - 1
        response = client.table("amazon_product_metadata").select("*").range(start, end).execute()
        rows = list(response.data or [])
        remaining = None if limit is None else max(0, limit - len(products))
        if remaining == 0:
            break
        products.extend(rows[:remaining])
        if len(rows) < page_size:
            break
        start += page_size
    return products


def existing_embedding_ids(parent_asins: list[str]) -> set[str]:
    if not parent_asins:
        return set()
    client = get_supabase_client()
    response = (
        client.table("product_embeddings")
        .select("parent_asin")
        .in_("parent_asin", list(dict.fromkeys(parent_asins)))
        .execute()
    )
    return {row["parent_asin"] for row in response.data or []}


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed product metadata into pgvector.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    args = parser.parse_args()

    products = fetch_products(args.limit, page_size=max(args.batch_size, 100))
    store = SupabasePgVectorStore()
    embedded_count = 0
    for start in range(0, len(products), args.batch_size):
        batch = products[start : start + args.batch_size]
        existing = set() if args.force else existing_embedding_ids([product["parent_asin"] for product in batch])
        pending = [product for product in batch if product.get("parent_asin") and product["parent_asin"] not in existing]
        if not pending:
            continue
        texts = [build_product_text(product) for product in pending]
        embeddings = embed_texts(texts, model_name=args.model)
        for product, product_text, embedding in zip(pending, texts, embeddings):
            store.upsert_product_embedding(product["parent_asin"], embedding, args.model, product_text)
            embedded_count += 1
    print({"products_seen": len(products), "embedded": embedded_count, "model": args.model})


if __name__ == "__main__":
    main()
