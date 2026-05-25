from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from src.constants import PERSONA_TRAIN_SPLIT, TASK_A_HOLDOUT_SPLIT, TASK_B_HOLDOUT_SPLIT
from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.taste_vector import product_matches_category


PAGE_SIZE = 1000
IN_FILTER_CHUNK = 500


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def page_query(query: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = query.range(start, end).execute()
        batch = list(response.data or [])
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def fetch_category_products(category: str, client: Any | None = None) -> dict[str, dict[str, Any]]:
    client = client or get_supabase_client()
    rows = page_query(client.table("amazon_product_metadata").select("*"))
    return {
        str(row["parent_asin"]): row
        for row in rows
        if row.get("parent_asin") and product_matches_category(row, category)
    }


def fetch_user_personas(category: str, client: Any | None = None) -> dict[str, dict[str, Any]]:
    client = client or get_supabase_client()
    rows = page_query(client.table("user_personas").select("*").eq("category", category))
    return {str(row["user_id"]): row for row in rows if row.get("user_id")}


def fetch_user_taste_vectors(category: str, client: Any | None = None) -> set[str]:
    client = client or get_supabase_client()
    rows = page_query(client.table("user_taste_vectors").select("user_id").eq("category", category))
    return {str(row["user_id"]) for row in rows if row.get("user_id")}


def fetch_reviews_for_products(
    parent_asins: list[str],
    client: Any | None = None,
    task_split: str | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    client = client or get_supabase_client()
    if not parent_asins:
        return []
    rows: list[dict[str, Any]] = []
    for asin_chunk in chunked(parent_asins, IN_FILTER_CHUNK):
        query = client.table("amazon_reviews").select("*").in_("parent_asin", asin_chunk)
        if task_split:
            query = query.eq("task_split", task_split)
        if user_id:
            query = query.eq("user_id", user_id)
        rows.extend(page_query(query))
    return rows


def sorted_examples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("user_id") or ""),
            str(row.get("timestamp") or ""),
            str(row.get("review_id") or ""),
        ),
    )


def select_task_a_examples(
    category: str,
    limit: int,
    user_id: str | None = None,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    products = fetch_category_products(category, client=client)
    personas = fetch_user_personas(category, client=client)
    reviews = fetch_reviews_for_products(
        sorted(products),
        client=client,
        task_split=TASK_A_HOLDOUT_SPLIT,
        user_id=user_id,
    )
    examples: list[dict[str, Any]] = []
    for review in sorted_examples(reviews):
        review_user_id = str(review.get("user_id") or "")
        product = products.get(str(review.get("parent_asin") or ""))
        persona = personas.get(review_user_id)
        if not product or not persona:
            continue
        examples.append({"review": review, "product": product, "persona": persona})
        if limit and len(examples) >= limit:
            break
    return examples


def select_task_b_examples(
    category: str,
    limit: int,
    user_id: str | None = None,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    products = fetch_category_products(category, client=client)
    personas = fetch_user_personas(category, client=client)
    taste_vector_users = fetch_user_taste_vectors(category, client=client)
    reviews = fetch_reviews_for_products(
        sorted(products),
        client=client,
        task_split=TASK_B_HOLDOUT_SPLIT,
        user_id=user_id,
    )
    examples: list[dict[str, Any]] = []
    for review in sorted_examples(reviews):
        review_user_id = str(review.get("user_id") or "")
        rating = float(review.get("rating") or 0)
        product = products.get(str(review.get("parent_asin") or ""))
        if rating < 4 or not product or review_user_id not in personas or review_user_id not in taste_vector_users:
            continue
        examples.append({"review": review, "product": product, "persona": personas[review_user_id]})
        if limit and len(examples) >= limit:
            break
    return examples


def user_average_ratings_from_persona_train(category: str, client: Any | None = None) -> dict[str, float]:
    products = fetch_category_products(category, client=client)
    reviews = fetch_reviews_for_products(sorted(products), client=client, task_split=PERSONA_TRAIN_SPLIT)
    ratings_by_user: dict[str, list[float]] = defaultdict(list)
    for review in reviews:
        if review.get("rating") is None or not review.get("user_id"):
            continue
        ratings_by_user[str(review["user_id"])].append(float(review["rating"]))
    return {user_id: mean(ratings) for user_id, ratings in ratings_by_user.items() if ratings}


def persona_train_parent_asins(user_id: str, category: str, client: Any | None = None) -> set[str]:
    products = fetch_category_products(category, client=client)
    reviews = fetch_reviews_for_products(
        sorted(products),
        client=client,
        task_split=PERSONA_TRAIN_SPLIT,
        user_id=user_id,
    )
    return {str(review["parent_asin"]) for review in reviews if review.get("parent_asin")}


def popularity_baseline_recommendations(
    user_id: str,
    category: str,
    k: int,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    products = fetch_category_products(category, client=client)
    excluded = persona_train_parent_asins(user_id, category, client=client)
    candidates = [product for asin, product in products.items() if asin not in excluded]
    candidates.sort(
        key=lambda product: (
            -float(product.get("average_rating") or 0),
            -int(product.get("rating_number") or 0),
            str(product.get("parent_asin") or ""),
        )
    )
    return candidates[:k]
