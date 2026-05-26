import logging

from src.task_b_recommendation.service import store_recommendation_run
from src.task_b_recommendation.schema import RecommendationIntent, RecommendationOutput, RerankedRecommendation


class RecordingTable:
    def __init__(self, name: str, fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.payloads = []

    def insert(self, payload):
        self.payloads.append(payload)
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError(f"{self.name} insert failed")
        payload = self.payloads[-1]
        if self.name == "recommendation_runs":
            return type("Response", (), {"data": [{**payload, "id": "run-1"}]})()
        return type("Response", (), {"data": [payload]})()


class RecordingClient:
    def __init__(self, fail_tables: set[str] | None = None) -> None:
        fail_tables = fail_tables or set()
        self.tables = {
            name: RecordingTable(name, fail=name in fail_tables)
            for name in ["recommendation_runs", "intent_plans", "recommendation_candidates"]
        }

    def table(self, name):
        return self.tables[name]


def make_output() -> RecommendationOutput:
    return RecommendationOutput(
        user_id="user-1",
        category="Electronics",
        request="gentle skincare",
        intent=RecommendationIntent(
            interpreted_need="gentle skincare",
            explicit_constraints={"need": "gentle"},
            implicit_constraints_from_persona={"avoid": "fragrance"},
            retrieval_query="gentle skincare",
            avoid=["strong fragrance"],
            category_filter="All_Beauty",
            price_max=25,
            required_attributes=["gentle"],
            excluded_attributes=["fragrance"],
        ),
        recommendations=[
            RerankedRecommendation(parent_asin="asin-2", rank=1, title="Second", reason="Best fit."),
            RerankedRecommendation(parent_asin="asin-top", rank=2, title="Top", reason="Good fit."),
        ],
        candidate_count=50,
        session_id="session-1",
        model_name="test-model",
        prompt_version="intent-v1+rerank-v1",
    )


def make_scored_candidates() -> list[dict]:
    return [
        {
            "parent_asin": "asin-top",
            "retrieval_source": "preference_vector",
            "retrieval_sources": ["preference_vector", "request_query"],
            "semantic_similarity": 0.9,
            "collaborative_similarity": 0.7,
            "score_breakdown": {
                "final_score": 0.91,
                "preference_match": 0.8,
                "product_quality": 0.9,
                "price_fit": 0.7,
                "popularity_reliability": 0.6,
            },
        },
        {
            "parent_asin": "asin-2",
            "retrieval_source": "attribute_match",
            "retrieval_sources": ["attribute_match"],
            "semantic_similarity": 0.4,
            "collaborative_similarity": None,
            "score_breakdown": {
                "final_score": 0.85,
                "preference_match": 0.95,
                "product_quality": 0.8,
                "price_fit": 0.65,
                "popularity_reliability": 0.4,
            },
        },
        {
            "parent_asin": "asin-3",
            "retrieval_source": "quality_fallback",
            "retrieval_sources": ["quality_fallback"],
            "semantic_similarity": 0.0,
            "collaborative_similarity": None,
            "score_breakdown": {
                "final_score": 0.5,
                "preference_match": 0.3,
                "product_quality": 0.7,
                "price_fit": 0.5,
                "popularity_reliability": 0.9,
            },
        },
    ]


def test_recommendation_run_counts_retrieval_sources_from_full_candidate_pool() -> None:
    output = make_output()
    candidates = []
    candidates.extend({"parent_asin": f"pref-{index}", "retrieval_source": "preference_vector"} for index in range(25))
    candidates.extend({"parent_asin": f"query-{index}", "retrieval_source": "request_query"} for index in range(15))
    candidates.extend({"parent_asin": f"fallback-{index}", "retrieval_source": "quality_fallback"} for index in range(10))
    client = RecordingClient()

    payload = store_recommendation_run(output, {"scored_candidates": candidates}, client=client)

    assert payload["retrieval_sources"] == {
        "preference_vector": 25,
        "request_query": 15,
        "quality_fallback": 10,
    }
    assert payload["top_asin"] == "asin-2"


def test_intent_plan_trace_writes_expected_fields() -> None:
    client = RecordingClient()

    store_recommendation_run(make_output(), {"scored_candidates": make_scored_candidates()}, client=client)

    payload = client.tables["intent_plans"].payloads[0]
    assert set(payload) == {
        "recommendation_run_id",
        "session_id",
        "user_id",
        "category",
        "raw_request",
        "interpreted_need",
        "explicit_constraints",
        "implicit_constraints",
        "retrieval_query",
        "avoid",
        "category_filter",
        "price_max",
        "required_attributes",
        "excluded_attributes",
        "model_name",
        "prompt_version",
    }
    assert payload["recommendation_run_id"] == "run-1"
    assert payload["category"] == "Electronics"
    assert payload["implicit_constraints"] == {"avoid": "fragrance"}
    assert payload["prompt_version"] == "intent-v1+rerank-v1"


def test_recommendation_run_stores_output_category() -> None:
    client = RecordingClient()

    payload = store_recommendation_run(make_output(), {"scored_candidates": make_scored_candidates()}, client=client)

    assert payload["category"] == "Electronics"


def test_recommendation_run_stores_evaluation_metadata_when_present() -> None:
    client = RecordingClient()

    payload = store_recommendation_run(
        make_output(),
        {
            "evaluation_metadata": {"is_evaluation_run": True, "holdout_asin": "holdout-1"},
            "hit_at_10": True,
            "rank_of_holdout": 3,
            "scored_candidates": make_scored_candidates(),
        },
        client=client,
    )

    assert payload["is_evaluation_run"] is True
    assert payload["holdout_asin"] == "holdout-1"
    assert payload["hit_at_10"] is True
    assert payload["rank_of_holdout"] == 3


def test_candidate_traces_are_inserted_in_one_batch_with_ranks() -> None:
    client = RecordingClient()

    store_recommendation_run(make_output(), {"scored_candidates": make_scored_candidates()}, client=client)

    table = client.tables["recommendation_candidates"]
    assert len(table.payloads) == 1
    rows = table.payloads[0]
    assert len(rows) == 3
    assert set(rows[0]) == {
        "recommendation_run_id",
        "parent_asin",
        "candidate_rank",
        "rank_before_rerank",
        "rank_after_rerank",
        "retrieval_source",
        "retrieval_sources",
        "semantic_similarity",
        "collaborative_similarity",
        "preference_match",
        "product_quality",
        "price_fit",
        "popularity_reliability",
        "final_score",
        "score_breakdown",
    }
    assert rows[0]["recommendation_run_id"] == "run-1"
    assert rows[0]["parent_asin"] == "asin-top"
    assert rows[0]["candidate_rank"] == 1
    assert rows[0]["rank_before_rerank"] == 1
    assert rows[0]["rank_after_rerank"] == 2
    assert rows[0]["retrieval_sources"] == ["preference_vector", "request_query"]
    assert rows[0]["collaborative_similarity"] == 0.7
    assert rows[0]["preference_match"] == 0.8
    assert rows[0]["product_quality"] == 0.9
    assert rows[0]["price_fit"] == 0.7
    assert rows[0]["popularity_reliability"] == 0.6
    assert rows[0]["final_score"] == 0.91
    assert rows[0]["score_breakdown"]["preference_match"] == 0.8
    assert rows[1]["rank_after_rerank"] == 1
    assert rows[1]["collaborative_similarity"] is None
    assert rows[2]["rank_after_rerank"] is None


def test_trace_persistence_failures_do_not_crash_recommendation_run(caplog) -> None:
    client = RecordingClient(fail_tables={"intent_plans", "recommendation_candidates"})

    with caplog.at_level(logging.WARNING):
        payload = store_recommendation_run(make_output(), {"scored_candidates": make_scored_candidates()}, client=client)

    assert payload["id"] == "run-1"
    assert "Failed to persist Task B intent plan trace" in caplog.text
    assert "Failed to persist Task B candidate traces" in caplog.text
