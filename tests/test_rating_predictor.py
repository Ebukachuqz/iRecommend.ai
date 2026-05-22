from src.task_a_simulation.rating_predictor import predict_statistical_rating
from src.task_a_simulation.schema import ProductSnapshot


def persona_with_preferences(disliked=None, strictness="moderate") -> dict:
    return {
        "preferences": {
            "liked_attributes": ["lightweight", "non greasy"],
            "what_they_value": ["value"],
            "disliked_attributes": disliked or [],
            "common_complaints": [],
        },
        "rating_behavior": {
            "average_rating": 3.8,
            "rating_distribution": {"1": 1, "2": 1, "3": 3, "4": 5, "5": 0},
            "strictness": strictness,
        },
        "purchase_behavior": {
            "price_sensitivity": "high",
            "quality_sensitivity": "high",
        },
    }


def test_statistical_prediction_stays_between_one_and_five() -> None:
    product = ProductSnapshot(
        parent_asin="asin-1",
        title="Lightweight non greasy lotion",
        average_rating=4.6,
        rating_number=100,
        price=12,
    )

    result = predict_statistical_rating(persona_with_preferences(), product)

    assert 1 <= result.statistical_predicted_rating <= 5


def test_disliked_attributes_reduce_rating() -> None:
    product = ProductSnapshot(
        parent_asin="asin-1",
        title="Strong fragrance cream",
        features=["strong fragrance"],
        average_rating=4.5,
        rating_number=100,
    )
    neutral = predict_statistical_rating(persona_with_preferences(), product)
    disliked = predict_statistical_rating(persona_with_preferences(disliked=["strong fragrance"]), product)

    assert disliked.statistical_predicted_rating < neutral.statistical_predicted_rating


def test_strictness_lowers_statistical_rating() -> None:
    product = ProductSnapshot(parent_asin="asin-1", title="Good lotion", average_rating=4.8, rating_number=100)

    moderate = predict_statistical_rating(persona_with_preferences(strictness="moderate"), product)
    strict = predict_statistical_rating(persona_with_preferences(strictness="strict"), product)

    assert strict.statistical_predicted_rating < moderate.statistical_predicted_rating
