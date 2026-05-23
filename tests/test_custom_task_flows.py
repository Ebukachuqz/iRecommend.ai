from src.task_a_simulation import service as task_a_service
from src.task_a_simulation.schema import LLMReviewSimulationOutput, ReviewSimulationRequest
from src.task_b_recommendation import service as task_b_service
from src.task_b_recommendation.schema import RecommendationIntent, RecommendationRequest


class DummyInsert:
    def insert(self, _payload):
        return self

    def execute(self):
        return type("Response", (), {"data": [{}]})()


class DummyClient:
    def table(self, _name):
        return DummyInsert()


def test_task_a_custom_request_works_without_user_id(monkeypatch) -> None:
    monkeypatch.setattr(
        task_a_service,
        "generate_llm_review_and_rating",
        lambda *args, **kwargs: LLMReviewSimulationOutput(
            llm_predicted_rating=4.0,
            simulated_review_title="Gentle and hydrating",
            simulated_review_text="This matches the dry skin preference well.",
            confidence=0.8,
            reasoning_summary="Custom persona and product matched.",
            evidence_used=["hydrating", "dry skin"],
        ),
    )

    output = task_a_service.simulate_review(
        ReviewSimulationRequest(
            persona={"likes": ["hydrating skincare"], "average_rating": 4.2},
            product={"name": "Gentle Hydrating Face Cream", "features": ["for dry skin"], "rating": 4.5},
            category="Custom",
        ),
        client=DummyClient(),
    )

    assert output.user_id is None
    assert output.parent_asin == "custom_product"
    assert output.product_title == "Gentle Hydrating Face Cream"


def test_task_a_rejects_missing_user_id_and_missing_custom_payload() -> None:
    try:
        task_a_service.simulate_review(ReviewSimulationRequest(parent_asin="asin-1"), client=DummyClient())
    except task_a_service.TaskAServiceError as exc:
        assert "Task A requires either user_id" in str(exc)
    else:
        raise AssertionError("Expected TaskAServiceError")


def test_task_b_persona_only_request_uses_custom_persona(monkeypatch) -> None:
    monkeypatch.setattr(
        task_b_service,
        "plan_intent",
        lambda persona, request, session_state=None: RecommendationIntent(retrieval_query=request or ""),
    )
    monkeypatch.setattr(task_b_service, "retrieve_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(task_b_service, "score_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(task_b_service, "rerank_recommendations", lambda *args, **kwargs: type("Reranked", (), {"recommendations": []})())
    monkeypatch.setattr(task_b_service, "store_recommendation_run", lambda *args, **kwargs: {})

    output = task_b_service.recommend(
        RecommendationRequest(persona={"likes": ["hydrating skincare"]}, request="gentle moisturizer"),
        client=DummyClient(),
    )

    assert output.user_id is None
    assert output.cold_start is True
