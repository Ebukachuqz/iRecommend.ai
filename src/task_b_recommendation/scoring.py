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


INTENT_TERM_ALIASES = {
    "suitable for dry skin": "dry skin",
    "for dry skin": "dry skin",
    "oil free": "oil free",
    "value for money": "value for money",
    "sensitive skin": "sensitive skin",
    "acne prone": "acne prone",
    "non comedogenic": "non comedogenic",
}

RELATED_REQUEST_TERMS = {
    "dry skin": [
        "dry skin",
        "moisturizer",
        "moisturiser",
        "moisturizing",
        "moisturising",
        "hydrating",
        "hydration",
        "soft",
        "sensitive skin",
        "body butter",
        "cream",
    ],
    "oily skin": [
        "oily skin",
        "oil free",
        "oil-free",
        "oil control",
        "non greasy",
        "non-greasy",
        "cleanser",
        "toner",
        "acne",
        "pore",
    ],
    "affordable": ["affordable", "value", "budget", "low price"],
    "value for money": ["value for money", "value", "budget", "affordable"],
    "skincare": ["skincare", "skin care", "face", "facial", "body", "cleanser", "toner", "serum", "moisturizer", "cream"],
}


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_intent_term(term: str) -> str:
    normalized = str(term).strip().lower().replace("_", " ").replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return INTENT_TERM_ALIASES.get(normalized, normalized)


def normalize_text_for_matching(text: str) -> str:
    normalized = text.lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", normalized)


def unique_terms(terms: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for term in terms:
        normalized = normalize_intent_term(term)
        if not normalized or normalized in seen:
            continue
        output.append(normalized)
        seen.add(normalized)
        if limit is not None and len(output) >= limit:
            break
    return output


def normalized_required_attributes(intent: RecommendationIntent) -> list[str]:
    return unique_terms(intent.required_attributes)


def related_terms_for_intent(intent: RecommendationIntent) -> list[str]:
    related: list[str] = []
    required = normalized_required_attributes(intent)
    for term in required:
        related.extend(RELATED_REQUEST_TERMS.get(term, []))
    return unique_terms(related)


def terms_from_persona(persona: dict[str, Any], *keys: str) -> list[str]:
    preferences = persona.get("preferences", {}) if isinstance(persona.get("preferences"), dict) else {}
    terms: list[str] = []
    for key in keys:
        value = preferences.get(key, [])
        if isinstance(value, list):
            terms.extend(str(item) for item in value if str(item).strip())
    return terms


def contains_term(text: str, term: str) -> bool:
    normalized_text = normalize_text_for_matching(text)
    normalized_term = normalize_intent_term(term)
    return bool(normalized_term and re.search(re.escape(normalized_term), normalized_text))


def matched_terms(text: str, terms: list[str]) -> list[str]:
    return unique_terms([term for term in terms if contains_term(text, term)])


def preference_match_score(
    persona: dict[str, Any],
    product: dict[str, Any],
    intent: RecommendationIntent,
) -> tuple[float, list[str], list[str]]:
    text = build_product_text(product).lower()
    positive_terms = unique_terms(terms_from_persona(persona, "liked_attributes", "what_they_value", "liked_product_types"))
    request_terms = normalized_required_attributes(intent)
    related_request_terms = related_terms_for_intent(intent)
    negative_terms = terms_from_persona(persona, "disliked_attributes", "common_complaints", "disliked_product_types")
    negative_terms.extend(intent.excluded_attributes)
    matched_persona_terms = matched_terms(text, positive_terms)
    matched_request_terms = matched_terms(text, request_terms)
    matched_related_terms = [term for term in matched_terms(text, related_request_terms) if term not in matched_request_terms]
    matched = unique_terms(matched_persona_terms + matched_request_terms + matched_related_terms)
    warnings = [f"Matched avoided signal: {term}" for term in negative_terms if contains_term(text, term)]
    score = (
        0.30
        + min(0.20, len(matched_persona_terms) * 0.06)
        + min(0.38, len(matched_request_terms) * 0.14)
        + min(0.24, len(matched_related_terms) * 0.08)
        - min(0.35, len(warnings) * 0.12)
    )
    return clamp_score(score), matched, warnings


def request_fit_adjustment(product: dict[str, Any], intent: RecommendationIntent) -> tuple[float, list[str], list[str]]:
    text = build_product_text(product).lower()
    required = set(normalized_required_attributes(intent))
    warnings: list[str] = []
    matched: list[str] = []
    adjustment = 0.0

    wants_skincare = "skincare" in required or "oily skin" in required or "dry skin" in required
    wants_oily_skin = "oily skin" in required
    wants_dry_skin = "dry skin" in required
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
        if re.search(r"\b(under eye|eye pads|eye mask|eye cream|eye gel)\b", normalize_text_for_matching(text)):
            direct_terms = ["face moisturizer", "facial moisturizer", "cleanser", "toner", "dry skin", "body butter", "cream"]
            if not any(contains_term(text, term) for term in direct_terms):
                warnings.append("Narrow eye-area product for broad skincare request.")
                adjustment -= 0.06

    if wants_oily_skin:
        oily_skin_terms = RELATED_REQUEST_TERMS["oily skin"] + ["non comedogenic", "face", "facial"]
        matched_oily_terms = matched_terms(text, oily_skin_terms)
        if matched_oily_terms:
            matched.extend(matched_oily_terms[:5])
            adjustment += min(0.16, 0.04 * len(matched_oily_terms))

    if wants_dry_skin:
        dry_skin_terms = RELATED_REQUEST_TERMS["dry skin"] + ["face", "facial", "cleanser"]
        matched_dry_terms = matched_terms(text, dry_skin_terms)
        if matched_dry_terms:
            matched.extend(matched_dry_terms[:5])
            adjustment += min(0.18, 0.04 * len(matched_dry_terms))

    return adjustment, unique_terms(matched), warnings


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
    required = set(normalized_required_attributes(intent))
    if "affordable" in required or "value for money" in required:
        if price <= 15:
            return 1.0
        if price <= 25:
            return 0.85
        return 0.35
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
