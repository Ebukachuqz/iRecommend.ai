from __future__ import annotations

from typing import Any


def build_cold_start_persona(request: str | None = None, onboarding_answers: dict[str, Any] | None = None) -> dict[str, Any]:
    answers = onboarding_answers or {}
    request_text = request or ""
    return {
        "writing_style": {
            "tone": "unknown",
            "length": "medium",
            "detail_level": "medium",
            "formality": "mixed",
            "vocabulary_markers": [],
            "common_phrases": [],
        },
        "preferences": {
            "liked_product_types": answers.get("liked_product_types", []),
            "disliked_product_types": answers.get("disliked_product_types", []),
            "liked_attributes": answers.get("liked_attributes", []),
            "disliked_attributes": answers.get("disliked_attributes", []),
            "what_they_value": answers.get("what_they_value", ["value for money"] if "affordable" in request_text.lower() else []),
            "common_complaints": answers.get("common_complaints", []),
        },
        "rating_behavior": {
            "average_rating": 3.8,
            "rating_distribution": {"1": 0, "2": 0, "3": 1, "4": 2, "5": 1},
            "strictness": "moderate",
            "rating_patterns": "Temporary cold-start estimate.",
        },
        "purchase_behavior": {
            "preferred_categories": [],
            "price_sensitivity": "high" if "affordable" in request_text.lower() or "cheap" in request_text.lower() else "unknown",
            "quality_sensitivity": "medium",
            "verified_purchase_ratio": 0.0,
        },
        "cultural_signals": "",
        "evidence": {
            "positive_examples": [],
            "negative_examples": [],
        },
        "extra_persona_signals": {
            "cold_start": True,
            "request_context": request_text,
        },
    }
