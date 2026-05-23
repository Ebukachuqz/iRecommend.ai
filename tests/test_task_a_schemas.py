import pytest
from pydantic import ValidationError

from src.task_a_simulation.schema import (
    LLMReviewSimulationOutput,
    ProductSnapshot,
    ReviewSimulationOutput,
)


def test_product_snapshot_coerces_metadata_fields() -> None:
    product = ProductSnapshot.model_validate(
        {
            "parent_asin": "asin-1",
            "title": "Lightweight lotion",
            "features": "non greasy",
            "description": None,
            "details": "not-json",
        }
    )

    assert product.features == ["non greasy"]
    assert product.description == []
    assert product.details == {}


def test_invalid_llm_rating_fails_validation() -> None:
    with pytest.raises(ValidationError):
        LLMReviewSimulationOutput.model_validate(
            {
                "llm_predicted_rating": 6,
                "simulated_review_title": "Too much",
                "simulated_review_text": "Too much",
                "reasoning_summary": "Invalid high rating.",
                "evidence_used": [],
            }
        )


def test_review_output_carries_nigerian_mode_flag(sample_rating_breakdown) -> None:
    output = ReviewSimulationOutput(
        user_id=None,
        category="All_Beauty",
        parent_asin="asin-1",
        llm_predicted_rating=4,
        statistical_predicted_rating=3.8,
        final_predicted_rating=3.9,
        simulated_review_title="Good",
        simulated_review_text="Good enough for the price.",
        reasoning_summary="Matches value preference.",
        rating_breakdown=sample_rating_breakdown,
        nigerian_mode=True,
    )

    assert output.nigerian_mode is True
    assert output.user_id is None
