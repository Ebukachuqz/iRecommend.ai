from app.api.models.requests import (
    ColdStartRecommendationAPIRequest,
    RecommendationAPIRequest,
    ReviewSimulationAPIRequest,
    SessionMessageRequest,
)


def test_review_simulation_request_accepts_custom_mode_without_user_id() -> None:
    request = ReviewSimulationAPIRequest(persona={"likes": ["hydrating"]}, product={"name": "Cream"})

    assert request.user_id is None
    assert request.persona == {"likes": ["hydrating"]}


def test_review_simulation_request_accepts_custom_text_inputs() -> None:
    request = ReviewSimulationAPIRequest(
        persona="I like gentle skincare.",
        product="A fragrance-free hydrating face cream.",
    )

    assert request.persona == "I like gentle skincare."
    assert request.product == "A fragrance-free hydrating face cream."


def test_recommendation_request_accepts_user_id() -> None:
    request = RecommendationAPIRequest(user_id="user-1", request="gentle toner")

    assert request.user_id == "user-1"
    assert request.limit == 5


def test_recommendation_request_accepts_custom_text_persona() -> None:
    request = RecommendationAPIRequest(persona="I prefer affordable fragrance-free moisturizers.")

    assert request.persona == "I prefer affordable fragrance-free moisturizers."


def test_cold_start_request_requires_request_text() -> None:
    payload = ColdStartRecommendationAPIRequest(request="affordable skincare")

    assert payload.request == "affordable skincare"


def test_session_message_request_validates_message() -> None:
    payload = SessionMessageRequest(message="something cheaper", user_id="user-1")

    assert payload.message == "something cheaper"
