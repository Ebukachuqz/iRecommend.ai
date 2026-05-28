from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.task_b_recommendation.graph import candidate_trace_rows, inject_evaluation_holdout
from src.task_b_recommendation.schema import (
    RecommendationCandidate,
    RecommendationIntent,
    RecommendationOutput,
    RecommendationRequest,
    RerankedRecommendation,
)


def _make_candidate(parent_asin: str, sources: list[str] | None = None) -> RecommendationCandidate:
    return RecommendationCandidate(
        parent_asin=parent_asin,
        title=f"Product {parent_asin}",
        product={"parent_asin": parent_asin, "category": "Electronics"},
        semantic_similarity=0.5,
        retrieval_source=sources[0] if sources else "preference_vector",
        retrieval_sources=sources or ["preference_vector"],
    )


def _make_request(
    evaluation_mode: bool = False,
    holdout_asin: str | None = None,
    category: str = "Electronics",
) -> RecommendationRequest:
    return RecommendationRequest(
        user_id="U1",
        category=category,
        request="Recommend products",
        evaluation_mode=evaluation_mode,
        holdout_asin=holdout_asin,
    )


@patch("src.task_b_recommendation.graph.fetch_products_by_parent_asins")
def test_injects_holdout_when_absent(mock_fetch):
    mock_fetch.return_value = {
        "HOLDOUT1": {"parent_asin": "HOLDOUT1", "title": "Holdout Product", "category": "Electronics"}
    }
    request = _make_request(evaluation_mode=True, holdout_asin="HOLDOUT1")
    candidates = [_make_candidate("A1"), _make_candidate("A2")]
    source_counts = {"preference_vector": 2}
    reviewed = set()
    client = MagicMock()

    result_candidates, result_counts = inject_evaluation_holdout(
        request, candidates, source_counts, reviewed, client,
    )

    holdout_asins = [c.parent_asin for c in result_candidates if c.parent_asin == "HOLDOUT1"]
    assert len(holdout_asins) == 1
    holdout = [c for c in result_candidates if c.parent_asin == "HOLDOUT1"][0]
    assert "evaluation_holdout" in holdout.retrieval_sources
    assert result_counts.get("evaluation_holdout") == 1


@patch("src.task_b_recommendation.graph.fetch_products_by_parent_asins")
def test_tags_existing_holdout(mock_fetch):
    request = _make_request(evaluation_mode=True, holdout_asin="A1")
    candidates = [_make_candidate("A1", ["preference_vector"]), _make_candidate("A2")]
    source_counts = {"preference_vector": 2}
    reviewed = set()
    client = MagicMock()

    result_candidates, _ = inject_evaluation_holdout(
        request, candidates, source_counts, reviewed, client,
    )

    holdout = [c for c in result_candidates if c.parent_asin == "A1"][0]
    assert "evaluation_holdout" in holdout.retrieval_sources
    assert "preference_vector" in holdout.retrieval_sources
    mock_fetch.assert_not_called()


def test_normal_mode_no_injection():
    request = _make_request(evaluation_mode=False, holdout_asin="HOLDOUT1")
    candidates = [_make_candidate("A1")]
    source_counts = {"preference_vector": 1}
    reviewed = set()
    client = MagicMock()

    result_candidates, _ = inject_evaluation_holdout(
        request, candidates, source_counts, reviewed, client,
    )

    assert len(result_candidates) == 1
    assert result_candidates[0].parent_asin == "A1"


@patch("src.task_b_recommendation.graph.fetch_products_by_parent_asins")
def test_no_injection_if_persona_train_excluded(mock_fetch):
    request = _make_request(evaluation_mode=True, holdout_asin="HOLDOUT1")
    candidates = [_make_candidate("A1")]
    source_counts = {"preference_vector": 1}
    reviewed = {"HOLDOUT1"}
    client = MagicMock()

    result_candidates, _ = inject_evaluation_holdout(
        request, candidates, source_counts, reviewed, client,
    )

    assert len(result_candidates) == 1
    mock_fetch.assert_not_called()


@patch("src.task_b_recommendation.graph.fetch_products_by_parent_asins")
def test_no_injection_if_category_mismatch(mock_fetch):
    mock_fetch.return_value = {
        "HOLDOUT1": {"parent_asin": "HOLDOUT1", "title": "Wrong", "category": "Beauty_and_Personal_Care"}
    }
    request = _make_request(evaluation_mode=True, holdout_asin="HOLDOUT1", category="Electronics")
    candidates = [_make_candidate("A1")]
    source_counts = {"preference_vector": 1}
    reviewed = set()
    client = MagicMock()

    result_candidates, result_counts = inject_evaluation_holdout(
        request, candidates, source_counts, reviewed, client,
    )

    assert len(result_candidates) == 1
    assert "evaluation_holdout" not in result_counts


@patch("src.task_b_recommendation.graph.fetch_products_by_parent_asins")
def test_no_injection_if_product_not_found(mock_fetch):
    mock_fetch.return_value = {}
    request = _make_request(evaluation_mode=True, holdout_asin="MISSING")
    candidates = [_make_candidate("A1")]
    source_counts = {"preference_vector": 1}
    reviewed = set()
    client = MagicMock()

    result_candidates, _ = inject_evaluation_holdout(
        request, candidates, source_counts, reviewed, client,
    )

    assert len(result_candidates) == 1


@patch("src.task_b_recommendation.graph.fetch_products_by_parent_asins")
def test_injected_holdout_not_forced_into_top_k(mock_fetch):
    mock_fetch.return_value = {
        "HOLDOUT1": {"parent_asin": "HOLDOUT1", "title": "Holdout", "category": "Electronics"}
    }
    request = _make_request(evaluation_mode=True, holdout_asin="HOLDOUT1")
    candidates = [_make_candidate(f"A{i}") for i in range(10)]
    source_counts = {"preference_vector": 10}
    reviewed = set()
    client = MagicMock()

    result_candidates, _ = inject_evaluation_holdout(
        request, candidates, source_counts, reviewed, client,
    )

    holdout = [c for c in result_candidates if c.parent_asin == "HOLDOUT1"][0]
    assert holdout.semantic_similarity == 0.0
    assert len(result_candidates) == 11


def test_no_holdout_asin_no_injection():
    request = _make_request(evaluation_mode=True, holdout_asin=None)
    candidates = [_make_candidate("A1")]
    source_counts = {"preference_vector": 1}
    reviewed = set()
    client = MagicMock()

    result_candidates, _ = inject_evaluation_holdout(
        request, candidates, source_counts, reviewed, client,
    )

    assert len(result_candidates) == 1


@patch("src.task_b_recommendation.graph.fetch_products_by_parent_asins")
def test_injects_holdout_from_evaluation_context(mock_fetch):
    mock_fetch.return_value = {
        "HOLDOUT1": {"parent_asin": "HOLDOUT1", "title": "Holdout Product", "category": "Electronics"}
    }
    request = RecommendationRequest(
        user_id="U1",
        category="Electronics",
        request="Recommend products",
        context={"evaluation": True, "evaluation_holdout_parent_asin": "HOLDOUT1"},
    )
    candidates = [_make_candidate("A1")]
    source_counts = {"preference_vector": 1}
    reviewed = set()
    client = MagicMock()

    result_candidates, result_counts = inject_evaluation_holdout(
        request, candidates, source_counts, reviewed, client,
    )

    holdout = [c for c in result_candidates if c.parent_asin == "HOLDOUT1"][0]
    assert holdout.retrieval_sources == ["evaluation_holdout"]
    assert result_counts.get("evaluation_holdout") == 1


def test_candidate_trace_rows_include_evaluation_holdout_candidate():
    output = RecommendationOutput(
        user_id="U1",
        category="Electronics",
        request="Recommend products",
        intent=RecommendationIntent(retrieval_query="Recommend products"),
        recommendations=[
            RerankedRecommendation(
                parent_asin="A1",
                rank=1,
                title="Selected Product",
                reason="Best match.",
            )
        ],
        candidate_count=2,
    )
    context = {
        "scored_candidates": [
            {
                "parent_asin": "A1",
                "retrieval_source": "preference_vector",
                "retrieval_sources": ["preference_vector"],
                "semantic_similarity": 0.8,
                "score_breakdown": {
                    "preference_match": 0.8,
                    "product_quality": 0.7,
                    "price_fit": 0.6,
                    "popularity_reliability": 0.5,
                    "final_score": 0.75,
                },
            },
            {
                "parent_asin": "HOLDOUT1",
                "retrieval_source": "evaluation_holdout",
                "retrieval_sources": ["evaluation_holdout"],
                "semantic_similarity": 0.0,
                "score_breakdown": {
                    "preference_match": 0.2,
                    "product_quality": 0.4,
                    "price_fit": 0.5,
                    "popularity_reliability": 0.3,
                    "final_score": 0.25,
                },
            },
        ]
    }

    rows = candidate_trace_rows(output, context, recommendation_run_id="run-1")

    holdout = [row for row in rows if row["parent_asin"] == "HOLDOUT1"][0]
    assert holdout["retrieval_source"] == "evaluation_holdout"
    assert holdout["retrieval_sources"] == ["evaluation_holdout"]
    assert holdout["rank_before_rerank"] == 2
    assert holdout["rank_after_rerank"] is None
    assert holdout["final_score"] == 0.25
