from __future__ import annotations

import re
from typing import Any


BEAUTY_DOMAINS = {
    "all beauty",
    "beauty",
    "beauty and personal care",
    "skincare",
    "skin care",
    "skin care and body wash",
    "personal care",
}

DOMAIN_ALIASES = {
    "all beauty": "beauty",
    "beauty": "beauty",
    "beauty and personal care": "beauty",
    "skincare": "beauty",
    "skin care": "beauty",
    "skin care and body wash": "beauty",
    "personal care": "beauty",
    "electronics": "electronics",
    "books": "books",
    "home and kitchen": "home",
    "home kitchen": "home",
    "home": "home",
    "clothing shoes and jewelry": "fashion",
    "fashion": "fashion",
}

TRANSFERABLE_TERMS = {
    "affordable",
    "authentic",
    "budget",
    "durable",
    "durability",
    "easy to use",
    "good quality",
    "long lasting",
    "low quality",
    "misleading",
    "not overhyped",
    "overhyped",
    "premium",
    "quality",
    "reliable",
    "reliability",
    "simple",
    "simplicity",
    "sturdy",
    "value",
    "value for money",
    "well made",
}

CATEGORY_SPECIFIC_TERMS = {
    "acne",
    "cleanser",
    "dry skin",
    "fragrance",
    "fragrance free",
    "hair",
    "hydrating",
    "moisturizer",
    "oil free",
    "oily skin",
    "serum",
    "shampoo",
    "skin",
    "skincare",
    "toner",
}


def coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value).strip()] if str(value).strip() else []


def normalize_category_label(category: str | None) -> str | None:
    if not category:
        return None
    normalized = str(category).replace("_", " ").replace("-", " ").lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def category_domain(category: str | None) -> str | None:
    normalized = normalize_category_label(category)
    if not normalized:
        return None
    if normalized in DOMAIN_ALIASES:
        return DOMAIN_ALIASES[normalized]
    if normalized in BEAUTY_DOMAINS or "beauty" in normalized or "skin care" in normalized or "skincare" in normalized:
        return "beauty"
    if "electronic" in normalized:
        return "electronics"
    if "book" in normalized:
        return "books"
    if "home" in normalized or "kitchen" in normalized:
        return "home"
    return normalized


def categories_are_meaningfully_different(source_category: str | None, target_category: str | None) -> bool:
    source_domain = category_domain(source_category)
    target_domain = category_domain(target_category)
    return bool(source_domain and target_domain and source_domain != target_domain)


def request_derived_signals(request_text: str) -> dict[str, list[str] | str]:
    lower = request_text.lower()
    liked_attributes: list[str] = []
    values: list[str] = []
    preferred_categories: list[str] = []
    price_sensitivity = "unknown"
    quality_sensitivity = "medium"

    if any(term in lower for term in ("affordable", "cheap", "budget", "value")):
        values.extend(["value for money", "affordable"])
        price_sensitivity = "high"
    if any(term in lower for term in ("premium", "high end", "high-end")):
        values.append("premium quality")
        price_sensitivity = "low"
        quality_sensitivity = "high"
    if any(term in lower for term in ("durable", "reliable", "sturdy", "long lasting", "long-lasting")):
        values.extend(["durability", "reliability"])
        quality_sensitivity = "high"
    if "gentle" in lower:
        liked_attributes.append("gentle")
    if "fragrance-free" in lower or "fragrance free" in lower:
        liked_attributes.append("fragrance free")
    if "skincare" in lower or "skin care" in lower:
        preferred_categories.append("skincare")
    if "electronics" in lower or "electronic" in lower:
        preferred_categories.append("electronics")
    if "book" in lower:
        preferred_categories.append("books")

    return {
        "liked_attributes": list(dict.fromkeys(liked_attributes)),
        "what_they_value": list(dict.fromkeys(values)),
        "preferred_categories": list(dict.fromkeys(preferred_categories)),
        "price_sensitivity": price_sensitivity,
        "quality_sensitivity": quality_sensitivity,
    }


def build_cold_start_persona(request: str | None = None, onboarding_answers: dict[str, Any] | None = None) -> dict[str, Any]:
    answers = onboarding_answers or {}
    request_text = request or ""
    request_signals = request_derived_signals(request_text)
    liked_attributes = coerce_list(answers.get("liked_attributes")) + list(request_signals["liked_attributes"])
    values = coerce_list(answers.get("what_they_value")) + list(request_signals["what_they_value"])
    preferred_categories = coerce_list(answers.get("preferred_categories")) + list(request_signals["preferred_categories"])
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
            "liked_product_types": coerce_list(answers.get("liked_product_types")),
            "disliked_product_types": coerce_list(answers.get("disliked_product_types")),
            "liked_attributes": list(dict.fromkeys(liked_attributes)),
            "disliked_attributes": coerce_list(answers.get("disliked_attributes")),
            "what_they_value": list(dict.fromkeys(values)),
            "common_complaints": coerce_list(answers.get("common_complaints")),
        },
        "rating_behavior": {
            "average_rating": 3.8,
            "rating_distribution": {"1": 0, "2": 0, "3": 1, "4": 2, "5": 1},
            "strictness": "moderate",
            "rating_patterns": "Temporary cold-start estimate.",
        },
        "purchase_behavior": {
            "preferred_categories": list(dict.fromkeys(preferred_categories)),
            "price_sensitivity": answers.get("price_sensitivity") or request_signals["price_sensitivity"],
            "quality_sensitivity": answers.get("quality_sensitivity") or request_signals["quality_sensitivity"],
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
            "persona_confidence": "low",
            "persona_source": "request_context",
        },
        "persona_confidence": "low",
        "persona_source": "request_context",
    }


def is_transferable_term(term: str) -> bool:
    normalized = normalize_category_label(term)
    if not normalized:
        return False
    if normalized in CATEGORY_SPECIFIC_TERMS:
        return False
    return normalized in TRANSFERABLE_TERMS or any(value in normalized for value in TRANSFERABLE_TERMS)


def transferable_values_from_persona(persona: dict[str, Any]) -> list[str]:
    preferences = persona.get("preferences", {}) if isinstance(persona.get("preferences"), dict) else {}
    purchase = persona.get("purchase_behavior", {}) if isinstance(persona.get("purchase_behavior"), dict) else {}
    rating = persona.get("rating_behavior", {}) if isinstance(persona.get("rating_behavior"), dict) else {}
    values: list[str] = []

    price_sensitivity = purchase.get("price_sensitivity")
    if price_sensitivity == "high":
        values.extend(["affordable", "value for money"])
    elif price_sensitivity == "low":
        values.append("premium")
    quality_sensitivity = purchase.get("quality_sensitivity")
    if quality_sensitivity in {"medium", "high"}:
        values.append("quality")
    if rating.get("strictness") == "strict":
        values.extend(["reliable", "well reviewed"])

    for key in ("what_they_value", "common_complaints"):
        for term in coerce_list(preferences.get(key)):
            if is_transferable_term(term):
                values.append(term)

    return list(dict.fromkeys(values))


def cross_domain_persona(persona: dict[str, Any]) -> dict[str, Any]:
    adjusted = dict(persona)
    preferences = dict(adjusted.get("preferences") or {})
    transferable = transferable_values_from_persona(persona)
    preferences["liked_product_types"] = []
    preferences["liked_attributes"] = [term for term in coerce_list(preferences.get("liked_attributes")) if is_transferable_term(term)]
    preferences["what_they_value"] = transferable
    preferences["common_complaints"] = [term for term in coerce_list(preferences.get("common_complaints")) if is_transferable_term(term)]
    adjusted["preferences"] = preferences
    return adjusted


def build_cross_domain_retrieval_query(
    source_persona: dict[str, Any],
    target_category: str,
    request_text: str | None = None,
) -> str:
    values = transferable_values_from_persona(source_persona)
    base = [target_category]
    if request_text:
        base.append(request_text)
    base.extend(values)
    return " ".join(term for term in base if term).strip()
