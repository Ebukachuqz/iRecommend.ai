from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from supabase import Client

from src.constants import PERSONA_TRAIN_SPLIT
from src.db.queries import fetch_reviewed_parent_asins
from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.embeddings import embed_text
from src.task_b_recommendation.pgvector_store import SupabasePgVectorStore
from src.task_b_recommendation.product_text import build_product_text
from src.task_b_recommendation.schema import RecommendationCandidate, RecommendationIntent
from src.task_b_recommendation.taste_vector import fetch_user_taste_vector, parse_embedding, product_matches_category
from src.task_b_recommendation.vector_store import VectorStore


@dataclass
class CandidateRetrievalResult:
    candidates: list[RecommendationCandidate]
    source_counts: dict[str, int] = field(default_factory=dict)


def has_category_signal(product: dict[str, Any]) -> bool:
    return any(product.get(key) not in (None, "", [], {}) for key in ("category", "main_category", "categories"))


def product_matches_requested_category(product: dict[str, Any], category: str | None) -> bool:
    if not category or not has_category_signal(product):
        return True
    return product_matches_category(product, category)


def effective_category(category: str, intent: RecommendationIntent) -> str | None:
    return intent.category_filter or category


def collect_persona_terms(persona: dict[str, Any] | None, intent: RecommendationIntent) -> tuple[list[str], list[str]]:
    persona = persona or {}
    preferences = persona.get("preferences", {}) if isinstance(persona.get("preferences"), dict) else {}
    positive: list[str] = []
    negative: list[str] = []
    for key in ("liked_attributes", "liked_product_types", "what_they_value"):
        value = preferences.get(key) or []
        positive.extend(str(item) for item in value if str(item).strip())
    positive.extend(intent.required_attributes)
    for key in ("disliked_attributes", "disliked_product_types", "common_complaints"):
        value = preferences.get(key) or []
        negative.extend(str(item) for item in value if str(item).strip())
    negative.extend(intent.excluded_attributes)
    return list(dict.fromkeys(positive)), list(dict.fromkeys(negative))


def text_contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms if term)


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
    return {row["parent_asin"]: row for row in response.data or [] if row.get("parent_asin")}


def merge_candidate(
    candidates_by_asin: dict[str, RecommendationCandidate],
    product: dict[str, Any],
    source: str,
    semantic_similarity: float = 0.0,
    collaborative_similarity: float | None = None,
    evidence: list[str] | None = None,
    warnings: list[str] | None = None,
) -> bool:
    parent_asin = product.get("parent_asin")
    if not parent_asin:
        return False

    evidence = evidence or []
    warnings = warnings or []
    existing = candidates_by_asin.get(parent_asin)
    if existing:
        if source not in existing.retrieval_sources:
            existing.retrieval_sources.append(source)
        existing.semantic_similarity = max(existing.semantic_similarity, semantic_similarity)
        if collaborative_similarity is not None:
            existing.collaborative_similarity = max(existing.collaborative_similarity or 0.0, collaborative_similarity)
        for item in evidence:
            if item not in existing.source_evidence:
                existing.source_evidence.append(item)
        for item in warnings:
            if item not in existing.warnings:
                existing.warnings.append(item)
        return False

    candidates_by_asin[parent_asin] = RecommendationCandidate(
        parent_asin=parent_asin,
        title=product.get("title"),
        product=product,
        semantic_similarity=semantic_similarity,
        collaborative_similarity=collaborative_similarity,
        retrieval_source=source,
        retrieval_sources=[source],
        source_evidence=evidence,
        warnings=warnings,
    )
    return True


def add_vector_matches(
    candidates_by_asin: dict[str, RecommendationCandidate],
    matches: list[dict[str, Any]],
    retrieval_source: str,
    reviewed: set[str],
    client: Client,
    category: str | None = None,
    source_counts: dict[str, int] | None = None,
) -> None:
    products = fetch_products_by_parent_asins([match["parent_asin"] for match in matches if match.get("parent_asin")], client=client)
    for match in matches:
        parent_asin = match.get("parent_asin")
        product = products.get(parent_asin)
        if not parent_asin or parent_asin in reviewed or not product:
            continue
        if not product_matches_requested_category(product, category):
            continue
        similarity = float(match.get("similarity") or 0)
        merge_candidate(
            candidates_by_asin,
            product,
            retrieval_source,
            semantic_similarity=similarity,
            evidence=[f"{retrieval_source} similarity {similarity:.2f}"],
        )
        if source_counts is not None:
            source_counts[retrieval_source] = source_counts.get(retrieval_source, 0) + 1


def fetch_quality_fallback_products(
    user_id: str | None,
    limit: int,
    client: Client | None = None,
    category: str | None = None,
    intent: RecommendationIntent | None = None,
    reviewed: set[str] | None = None,
) -> list[RecommendationCandidate]:
    client = client or get_supabase_client()
    reviewed = reviewed if reviewed is not None else (fetch_reviewed_parent_asins(user_id, client=client) if user_id else set())
    query = client.table("amazon_product_metadata").select("*")
    if intent and intent.price_max is not None and hasattr(query, "lte"):
        query = query.lte("price", intent.price_max)
    if hasattr(query, "gte"):
        query = query.gte("average_rating", 4.0)
    response = (
        query.order("average_rating", desc=True)
        .order("rating_number", desc=True)
        .limit(limit * 3)
        .execute()
    )
    candidates: list[RecommendationCandidate] = []
    for product in response.data or []:
        parent_asin = product.get("parent_asin")
        if not parent_asin or parent_asin in reviewed:
            continue
        if not product_matches_requested_category(product, category):
            continue
        if product.get("rating_number") is not None and int(product.get("rating_number") or 0) < 20:
            continue
        candidates.append(
            RecommendationCandidate(
                parent_asin=parent_asin,
                title=product.get("title"),
                product=product,
                semantic_similarity=0.0,
                retrieval_source="quality_fallback",
                retrieval_sources=["quality_fallback"],
                source_evidence=["high rating/popularity fallback"],
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def retrieve_collaborative_candidates(
    user_id: str,
    category: str,
    taste_vector: list[float],
    reviewed: set[str],
    limit: int,
    client: Client,
    vector_store: VectorStore,
) -> list[tuple[dict[str, Any], float, list[str]]]:
    similar_users = vector_store.search_similar_users(
        taste_vector,
        category=category,
        limit=5,
        exclude_user_id=user_id,
    )
    similar_user_ids = [row["user_id"] for row in similar_users if row.get("user_id")]
    if not similar_user_ids:
        return []
    similarity_by_user = {row["user_id"]: float(row.get("similarity") or 0) for row in similar_users if row.get("user_id")}
    response = (
        client.table("amazon_reviews")
        .select("user_id,parent_asin,rating")
        .in_("user_id", similar_user_ids)
        .eq("task_split", PERSONA_TRAIN_SPLIT)
        .gte("rating", 4)
        .limit(limit * 5)
        .execute()
    )
    asin_similarity: dict[str, float] = {}
    asin_evidence: dict[str, list[str]] = {}
    for row in response.data or []:
        parent_asin = row.get("parent_asin")
        similar_user_id = row.get("user_id")
        if not parent_asin or parent_asin in reviewed:
            continue
        similarity = similarity_by_user.get(similar_user_id, 0.0)
        asin_similarity[parent_asin] = max(asin_similarity.get(parent_asin, 0.0), similarity)
        asin_evidence.setdefault(parent_asin, []).append(f"liked by similar user {similar_user_id}")
    products = fetch_products_by_parent_asins(list(asin_similarity), client=client)
    results: list[tuple[dict[str, Any], float, list[str]]] = []
    for parent_asin, similarity in sorted(asin_similarity.items(), key=lambda item: item[1], reverse=True):
        product = products.get(parent_asin)
        if product and product_matches_requested_category(product, category):
            results.append((product, similarity, asin_evidence.get(parent_asin, [])))
        if len(results) >= limit:
            break
    return results


def retrieve_attribute_match_candidates(
    persona: dict[str, Any] | None,
    intent: RecommendationIntent,
    reviewed: set[str],
    limit: int,
    client: Client,
    category: str | None = None,
) -> list[tuple[dict[str, Any], list[str], list[str]]]:
    positive_terms, negative_terms = collect_persona_terms(persona, intent)
    if not positive_terms:
        return []
    matched_embeddings: dict[str, dict[str, Any]] = {}
    for term in positive_terms[:6]:
        response = (
            client.table("product_embeddings")
            .select("parent_asin,product_text")
            .ilike("product_text", f"%{term}%")
            .limit(limit * 2)
            .execute()
        )
        for row in response.data or []:
            parent_asin = row.get("parent_asin")
            if not parent_asin or parent_asin in reviewed:
                continue
            matched_embeddings.setdefault(parent_asin, row)
    products = fetch_products_by_parent_asins(list(matched_embeddings), client=client)
    results: list[tuple[dict[str, Any], list[str], list[str]]] = []
    for parent_asin, row in matched_embeddings.items():
        product = products.get(parent_asin)
        if not product or not product_matches_requested_category(product, category):
            continue
        product_text = row.get("product_text") or build_product_text(product)
        matched_terms = [term for term in positive_terms if term.lower() in product_text.lower()]
        warnings = [f"matched avoided signal: {term}" for term in negative_terms if term.lower() in product_text.lower()]
        enriched_product = {**product, "product_text": product_text}
        results.append((enriched_product, matched_terms[:5], warnings[:5]))
        if len(results) >= limit:
            break
    return results


def retrieve_candidates_with_sources(
    user_id: str | None,
    category: str,
    intent: RecommendationIntent,
    limit: int = 50,
    client: Client | None = None,
    vector_store: VectorStore | None = None,
    persona: dict[str, Any] | None = None,
    taste_vector_row: dict[str, Any] | None = None,
) -> CandidateRetrievalResult:
    client = client or get_supabase_client()
    reviewed = fetch_reviewed_parent_asins(user_id, client=client) if user_id else set()
    vector_store = vector_store or SupabasePgVectorStore(client=client)
    category_filter = effective_category(category, intent)
    vector_row = taste_vector_row or (fetch_user_taste_vector(user_id, category, client=client) if user_id else None)
    candidates_by_asin: dict[str, RecommendationCandidate] = {}
    source_counts: dict[str, int] = {}

    taste_vector: list[float] = []
    if vector_row and vector_row.get("embedding"):
        taste_vector = parse_embedding(vector_row["embedding"])
        try:
            matches = vector_store.search_products(
                taste_vector,
                limit=limit,
                exclude_parent_asins=reviewed,
            )
        except Exception:
            matches = []
        add_vector_matches(candidates_by_asin, matches, "taste_vector", reviewed, client, category_filter, source_counts)

    retrieval_query = intent.retrieval_query.strip()
    if retrieval_query:
        try:
            matches = vector_store.search_products(
                embed_text(retrieval_query),
                limit=limit,
                exclude_parent_asins=reviewed,
            )
        except Exception:
            matches = []
        add_vector_matches(candidates_by_asin, matches, "request_query", reviewed, client, category_filter, source_counts)

    if user_id and taste_vector:
        try:
            collaborative = retrieve_collaborative_candidates(
                user_id,
                category,
                taste_vector,
                reviewed,
                limit=max(10, limit // 2),
                client=client,
                vector_store=vector_store,
            )
        except Exception:
            collaborative = []
        for product, similarity, evidence in collaborative:
            merge_candidate(
                candidates_by_asin,
                product,
                "collaborative",
                collaborative_similarity=similarity,
                evidence=evidence,
            )
            source_counts["collaborative"] = source_counts.get("collaborative", 0) + 1

    try:
        attribute_matches = retrieve_attribute_match_candidates(
            persona,
            intent,
            reviewed,
            limit=max(10, limit // 2),
            client=client,
            category=category_filter,
        )
    except Exception:
        attribute_matches = []
    for product, evidence, warnings in attribute_matches:
        merge_candidate(candidates_by_asin, product, "attribute_match", evidence=evidence, warnings=warnings)
        source_counts["attribute_match"] = source_counts.get("attribute_match", 0) + 1

    candidates = list(candidates_by_asin.values())
    if len(candidates) < limit:
        seen = {candidate.parent_asin for candidate in candidates}
        fallback = fetch_quality_fallback_products(
            user_id,
            limit=limit,
            client=client,
            category=category_filter,
            intent=intent,
            reviewed=reviewed,
        )
        for candidate in fallback:
            if candidate.parent_asin in seen:
                continue
            candidates.append(candidate)
            seen.add(candidate.parent_asin)
            source_counts["quality_fallback"] = source_counts.get("quality_fallback", 0) + 1
            if len(candidates) >= limit:
                break

    return CandidateRetrievalResult(candidates=candidates[:limit], source_counts=source_counts)


def retrieve_candidates(
    user_id: str | None,
    category: str,
    intent: RecommendationIntent,
    limit: int = 50,
    client: Client | None = None,
    vector_store: VectorStore | None = None,
    persona: dict[str, Any] | None = None,
    taste_vector_row: dict[str, Any] | None = None,
) -> list[RecommendationCandidate]:
    return retrieve_candidates_with_sources(
        user_id,
        category,
        intent,
        limit=limit,
        client=client,
        vector_store=vector_store,
        persona=persona,
        taste_vector_row=taste_vector_row,
    ).candidates
