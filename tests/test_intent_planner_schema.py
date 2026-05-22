from src.task_b_recommendation.cold_start import build_cold_start_persona
from src.task_b_recommendation.intent_planner import fallback_intent
from src.task_b_recommendation.schema import RecommendationIntent


def test_cold_start_request_can_produce_intent_schema() -> None:
    persona = build_cold_start_persona("I need affordable skincare for oily skin")
    intent = fallback_intent("I need affordable skincare for oily skin", persona)

    assert isinstance(intent, RecommendationIntent)
    assert "affordable" in intent.interpreted_need
    assert persona["purchase_behavior"]["price_sensitivity"] == "high"
