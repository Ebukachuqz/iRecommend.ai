import pytest

from src.personas.normalizer import MINIMUM_PERSONA_ERROR, normalize_custom_persona
from src.task_a_simulation.product_normalizer import MINIMUM_PRODUCT_ERROR, normalize_custom_product


def test_valid_internal_persona_is_preserved() -> None:
    persona = {
        "writing_style": {"tone": "direct"},
        "preferences": {"liked_attributes": ["hydrating"]},
        "rating_behavior": {"average_rating": 4.2, "strictness": "moderate"},
        "purchase_behavior": {"preferred_categories": ["Skincare"]},
    }

    normalized = normalize_custom_persona(persona)

    assert normalized["writing_style"]["tone"] == "direct"
    assert normalized["preferences"]["liked_attributes"] == ["hydrating"]
    assert normalized["rating_behavior"]["average_rating"] == 4.2


def test_simple_custom_persona_maps_into_internal_schema() -> None:
    normalized = normalize_custom_persona(
        {
            "likes": ["hydrating skincare"],
            "dislikes": "strong fragrance",
            "budget": "medium",
            "tone": "casual",
            "average_rating": 4.2,
            "concerns": ["dry skin"],
        }
    )

    assert "hydrating skincare" in normalized["preferences"]["liked_attributes"]
    assert "strong fragrance" in normalized["preferences"]["disliked_attributes"]
    assert "dry skin" in normalized["preferences"]["common_complaints"]
    assert normalized["writing_style"]["tone"] == "casual"
    assert normalized["rating_behavior"]["average_rating"] == 4.2
    assert normalized["purchase_behavior"]["price_sensitivity"] == "medium"


def test_unknown_persona_fields_are_preserved_as_unmapped() -> None:
    normalized = normalize_custom_persona({"likes": ["serums"], "favorite_store": "Example Store"})

    unmapped = normalized["extra_persona_signals"]["unmapped_fields"]
    assert unmapped["favorite_store"] == "Example Store"


def test_meaningless_persona_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=MINIMUM_PERSONA_ERROR):
        normalize_custom_persona({"hello": "world"})


def test_budget_only_persona_counts_as_usable_signal() -> None:
    normalized = normalize_custom_persona({"budget": "high"})

    assert normalized["purchase_behavior"]["price_sensitivity"] == "high"


def test_product_normalizer_maps_common_fields() -> None:
    normalized = normalize_custom_product(
        {
            "name": "Gentle Hydrating Face Cream",
            "category": "Skincare",
            "rating": 4.5,
            "reviews_count": 120,
            "brand": "Example Brand",
            "unknown": "kept",
        }
    )

    assert normalized["title"] == "Gentle Hydrating Face Cream"
    assert normalized["main_category"] == "Skincare"
    assert normalized["categories"] == ["Skincare"]
    assert normalized["average_rating"] == 4.5
    assert normalized["rating_number"] == 120
    assert normalized["store"] == "Example Brand"
    assert normalized["details"]["custom_fields"]["unknown"] == "kept"


def test_meaningless_product_raises_clear_error() -> None:
    with pytest.raises(ValueError, match=MINIMUM_PRODUCT_ERROR):
        normalize_custom_product({"hello": "world"})
