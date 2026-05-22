from __future__ import annotations

import re
from typing import Any

from src.task_a_simulation.schema import ProductSnapshot, RatingPredictionBreakdown


def clamp_rating(value: float) -> float:
    return max(1.0, min(5.0, value))


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(normalize_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {normalize_text(item)}" for key, item in value.items())
    return str(value)


def product_search_text(product: ProductSnapshot) -> str:
    parts = [
        product.title,
        product.main_category,
        product.categories,
        product.features,
        product.description,
        product.store,
        product.details,
    ]
    return re.sub(r"\s+", " ", " ".join(normalize_text(part) for part in parts)).lower()


def count_matches(terms: list[str], text: str) -> int:
    return sum(1 for term in terms if term and term.lower() in text)


def get_persona_section(persona: dict[str, Any], section: str) -> dict[str, Any]:
    value = persona.get(section, {})
    return value if isinstance(value, dict) else {}


def user_average_from_persona(persona: dict[str, Any]) -> float:
    rating_behavior = get_persona_section(persona, "rating_behavior")
    average = rating_behavior.get("average_rating") or 3.5
    return clamp_rating(float(average))


def predict_statistical_rating(
    persona: dict[str, Any],
    product: ProductSnapshot | dict[str, Any],
) -> RatingPredictionBreakdown:
    product = product if isinstance(product, ProductSnapshot) else ProductSnapshot.model_validate(product)
    preferences = get_persona_section(persona, "preferences")
    rating_behavior = get_persona_section(persona, "rating_behavior")
    purchase_behavior = get_persona_section(persona, "purchase_behavior")

    user_average = user_average_from_persona(persona)
    product_average = product.average_rating
    rating_count = product.rating_number or 0
    product_component = product_average if product_average and rating_count >= 5 else user_average
    predicted = (0.65 * user_average) + (0.35 * product_component)

    text = product_search_text(product)
    liked_terms = (
        preferences.get("liked_attributes", [])
        + preferences.get("what_they_value", [])
        + preferences.get("liked_product_types", [])
    )
    disliked_terms = (
        preferences.get("disliked_attributes", [])
        + preferences.get("common_complaints", [])
        + preferences.get("disliked_product_types", [])
    )

    liked_matches = count_matches(liked_terms, text)
    disliked_matches = count_matches(disliked_terms, text)
    preference_match_score = min(0.6, liked_matches * 0.15)
    disliked_attribute_penalty = -min(0.8, disliked_matches * 0.2)

    price_fit_score = 0.0
    price_sensitivity = purchase_behavior.get("price_sensitivity", "unknown")
    if product.price is not None:
        if price_sensitivity == "high" and product.price > 35:
            price_fit_score = -0.25
        elif price_sensitivity == "low" and product.price > 35:
            price_fit_score = 0.05
        elif price_sensitivity in {"medium", "high"} and product.price <= 15:
            price_fit_score = 0.15

    quality_sensitivity = purchase_behavior.get("quality_sensitivity", "medium")
    if quality_sensitivity == "high" and product_average and product_average < 4:
        predicted -= 0.25
    elif quality_sensitivity == "high" and product_average and product_average >= 4.4 and rating_count >= 20:
        predicted += 0.15

    strictness = rating_behavior.get("strictness", "moderate")
    strictness_adjustment = 0.0
    if strictness == "strict":
        strictness_adjustment = -0.25
    elif strictness == "generous":
        strictness_adjustment = 0.15

    predicted = clamp_rating(
        predicted
        + preference_match_score
        + disliked_attribute_penalty
        + price_fit_score
        + strictness_adjustment
    )

    explanation = (
        f"Started from user average {user_average:.2f}; "
        f"product average contribution {product_component:.2f}; "
        f"liked matches={liked_matches}, disliked matches={disliked_matches}; "
        f"strictness={strictness}."
    )

    return RatingPredictionBreakdown(
        user_average_rating=user_average,
        product_average_rating=product_average,
        preference_match_score=preference_match_score,
        disliked_attribute_penalty=disliked_attribute_penalty,
        price_fit_score=price_fit_score,
        strictness_adjustment=strictness_adjustment,
        statistical_predicted_rating=round(predicted, 3),
        explanation=explanation,
    )
