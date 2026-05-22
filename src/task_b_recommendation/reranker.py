from __future__ import annotations

import json
from typing import Any

from src.config import get_settings
from src.llm.groq_client import get_groq_chat
from src.llm.logging import log_llm_response
from src.llm.parsers import parse_json_from_llm_text
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


def fallback_rerank(
    candidates: list[ScoredRecommendationCandidate],
    limit: int,
) -> RerankerOutput:
    recommendations = []
    for rank, candidate in enumerate(candidates[:limit], start=1):
        matched = candidate.score_breakdown.matched_persona_signals
        evidence = matched[:3] or ["High transparent score from metadata and persona matching."]
        reason = (
            f"Matches persona signals: {', '.join(matched[:3])}."
            if matched
            else "Ranks well from product quality, reliability, and available preference signals."
        )
        recommendations.append(
            RerankedRecommendation(
                parent_asin=candidate.parent_asin,
                rank=rank,
                title=candidate.title,
                reason=reason,
                confidence=candidate.score_breakdown.final_score,
                evidence=evidence,
                score_breakdown=candidate.score_breakdown.model_dump(mode="json"),
            )
        )
    return RerankerOutput(recommendations=recommendations)


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
        reranked = RerankerOutput(recommendations=filtered) if filtered else fallback_rerank(candidates, limit)
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
        return fallback_rerank(candidates, limit)
