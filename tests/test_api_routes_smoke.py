from fastapi.testclient import TestClient

from app.api.dependencies import get_db_client
from app.api.main import app
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


def client_with_overrides() -> TestClient:
    app.dependency_overrides[get_db_client] = lambda: DummyClient()
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_reviews_simulate_rejects_missing_user_id() -> None:
    response = client_with_overrides().post("/reviews/simulate", json={"parent_asin": "asin-1"})

    assert response.status_code == 422


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
