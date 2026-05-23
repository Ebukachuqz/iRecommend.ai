from fastapi.testclient import TestClient

from app.api.dependencies import get_db_client
from app.api.main import app
from src.task_a_simulation.schema import ReviewSimulationOutput, RatingPredictionBreakdown
from src.task_b_recommendation.schema import RecommendationIntent, RecommendationOutput, RerankedRecommendation


class DummyClient:
    pass


def make_recommendation_output(user_id: str | None = "user-1", cold_start: bool = False) -> RecommendationOutput:
    return RecommendationOutput(
        user_id=user_id,
        category="All_Beauty",
        request="affordable skincare",
        intent=RecommendationIntent(
            interpreted_need="affordable skincare",
            retrieval_query="affordable skincare",
            required_attributes=["skincare"],
        ),
        recommendations=[
            RerankedRecommendation(
                parent_asin="asin-1",
                rank=1,
                title="Gentle Toner",
                reason="Matches skincare request.",
                confidence=0.8,
                evidence=["skincare"],
                score_breakdown={"final_score": 0.8},
            )
        ],
        candidate_count=1,
        cold_start=cold_start,
        model_name="test-model",
        prompt_version="test-prompt",
    )


def make_simulation_output() -> ReviewSimulationOutput:
    return ReviewSimulationOutput(
        user_id=None,
        category="Custom",
        parent_asin="custom_product",
        product_title="Gentle Cream",
        llm_predicted_rating=4.0,
        statistical_predicted_rating=4.1,
        final_predicted_rating=4.05,
        simulated_review_title="Nice",
        simulated_review_text="This feels gentle and hydrating.",
        reasoning_summary="Matches custom persona.",
        rating_breakdown=RatingPredictionBreakdown(
            user_average_rating=4.2,
            product_average_rating=4.5,
            statistical_predicted_rating=4.1,
            explanation="test",
        ),
    )


def client_with_overrides() -> TestClient:
    app.dependency_overrides[get_db_client] = lambda: DummyClient()
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_reviews_simulate_rejects_missing_user_id() -> None:
    response = client_with_overrides().post("/reviews/simulate", json={"parent_asin": "asin-1"})

    assert response.status_code == 400


def test_reviews_simulate_accepts_custom_persona_and_product(monkeypatch) -> None:
    from app.api.routers import simulate

    calls = []

    def fail_db_client():
        raise AssertionError("Custom Task A route should not initialize Supabase")

    def fake_simulate_review(request, client=None):
        calls.append(client)
        return make_simulation_output()

    monkeypatch.setattr(simulate, "get_db_client", fail_db_client)
    monkeypatch.setattr(simulate.task_a_service, "simulate_review", fake_simulate_review)

    response = client_with_overrides().post(
        "/reviews/simulate",
        json={
            "persona": {"likes": ["hydrating skincare"]},
            "product": {"name": "Gentle Cream", "features": ["hydrating"]},
        },
    )

    assert response.status_code == 200
    assert response.json()["user_id"] is None
    assert response.json()["parent_asin"] == "custom_product"
    assert calls == [None]


def test_recommendations_generate_accepts_user_id_request(monkeypatch) -> None:
    from app.api.routers import recommend

    monkeypatch.setattr(recommend.recommendation_service, "recommend", lambda request, client=None: make_recommendation_output(request.user_id))

    response = client_with_overrides().post(
        "/recommendations/generate",
        json={"user_id": "user-1", "request": "affordable skincare", "limit": 1},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == "user-1"
    assert response.json()["recommendations"][0]["parent_asin"] == "asin-1"


def test_recommendations_cold_start_accepts_request(monkeypatch) -> None:
    from app.api.routers import recommend

    monkeypatch.setattr(recommend.recommendation_service, "recommend", lambda request, client=None: make_recommendation_output(None, True))

    response = client_with_overrides().post(
        "/recommendations/cold-start",
        json={"request": "I need affordable skincare for oily skin", "limit": 1},
    )

    assert response.status_code == 200
    assert response.json()["cold_start"] is True


def test_recommendations_generate_accepts_persona_only(monkeypatch) -> None:
    from app.api.routers import recommend

    monkeypatch.setattr(recommend.recommendation_service, "recommend", lambda request, client=None: make_recommendation_output(None, True))

    response = client_with_overrides().post(
        "/recommendations/generate",
        json={"persona": {"likes": ["hydrating skincare"]}, "request": "gentle moisturizer", "limit": 1},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] is None
