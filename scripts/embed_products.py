from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.embeddings import DEFAULT_EMBEDDING_MODEL, embed_texts
from src.task_b_recommendation.pgvector_store import SupabasePgVectorStore
from src.task_b_recommendation.product_text import build_product_text, is_embeddable


def fetch_products(limit: int | None, page_size: int, category: str | None = None) -> list[dict[str, Any]]:
    client = get_supabase_client()
    products: list[dict[str, Any]] = []
    start = 0
    while limit is None or len(products) < limit:
        end = start + page_size - 1
        query = client.table("amazon_product_metadata").select("*")
        if category:
            query = query.eq("category", category)
        response = query.range(start, end).execute()
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


def build_embedding_inputs(
    products: list[dict[str, Any]],
    existing_ids: set[str] | None = None,
    force_reembed: bool = False,
) -> tuple[list[dict[str, Any]], list[str], int]:
    existing_ids = existing_ids or set()
    pending_products: list[dict[str, Any]] = []
    product_texts: list[str] = []
    skipped = 0
    for product in products:
        parent_asin = product.get("parent_asin")
        if not parent_asin:
            skipped += 1
            continue
        if not force_reembed and parent_asin in existing_ids:
            skipped += 1
            continue
        if not is_embeddable(product):
            skipped += 1
            continue
        product_text = build_product_text(product)
        if not product_text.strip():
            skipped += 1
            continue
        pending_products.append(product)
        product_texts.append(product_text)
    return pending_products, product_texts, skipped


def embed_product_batch(
    products: list[dict[str, Any]],
    store: SupabasePgVectorStore,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    force_reembed: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    existing = set() if force_reembed else existing_embedding_ids([product.get("parent_asin") for product in products if product.get("parent_asin")])
    pending, texts, skipped = build_embedding_inputs(products, existing_ids=existing, force_reembed=force_reembed)
    if dry_run:
        return {"seen": len(products), "embedded": 0, "would_embed": len(pending), "skipped": skipped}
    if not pending:
        return {"seen": len(products), "embedded": 0, "would_embed": 0, "skipped": skipped}

    embeddings = embed_texts(texts, model_name=model_name)
    for product, product_text, embedding in zip(pending, texts, embeddings):
        store.upsert_product_embedding(product["parent_asin"], embedding, model_name, product_text)
    return {"seen": len(products), "embedded": len(pending), "would_embed": len(pending), "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed product metadata into pgvector.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--force-reembed", "--force", action="store_true", dest="force_reembed")
    parser.add_argument("--category", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    args = parser.parse_args()

    products = fetch_products(args.limit, page_size=max(args.batch_size, 100), category=args.category)
    store = SupabasePgVectorStore()
    totals = {"products_seen": len(products), "embedded": 0, "would_embed": 0, "skipped": 0, "model": args.model}
    for start in range(0, len(products), args.batch_size):
        batch = products[start : start + args.batch_size]
        result = embed_product_batch(
            batch,
            store,
            model_name=args.model,
            force_reembed=args.force_reembed,
            dry_run=args.dry_run,
        )
        totals["embedded"] += result["embedded"]
        totals["would_embed"] += result["would_embed"]
        totals["skipped"] += result["skipped"]
    print(totals)


if __name__ == "__main__":
    main()
