from src.task_a_simulation import service as task_a_service
from src.task_a_simulation.schema import LLMReviewSimulationOutput, ReviewSimulationRequest
from src.task_b_recommendation import graph as task_b_graph
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


CUSTOM_PERSONA = {
    "writing_style": {"tone": "casual", "length": "medium", "detail_level": "medium", "formality": "mixed"},
    "preferences": {
        "liked_product_types": ["moisturizers"],
        "disliked_product_types": [],
        "liked_attributes": ["hydrating"],
        "disliked_attributes": ["strong fragrance"],
        "what_they_value": ["gentle skincare"],
        "common_complaints": ["dry skin"],
    },
    "rating_behavior": {
        "average_rating": 4.2,
        "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 2, "5": 3},
        "strictness": "moderate",
        "rating_patterns": "likes useful detail",
    },
    "purchase_behavior": {
        "preferred_categories": ["skincare"],
        "price_sensitivity": "medium",
        "quality_sensitivity": "medium",
        "verified_purchase_ratio": 0.0,
    },
    "cultural_signals": "none detected",
    "evidence": {"positive_examples": [], "negative_examples": []},
    "extra_persona_signals": {},
}

CUSTOM_PRODUCT = {
    "parent_asin": "custom_product",
    "title": "Gentle Hydrating Face Cream",
    "main_category": "Skincare",
    "categories": ["Skincare"],
    "price": 18.99,
    "features": ["for dry skin"],
    "description": ["A gentle hydrating cream."],
    "average_rating": 4.5,
    "rating_number": 120,
    "store": "Example",
    "details": {},
}


def test_task_a_custom_request_works_without_user_id(monkeypatch) -> None:
    persona_calls = []
    product_calls = []
    monkeypatch.setattr(
        task_a_service,
        "process_custom_persona",
        lambda raw: persona_calls.append(raw) or CUSTOM_PERSONA,
    )
    monkeypatch.setattr(
        task_a_service,
        "process_custom_product",
        lambda raw: product_calls.append(raw) or CUSTOM_PRODUCT,
    )
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
    assert persona_calls
    assert product_calls


def test_task_a_rejects_missing_user_id_and_missing_custom_payload() -> None:
    try:
        task_a_service.simulate_review(ReviewSimulationRequest(parent_asin="asin-1"), client=DummyClient())
    except task_a_service.TaskAServiceError as exc:
        assert "Task A requires either user_id" in str(exc)
    else:
        raise AssertionError("Expected TaskAServiceError")


def test_task_b_persona_only_request_uses_custom_persona(monkeypatch) -> None:
    persona_calls = []
    monkeypatch.setattr(
        task_b_graph,
        "process_custom_persona",
        lambda raw: persona_calls.append(raw) or CUSTOM_PERSONA,
    )
    monkeypatch.setattr(
        task_b_graph,
        "plan_intent",
        lambda persona, request, session_state=None: RecommendationIntent(retrieval_query=request or ""),
    )
    monkeypatch.setattr(
        task_b_graph,
        "retrieve_candidates_with_sources",
        lambda *args, **kwargs: type("RetrievalResult", (), {"candidates": [], "source_counts": {}})(),
    )
    monkeypatch.setattr(task_b_graph, "score_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(task_b_graph, "rerank_recommendations", lambda *args, **kwargs: type("Reranked", (), {"recommendations": []})())
    monkeypatch.setattr(task_b_graph, "store_recommendation_run", lambda *args, **kwargs: {})
    monkeypatch.setattr(task_b_graph, "get_settings", lambda: type("Settings", (), {"groq_model": "test-model"})())

    output = task_b_service.recommend(
        RecommendationRequest(persona={"likes": ["hydrating skincare"]}, request="gentle moisturizer"),
        client=DummyClient(),
    )

    assert output.user_id is None
    assert output.cold_start is True
    assert persona_calls
