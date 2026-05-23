from __future__ import annotations

import re
from typing import Any

from src.task_b_recommendation.product_text import build_product_text
from src.task_b_recommendation.schema import (
    RecommendationIntent,
    RecommendationScoreBreakdown,
    ScoredRecommendationCandidate,
    RecommendationCandidate,
)


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def terms_from_persona(persona: dict[str, Any], *keys: str) -> list[str]:
    preferences = persona.get("preferences", {}) if isinstance(persona.get("preferences"), dict) else {}
    terms: list[str] = []
    for key in keys:
        value = preferences.get(key, [])
        if isinstance(value, list):
            terms.extend(str(item) for item in value if str(item).strip())
    return terms


def contains_term(text: str, term: str) -> bool:
    return bool(term and re.search(re.escape(term.lower()), text))


def preference_match_score(
    persona: dict[str, Any],
    product: dict[str, Any],
    intent: RecommendationIntent,
) -> tuple[float, list[str], list[str]]:
    text = build_product_text(product).lower()
    positive_terms = terms_from_persona(persona, "liked_attributes", "what_they_value", "liked_product_types")
    request_terms = list(intent.required_attributes)
    negative_terms = terms_from_persona(persona, "disliked_attributes", "common_complaints", "disliked_product_types")
    negative_terms.extend(intent.excluded_attributes)
    matched = [term for term in positive_terms if contains_term(text, term)]
    matched_request_terms = [term for term in request_terms if contains_term(text, term)]
    matched.extend(matched_request_terms)
    warnings = [f"Matched avoided signal: {term}" for term in negative_terms if contains_term(text, term)]
    score = (
        0.30
        + min(0.30, len(matched) * 0.08)
        + min(0.45, len(matched_request_terms) * 0.16)
        - min(0.35, len(warnings) * 0.12)
    )
    return clamp_score(score), matched, warnings


def request_fit_adjustment(product: dict[str, Any], intent: RecommendationIntent) -> tuple[float, list[str], list[str]]:
    text = build_product_text(product).lower()
    required = {term.lower() for term in intent.required_attributes}
    warnings: list[str] = []
    matched: list[str] = []
    adjustment = 0.0

    wants_skincare = "skincare" in required or "oily skin" in required
    wants_oily_skin = "oily skin" in required
    off_type_terms = [
        "shampoo",
        "conditioner",
        "hair",
        "nail",
        "travel",
        "luggage",
        "brush",
        "hand cream",
        "body lotion",
        "foot cream",
    ]
    if wants_skincare:
        off_type_matches = [term for term in off_type_terms if contains_term(text, term)]
        if off_type_matches:
            warnings.append(f"Possible off-type match for skincare request: {', '.join(off_type_matches[:3])}")
            adjustment -= 0.18

    if wants_oily_skin:
        oily_skin_terms = ["oily skin", "oil-free", "oil free", "non-comedogenic", "toner", "cleanser", "face", "facial", "acne"]
        matched_oily_terms = [term for term in oily_skin_terms if contains_term(text, term)]
        if matched_oily_terms:
            matched.extend(matched_oily_terms[:4])
            adjustment += min(0.16, 0.04 * len(matched_oily_terms))

    return adjustment, matched, warnings


def product_quality_score(product: dict[str, Any]) -> float:
    average_rating = float(product.get("average_rating") or 0)
    if average_rating <= 0:
        return 0.45
    return clamp_score(average_rating / 5)


def popularity_reliability_score(product: dict[str, Any]) -> float:
    rating_number = int(product.get("rating_number") or 0)
    if rating_number <= 0:
        return 0.25
    if rating_number >= 500:
        return 1.0
    return clamp_score(rating_number / 500)


def price_fit_score(persona: dict[str, Any], product: dict[str, Any], intent: RecommendationIntent) -> float:
    price = product.get("price")
    if price is None:
        return 0.5
    price = float(price)
    if intent.price_max is not None:
        return 1.0 if price <= intent.price_max else 0.15
    purchase_behavior = persona.get("purchase_behavior", {}) if isinstance(persona.get("purchase_behavior"), dict) else {}
    sensitivity = purchase_behavior.get("price_sensitivity", "unknown")
    if sensitivity == "high":
        return 0.9 if price <= 20 else 0.35
    if sensitivity == "medium":
        return 0.8 if price <= 40 else 0.45
    return 0.65


def score_candidate(
    candidate: RecommendationCandidate,
    persona: dict[str, Any],
    intent: RecommendationIntent,
) -> ScoredRecommendationCandidate:
    product = candidate.product
    preference_score, matched, warnings = preference_match_score(persona, product, intent)
    request_adjustment, request_matches, request_warnings = request_fit_adjustment(product, intent)
    matched.extend(term for term in request_matches if term not in matched)
    warnings.extend(request_warnings)
    quality_score = product_quality_score(product)
    price_score = price_fit_score(persona, product, intent)
    reliability_score = popularity_reliability_score(product)
    semantic_similarity = clamp_score(candidate.semantic_similarity)
    final_score = (
        0.30 * semantic_similarity
        + 0.25 * preference_score
        + 0.20 * quality_score
        + 0.15 * price_score
        + 0.10 * reliability_score
        + request_adjustment
    )
    breakdown = RecommendationScoreBreakdown(
        semantic_similarity=semantic_similarity,
        preference_match=preference_score,
        product_quality=quality_score,
        price_fit=price_score,
        popularity_reliability=reliability_score,
        final_score=round(clamp_score(final_score), 4),
        matched_persona_signals=matched,
        warnings=warnings,
    )
    return ScoredRecommendationCandidate(**candidate.model_dump(), score_breakdown=breakdown)


def score_candidates(
    candidates: list[RecommendationCandidate],
    persona: dict[str, Any],
    intent: RecommendationIntent,
) -> list[ScoredRecommendationCandidate]:
    scored = [score_candidate(candidate, persona, intent) for candidate in candidates]
    return sorted(scored, key=lambda candidate: candidate.score_breakdown.final_score, reverse=True)
