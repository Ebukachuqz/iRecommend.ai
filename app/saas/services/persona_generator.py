from __future__ import annotations

import json
from collections import Counter
from statistics import mean
from typing import Any

from supabase import Client

from app.saas.db import get_saas_client
from src.config import get_settings
from src.llm.groq_client import get_groq_chat
from src.llm.logging import log_llm_response
from src.llm.parsers import parse_json_from_llm_text
from src.personas.prompts import PERSONA_PROMPT, PERSONA_SCHEMA_EXAMPLE, PERSONA_SYSTEM_INSTRUCTIONS
from src.personas.validator import persona_to_storage_dict, validate_persona


def _text(value: Any) -> str:
    return str(value or "").strip()


def _coerce_rating(value: Any) -> float | None:
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    if rating < 1 or rating > 5:
        return None
    return rating


def compute_review_stats(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    ratings = [rating for review in reviews if (rating := _coerce_rating(review.get("rating"))) is not None]
    rounded = Counter(str(int(round(rating))) for rating in ratings)
    categories = [
        _text(review.get("category"))
        for review in reviews
        if _text(review.get("category"))
    ]
    return {
        "review_count": len(reviews),
        "average_rating": round(mean(ratings), 3) if ratings else 0.0,
        "rating_distribution": {str(key): rounded.get(str(key), 0) for key in range(1, 6)},
        "verified_purchase_ratio": 0.0,
        "preferred_categories": [category for category, _ in Counter(categories).most_common(5)],
    }


def infer_strictness(average_rating: float) -> str:
    if average_rating and average_rating < 3.4:
        return "strict"
    if average_rating >= 4.3:
        return "generous"
    return "moderate"


def extract_signal_terms(reviews: list[dict[str, Any]], *, positive: bool) -> list[str]:
    signals: list[str] = []
    for review in reviews:
        rating = _coerce_rating(review.get("rating")) or 0
        if positive and rating < 4:
            continue
        if not positive and rating > 2:
            continue
        product = _text(review.get("product_name")) or "the product"
        category = _text(review.get("category"))
        label = f"{product} ({category})" if category else product
        if label not in signals:
            signals.append(label)
        if len(signals) >= 5:
            break
    return signals


def format_review_context(reviews: list[dict[str, Any]], max_reviews: int = 12) -> str:
    selected = reviews[-max_reviews:]
    blocks = []
    for index, review in enumerate(selected, start=1):
        blocks.append(
            "\n".join(
                [
                    f"Review {index}",
                    f"Product: {_text(review.get('product_name')) or 'Unknown Product'}",
                    f"Category: {_text(review.get('category')) or 'Unknown'}",
                    f"Rating: {review.get('rating')}/5",
                    f"Review date: {_text(review.get('review_date')) or 'Unknown'}",
                    f"Review: {_text(review.get('review_text'))}",
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)


def build_fallback_persona(customer_id: str, reviews: list[dict[str, Any]]) -> dict[str, Any]:
    stats = compute_review_stats(reviews)
    average_rating = float(stats["average_rating"])
    positive_examples = [
        _text(review.get("review_text"))
        for review in reviews
        if (_coerce_rating(review.get("rating")) or 0) >= 4 and _text(review.get("review_text"))
    ][:3]
    negative_examples = [
        _text(review.get("review_text"))
        for review in reviews
        if (_coerce_rating(review.get("rating")) or 0) <= 2 and _text(review.get("review_text"))
    ][:3]
    persona = {
        "writing_style": {
            "tone": "practical and experience-led",
            "length": "medium",
            "detail_level": "medium",
            "formality": "mixed",
            "vocabulary_markers": [],
            "common_phrases": [],
        },
        "preferences": {
            "liked_product_types": extract_signal_terms(reviews, positive=True),
            "disliked_product_types": extract_signal_terms(reviews, positive=False),
            "liked_attributes": [],
            "disliked_attributes": [],
            "what_they_value": ["reliable product experience", "clear value for money"],
            "common_complaints": ["issues mentioned in lower-rated reviews"] if negative_examples else [],
        },
        "rating_behavior": {
            "average_rating": average_rating,
            "rating_distribution": stats["rating_distribution"],
            "strictness": infer_strictness(average_rating),
            "rating_patterns": "Computed from merchant CSV review history.",
        },
        "purchase_behavior": {
            "preferred_categories": stats["preferred_categories"],
            "price_sensitivity": "unknown",
            "quality_sensitivity": "medium",
            "verified_purchase_ratio": 0.0,
        },
        "cultural_signals": "",
        "evidence": {
            "positive_examples": positive_examples,
            "negative_examples": negative_examples,
        },
        "extra_persona_signals": {
            "generation_mode": "fallback",
            "customer_id": customer_id,
            "review_count": len(reviews),
        },
    }
    return persona_to_storage_dict(validate_persona(persona, repair=True))


class MerchantPersonaGenerator:
    def __init__(self, client: Client | None = None) -> None:
        self.client = client or get_saas_client()
        self.settings = get_settings()

    def generate_persona(self, customer_id: str, reviews: list[dict[str, Any]], org_id: str) -> tuple[dict[str, Any], str]:
        stats = compute_review_stats(reviews)
        prompt_input = {
            "instructions": PERSONA_SYSTEM_INSTRUCTIONS,
            "category": "merchant customer reviews",
            "user_stats": json.dumps(stats, indent=2),
            "review_context": format_review_context(reviews),
            "schema_example": json.dumps(PERSONA_SCHEMA_EXAMPLE, indent=2),
        }
        llm = get_groq_chat(self.settings.groq_model)
        raw_message = (PERSONA_PROMPT | llm).invoke(prompt_input)
        raw_text = getattr(raw_message, "content", str(raw_message))
        raw_payload, cleaned_json_text = parse_json_from_llm_text(raw_text)
        raw_payload.setdefault("extra_persona_signals", {})
        raw_payload["extra_persona_signals"]["generation_mode"] = "llm"
        raw_payload["rating_behavior"] = dict(raw_payload.get("rating_behavior") or {})
        raw_payload["rating_behavior"]["average_rating"] = stats["average_rating"]
        raw_payload["rating_behavior"]["rating_distribution"] = stats["rating_distribution"]
        raw_payload["purchase_behavior"] = dict(raw_payload.get("purchase_behavior") or {})
        raw_payload["purchase_behavior"]["verified_purchase_ratio"] = 0.0
        persona = persona_to_storage_dict(validate_persona(raw_payload, repair=True))
        log_llm_response(
            "merchant_persona_generation",
            {
                "organisation_id": org_id,
                "customer_id": customer_id,
                "model_name": self.settings.groq_model,
                "raw_text": raw_text,
                "cleaned_json_text": cleaned_json_text,
                "parsed_payload": raw_payload,
            },
        )
        return persona, "llm"

    def generate_with_fallback(self, customer_id: str, reviews: list[dict[str, Any]], org_id: str) -> tuple[dict[str, Any], str, str | None]:
        try:
            persona, mode = self.generate_persona(customer_id, reviews, org_id)
            return persona, mode, None
        except Exception as exc:
            return build_fallback_persona(customer_id, reviews), "fallback", str(exc)

    def upsert_persona(self, org_id: str, customer_id: str, persona: dict[str, Any], review_count: int) -> None:
        self.client.table("merchant_personas").upsert(
            {
                "organisation_id": org_id,
                "customer_id": customer_id,
                "persona": persona,
                "review_count": review_count,
            },
            on_conflict="organisation_id,customer_id",
        ).execute()
