import pytest

from src.task_a_simulation.schema import RatingPredictionBreakdown


@pytest.fixture
def sample_rating_breakdown() -> RatingPredictionBreakdown:
    return RatingPredictionBreakdown(
        user_average_rating=3.8,
        product_average_rating=4.5,
        preference_match_score=0.3,
        disliked_attribute_penalty=0.0,
        price_fit_score=0.0,
        strictness_adjustment=0.0,
        statistical_predicted_rating=4.2,
        explanation="test",
    )
