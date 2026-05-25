from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.evaluate_all import run_all_evaluations
from scripts.evaluate_task_a import evaluate_task_a
from scripts.evaluate_task_b import evaluate_task_b
from src.evaluation.data import (
    popularity_baseline_recommendations,
    select_task_a_examples,
    select_task_b_examples,
    user_average_ratings_from_persona_train,
)
from src.evaluation.metrics import (
    exact_rating_accuracy,
    hit_at_k,
    mae,
    ndcg_at_k,
    reciprocal_rank,
    rmse,
    within_1_star_accuracy,
)
from src.task_b_recommendation.schema import RecommendationIntent, RecommendationOutput, RerankedRecommendation


class Query:
    def __init__(self, client, table: str):
        self.client = client
        self.table = table
        self.filters = []
        self._range = None
        self._limit = None

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, list(values)))
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def limit(self, value):
        self._limit = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self.client.respond(self.table, self.filters, self._range, self._limit))


class FakeClient:
    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = tables

    def table(self, name: str):
        return Query(self, name)

    def respond(self, table: str, filters, range_value, limit_value):
        rows = list(self.tables.get(table, []))
        for kind, column, value in filters:
            if kind == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif kind == "in":
                value_set = set(value)
                rows = [row for row in rows if row.get(column) in value_set]
        if range_value is not None:
            start, end = range_value
            rows = rows[start : end + 1]
        if limit_value is not None:
            rows = rows[:limit_value]
        return rows


def fake_client() -> FakeClient:
    category = "Health_and_Household"
    return FakeClient(
        {
            "amazon_product_metadata": [
                {"parent_asin": "train-1", "category": category, "title": "Training Product", "average_rating": 5.0, "rating_number": 100},
                {"parent_asin": "task-a-1", "category": category, "title": "Task A Product", "average_rating": 4.6, "rating_number": 20},
                {"parent_asin": "task-b-1", "category": category, "title": "Task B Product", "average_rating": 4.9, "rating_number": 80},
                {"parent_asin": "task-b-2", "category": category, "title": "Low Rated Holdout", "average_rating": 4.2, "rating_number": 60},
                {"parent_asin": "pop-1", "category": category, "title": "Popular One", "average_rating": 4.8, "rating_number": 70},
                {"parent_asin": "pop-2", "category": category, "title": "Popular Two", "average_rating": 4.8, "rating_number": 50},
                {"parent_asin": "other-1", "category": "Electronics", "title": "Other Category", "average_rating": 5.0, "rating_number": 500},
            ],
            "amazon_reviews": [
                {"review_id": "r-train-1", "user_id": "u1", "parent_asin": "train-1", "rating": 4, "task_split": "persona_train"},
                {"review_id": "r-train-2", "user_id": "u1", "parent_asin": "pop-2", "rating": 2, "task_split": "persona_train"},
                {"review_id": "r-a-1", "user_id": "u1", "parent_asin": "task-a-1", "rating": 5, "title": "real", "text": "real text", "task_split": "task_a_holdout"},
                {"review_id": "r-a-other", "user_id": "u1", "parent_asin": "other-1", "rating": 1, "task_split": "task_a_holdout"},
                {"review_id": "r-b-1", "user_id": "u2", "parent_asin": "task-b-1", "rating": 5, "task_split": "task_b_holdout"},
                {"review_id": "r-b-low", "user_id": "u2", "parent_asin": "task-b-2", "rating": 3, "task_split": "task_b_holdout"},
                {"review_id": "r-b-no-vector", "user_id": "u3", "parent_asin": "task-b-1", "rating": 5, "task_split": "task_b_holdout"},
            ],
            "user_personas": [
                {"user_id": "u1", "category": category, "persona_version": "v1"},
                {"user_id": "u2", "category": category, "persona_version": "v1"},
                {"user_id": "u3", "category": category, "persona_version": "v1"},
            ],
            "user_preference_vectors": [{"user_id": "u2", "category": category}],
        }
    )


def test_rating_and_ranking_metrics() -> None:
    pairs = [(4.2, 4.0), (2.0, 3.0)]

    assert mae(pairs) == pytest.approx(0.6)
    assert round(rmse(pairs), 4) == 0.7211
    assert exact_rating_accuracy([(4.4, 4.0), (2.2, 3.0)]) == 0.5
    assert within_1_star_accuracy(pairs) == 1.0
    assert hit_at_k(2) is True
    assert ndcg_at_k(2) == pytest.approx(1 / 1.5849625007211563)
    assert reciprocal_rank(4) == 0.25


def test_data_selection_uses_holdouts_category_and_required_artifacts() -> None:
    client = fake_client()

    task_a = select_task_a_examples("Health_and_Household", limit=10, client=client)
    task_b = select_task_b_examples("Health_and_Household", limit=10, client=client)

    assert [item["review"]["review_id"] for item in task_a] == ["r-a-1"]
    assert [item["review"]["review_id"] for item in task_b] == ["r-b-1"]


def test_baselines_use_persona_train_and_popularity_ordering() -> None:
    client = fake_client()

    averages = user_average_ratings_from_persona_train("Health_and_Household", client=client)
    baseline = popularity_baseline_recommendations("u1", "Health_and_Household", 3, client=client)

    assert averages["u1"] == 3
    assert "train-1" not in [row["parent_asin"] for row in baseline]
    assert "pop-2" not in [row["parent_asin"] for row in baseline]
    assert [row["parent_asin"] for row in baseline[:2]] == ["task-b-1", "pop-1"]


def test_task_a_evaluation_writes_outputs_and_records_failures(tmp_path) -> None:
    client = fake_client()

    def failing_simulator(*_args, **_kwargs):
        raise RuntimeError("model unavailable")

    result = evaluate_task_a(
        "Health_and_Household",
        limit=10,
        output_dir=tmp_path,
        client=client,
        simulate_func=failing_simulator,
        timestamp="20260101T000000Z",
    )

    assert result["rows"][0]["status"] == "failed"
    assert result["summary"]["count_failed"] == 1
    assert (tmp_path / "task_a_results_Health_and_Household_20260101T000000Z.csv").exists()
    assert (tmp_path / "task_a_results_Health_and_Household_20260101T000000Z.json").exists()
    assert (tmp_path / "task_a_summary_Health_and_Household_20260101T000000Z.json").exists()


def test_task_b_evaluation_writes_outputs_and_allows_holdout_target(tmp_path) -> None:
    client = fake_client()
    seen_contexts = []

    def fake_recommender(request, **_kwargs):
        seen_contexts.append(request.context)
        return RecommendationOutput(
            user_id=request.user_id,
            category=request.category,
            request=request.request,
            intent=RecommendationIntent(retrieval_query=request.request or ""),
            recommendations=[
                RerankedRecommendation(parent_asin="pop-1", rank=1, title="Popular One", reason="Strong baseline."),
                RerankedRecommendation(parent_asin="task-b-1", rank=2, title="Task B Product", reason="Matches the holdout."),
            ],
            candidate_count=2,
        )

    result = evaluate_task_b(
        "Health_and_Household",
        limit=10,
        k=10,
        output_dir=tmp_path,
        client=client,
        recommend_func=fake_recommender,
        timestamp="20260101T000000Z",
    )

    assert result["rows"][0]["status"] == "success"
    assert result["rows"][0]["rank_of_holdout"] == 2
    assert seen_contexts[0]["evaluation_allowed_parent_asins"] == ["task-b-1"]
    assert (tmp_path / "task_b_results_Health_and_Household_20260101T000000Z.csv").exists()
    assert (tmp_path / "task_b_summary_Health_and_Household_20260101T000000Z.json").exists()


def test_evaluate_all_records_skipped_categories(tmp_path) -> None:
    def empty_runner(**_kwargs):
        return {"summary": {"count_evaluated": 0}, "files": {}}

    result = run_all_evaluations(
        ["Empty_Category"],
        output_dir=tmp_path,
        task_a_runner=empty_runner,
        task_b_runner=empty_runner,
        timestamp="20260101T000000Z",
    )

    assert result["manifest"]["category_runs"][0]["status"] == "skipped"
    assert (tmp_path / "evaluation_manifest_20260101T000000Z.json").exists()
