from __future__ import annotations

import json
import re
import string
from typing import Any

from src.config import get_settings
from src.llm.groq_client import get_groq_chat
from src.llm.logging import log_llm_response
from src.llm.parsers import parse_json_from_llm_text
from src.task_b_recommendation.product_text import build_product_text
from src.task_b_recommendation.scoring import (
    matched_terms,
    normalize_intent_term,
    normalized_required_attributes,
    related_terms_for_intent,
    unique_terms,
)
from src.task_b_recommendation.schema import (
    RecommendationIntent,
    RerankedRecommendation,
    RerankerOutput,
    ScoredRecommendationCandidate,
)


RERANKER_PROMPT_VERSION = "task_b_reranker_v1"

RERANKER_TEMPLATE = """Rerank product candidates for this specific user.
Return JSON only. Do not invent product facts.
Reasons must connect persona signals to product metadata or score evidence.
Never recommend products outside the candidate list.

Persona:
{persona_json}

User request:
{request_text}

Structured intent:
{intent_json}

Scored candidates:
{candidates_json}

Output:
{{
  "recommendations": [
    {{
      "parent_asin": "string",
      "rank": 1,
      "title": "string",
      "reason": "personalized reason",
      "confidence": 0.0,
      "evidence": [],
      "score_breakdown": {{}}
    }}
  ]
}}
"""


def normalize_product_title(title: str | None) -> str:
    text = (title or "").lower()
    text = re.sub(r"\b\d+(\.\d+)?\s*(fl\s*)?oz\b", " ", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(ounce|ounces|ml|g|gram|grams)\b", " ", text)
    text = re.sub(r"\b(pack of|pack|set of)\s*\d+\b", " ", text)
    text = re.sub(r"\b(single|one count|1 count)\b", " ", text)
    text = text.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", text).strip()


def dedupe_terms(terms: list[str], limit: int = 4) -> list[str]:
    return unique_terms([normalize_intent_term(term) for term in terms], limit=limit)


def concrete_product_matches(candidate: ScoredRecommendationCandidate, intent: RecommendationIntent | None) -> list[str]:
    if not intent:
        return []
    product_text = build_product_text(candidate.product).lower()
    direct_matches = matched_terms(product_text, normalized_required_attributes(intent))
    related_matches = [term for term in matched_terms(product_text, related_terms_for_intent(intent)) if term not in direct_matches]
    return dedupe_terms(direct_matches + related_matches, limit=4)


def build_fallback_reason(
    candidate: ScoredRecommendationCandidate,
    intent: RecommendationIntent | None,
    evidence: list[str],
) -> str:
    request_terms = normalized_required_attributes(intent) if intent else []
    has_affordable_signal = any(term in {"affordable", "value for money"} for term in request_terms)
    concrete = concrete_product_matches(candidate, intent)
    if concrete:
        display_terms = [term for term in concrete if term not in {"affordable", "value for money"}] or concrete
        value_clause = " and has strong price-fit evidence" if has_affordable_signal and candidate.score_breakdown.price_fit >= 0.75 else ""
        return f"This matches the request because it mentions {', '.join(display_terms[:3])}{value_clause}."
    if evidence:
        return f"This fits the request through {', '.join(evidence[:3])}."
    return (
        "This is the best available fallback from product quality, reliability, and preference-fit scores."
    )


def build_fallback_recommendation(
    candidate: ScoredRecommendationCandidate,
    rank: int,
    intent: RecommendationIntent | None = None,
) -> RerankedRecommendation:
    concrete = concrete_product_matches(candidate, intent)
    matched = candidate.score_breakdown.matched_persona_signals
    evidence = dedupe_terms(concrete + matched[:4])
    if intent:
        required = set(normalized_required_attributes(intent))
        if ("affordable" in required or "value for money" in required) and candidate.score_breakdown.price_fit >= 0.75:
            evidence = dedupe_terms(evidence + ["price fit"])
    if not evidence:
        evidence = dedupe_terms(
            [
                f"Product quality score {candidate.score_breakdown.product_quality:.2f}",
                f"Preference match score {candidate.score_breakdown.preference_match:.2f}",
            ],
            limit=2,
        )
    return RerankedRecommendation(
        parent_asin=candidate.parent_asin,
        rank=rank,
        title=candidate.title,
        reason=build_fallback_reason(candidate, intent, evidence),
        confidence=candidate.score_breakdown.final_score,
        evidence=evidence,
        score_breakdown=candidate.score_breakdown.model_dump(mode="json"),
    )


def dedupe_and_backfill_recommendations(
    recommendations: list[RerankedRecommendation],
    candidates: list[ScoredRecommendationCandidate],
    limit: int,
    intent: RecommendationIntent | None = None,
) -> list[RerankedRecommendation]:
    candidate_by_asin = {candidate.parent_asin: candidate for candidate in candidates}
    seen_titles: set[str] = set()
    seen_asins: set[str] = set()
    final: list[RerankedRecommendation] = []

    def add_recommendation(recommendation: RerankedRecommendation) -> None:
        candidate = candidate_by_asin.get(recommendation.parent_asin)
        title = recommendation.title or (candidate.title if candidate else None)
        normalized_title = normalize_product_title(title)
        if recommendation.parent_asin in seen_asins or (normalized_title and normalized_title in seen_titles):
            return
        if candidate:
            evidence = dedupe_terms(
                concrete_product_matches(candidate, intent)
                + candidate.score_breakdown.matched_persona_signals
                + recommendation.evidence
            )
            if intent:
                required = set(normalized_required_attributes(intent))
                if ("affordable" in required or "value for money" in required) and candidate.score_breakdown.price_fit >= 0.75:
                    evidence = dedupe_terms(evidence + ["price fit"])
        else:
            evidence = dedupe_terms(recommendation.evidence)
        if not evidence and candidate:
            evidence = build_fallback_recommendation(candidate, len(final) + 1, intent).evidence
        final.append(
            recommendation.model_copy(
                update={
                    "rank": len(final) + 1,
                    "title": title,
                    "evidence": evidence,
                    "score_breakdown": recommendation.score_breakdown
                    or (candidate.score_breakdown.model_dump(mode="json") if candidate else {}),
                }
            )
        )
        seen_asins.add(recommendation.parent_asin)
        if normalized_title:
            seen_titles.add(normalized_title)

    for recommendation in recommendations:
        add_recommendation(recommendation)
        if len(final) >= limit:
            return final

    for candidate in candidates:
        add_recommendation(build_fallback_recommendation(candidate, len(final) + 1, intent))
        if len(final) >= limit:
            break
    return final


def fallback_rerank(
    candidates: list[ScoredRecommendationCandidate],
    limit: int,
    intent: RecommendationIntent | None = None,
) -> RerankerOutput:
    recommendations = [build_fallback_recommendation(candidate, rank, intent) for rank, candidate in enumerate(candidates, start=1)]
    return RerankerOutput(
        recommendations=dedupe_and_backfill_recommendations(recommendations, candidates, limit, intent)
    )


def rerank_recommendations(
    persona: dict[str, Any],
    request: str | None,
    intent: RecommendationIntent,
    candidates: list[ScoredRecommendationCandidate],
    limit: int = 5,
) -> RerankerOutput:
    if not candidates:
        return RerankerOutput(recommendations=[])
    settings = get_settings()
    top_candidates = candidates[: min(50, max(limit, 20))]
    candidate_payload = [
        {
            "parent_asin": candidate.parent_asin,
            "title": candidate.title,
            "product": {
                "title": candidate.product.get("title"),
                "main_category": candidate.product.get("main_category"),
                "features": candidate.product.get("features"),
                "description": candidate.product.get("description"),
                "average_rating": candidate.product.get("average_rating"),
                "rating_number": candidate.product.get("rating_number"),
                "price": candidate.product.get("price"),
                "store": candidate.product.get("store"),
            },
            "score_breakdown": candidate.score_breakdown.model_dump(mode="json"),
        }
        for candidate in top_candidates
    ]
    prompt = RERANKER_TEMPLATE.format(
        persona_json=json.dumps(persona, indent=2, ensure_ascii=False),
        request_text=request or "",
        intent_json=json.dumps(intent.model_dump(mode="json"), indent=2, ensure_ascii=False),
        candidates_json=json.dumps(candidate_payload, indent=2, ensure_ascii=False),
    )
    try:
        raw_message = get_groq_chat(settings.groq_model).invoke(prompt)
        raw_text = getattr(raw_message, "content", str(raw_message))
        parsed, cleaned_json_text = parse_json_from_llm_text(raw_text)
        output = RerankerOutput.model_validate(parsed)
        allowed = {candidate.parent_asin: candidate for candidate in candidates}
        filtered: list[RerankedRecommendation] = []
        for recommendation in output.recommendations:
            candidate = allowed.get(recommendation.parent_asin)
            if not candidate:
                continue
            filtered.append(
                recommendation.model_copy(
                    update={
                        "rank": len(filtered) + 1,
                        "title": recommendation.title or candidate.title,
                        "score_breakdown": recommendation.score_breakdown
                        or candidate.score_breakdown.model_dump(mode="json"),
                    }
                )
            )
            if len(filtered) >= limit:
                break
        final_recommendations = (
            dedupe_and_backfill_recommendations(filtered, candidates, limit, intent)
            if filtered
            else fallback_rerank(candidates, limit, intent).recommendations
        )
        reranked = RerankerOutput(recommendations=final_recommendations)
        log_llm_response(
            "task_b_reranking",
            {
                "model_name": settings.groq_model,
                "prompt_version": RERANKER_PROMPT_VERSION,
                "raw_text": raw_text,
                "cleaned_json_text": cleaned_json_text,
                "parsed_payload": reranked.model_dump(mode="json"),
            },
        )
        return reranked
    except Exception as exc:
        log_llm_response(
            "task_b_reranking_fallback",
            {
                "model_name": settings.groq_model,
                "prompt_version": RERANKER_PROMPT_VERSION,
                "error": str(exc),
            },
        )
        return fallback_rerank(candidates, limit, intent)
