from src.task_b_recommendation.service import store_recommendation_run
from src.task_b_recommendation.schema import RecommendationIntent, RecommendationOutput, RerankedRecommendation


class DummyInsert:
    def __init__(self) -> None:
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return type("Response", (), {"data": [self.payload]})()


class DummyClient:
    def __init__(self) -> None:
        self.insert = DummyInsert()

    def table(self, name):
        assert name == "recommendation_runs"
        return self.insert


def test_recommendation_run_counts_retrieval_sources_from_full_candidate_pool() -> None:
    output = RecommendationOutput(
        user_id="user-1",
        category="All_Beauty",
        request="gentle skincare",
        intent=RecommendationIntent(retrieval_query="gentle skincare"),
        recommendations=[
            RerankedRecommendation(parent_asin="asin-top", rank=1, title="Top", reason="Best fit."),
            RerankedRecommendation(parent_asin="asin-2", rank=2, title="Second", reason="Good fit."),
        ],
        candidate_count=50,
    )
    candidates = []
    candidates.extend({"parent_asin": f"taste-{index}", "retrieval_source": "taste_vector"} for index in range(25))
    candidates.extend({"parent_asin": f"query-{index}", "retrieval_source": "request_query"} for index in range(15))
    candidates.extend({"parent_asin": f"fallback-{index}", "retrieval_source": "quality_fallback"} for index in range(10))
    client = DummyClient()

    payload = store_recommendation_run(output, {"scored_candidates": candidates}, client=client)

    assert payload["retrieval_sources"] == {
        "taste_vector": 25,
        "request_query": 15,
        "quality_fallback": 10,
    }
    assert payload["top_asin"] == "asin-top"
