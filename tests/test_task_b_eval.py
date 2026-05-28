from __future__ import annotations

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.task_b_eval import run_task_b_eval


@pytest.fixture
def mock_supabase():
    return MagicMock()


@patch("src.evaluation.task_b_eval.evaluate_task_b_row")
@patch("src.evaluation.task_b_eval._fetch_persona_train_asins")
@patch("src.evaluation.task_b_eval._fetch_personas_batch")
@patch("src.evaluation.task_b_eval._fetch_products_batch")
@patch("src.evaluation.task_b_eval.fetch_task_b_holdout_reviews")
def test_task_b_eval_skips_invalid_rows_and_hits_valid_limit(
    mock_fetch_reviews, mock_fetch_products, mock_fetch_personas,
    mock_fetch_train, mock_evaluate, mock_supabase
):
    mock_fetch_reviews.return_value = [
        {"user_id": "U1", "parent_asin": "A1", "category": "Electronics", "review_id": "R1", "rating": 5},
        {"user_id": "U2", "parent_asin": "A2", "category": "Electronics", "review_id": "R2", "rating": 5},
        {"user_id": "U3", "parent_asin": "A3", "category": "Electronics", "review_id": "R3", "rating": 5},
    ]

    mock_fetch_products.return_value = {
        "A1": {"parent_asin": "A1", "category": "Electronics", "title": "P1"},
        "A2": {"parent_asin": "A2", "category": "Electronics", "title": "P2"},
        "A3": {"parent_asin": "A3", "category": "Electronics", "title": "P3"},
    }

    mock_fetch_personas.return_value = {
        ("U1", "Electronics"): {"persona": "P1"},
        ("U2", "Electronics"): {"persona": "P2"},
        ("U3", "Electronics"): {"persona": "P3"},
    }

    # U1 has A1 in train set. U2 does not. U3 does not.
    mock_fetch_train.return_value = {
        "U1": ["A1"],
        "U2": [],
        "U3": [],
    }

    mock_evaluate.return_value = {
        "status": "success", 
        "recommendation_run_id": "run_123",
        "candidate_count": 100,
        "holdout_in_candidate_pool": True,
        "hit_at_10": 1, 
        "rank_of_holdout": 1, 
        "ndcg_score": 1, 
        "reciprocal_rank": 1
    }

    # Request limit of 1 valid row
    rows, summary = run_task_b_eval(["Electronics"], limit=1, supabase_client=mock_supabase)

    assert summary["total_evaluated"] == 1
    assert summary["total_skipped"] == 1
    assert summary["skipped_holdout_in_persona_train"] == 1
    assert summary["total_scanned"] == 2

    # Should have processed R1 (skipped) and R2 (success) and stopped before R3.
    assert len(rows) == 2
    assert rows[0]["status"] == "skipped"
    assert rows[0]["error_message"] == "holdout product already appears in persona_train"
    assert rows[1]["status"] == "success"
    assert mock_evaluate.call_count == 1


@patch("src.evaluation.task_b_eval.evaluate_task_b_row")
@patch("src.evaluation.task_b_eval._fetch_persona_train_asins")
@patch("src.evaluation.task_b_eval._fetch_personas_batch")
@patch("src.evaluation.task_b_eval._fetch_products_batch")
@patch("src.evaluation.task_b_eval.fetch_task_b_holdout_reviews")
def test_task_b_eval_skips_failed_recommendation_and_missing_pool(
    mock_fetch_reviews, mock_fetch_products, mock_fetch_personas,
    mock_fetch_train, mock_evaluate, mock_supabase
):
    mock_fetch_reviews.return_value = [
        {"user_id": "U1", "parent_asin": "A1", "category": "Electronics", "review_id": "R1", "rating": 5},
        {"user_id": "U2", "parent_asin": "A2", "category": "Electronics", "review_id": "R2", "rating": 5},
        {"user_id": "U3", "parent_asin": "A3", "category": "Electronics", "review_id": "R3", "rating": 5},
    ]

    mock_fetch_products.return_value = {
        "A1": {"parent_asin": "A1", "category": "Electronics", "title": "P1"},
        "A2": {"parent_asin": "A2", "category": "Electronics", "title": "P2"},
        "A3": {"parent_asin": "A3", "category": "Electronics", "title": "P3"},
    }

    mock_fetch_personas.return_value = {
        ("U1", "Electronics"): {"persona": "P1"},
        ("U2", "Electronics"): {"persona": "P2"},
        ("U3", "Electronics"): {"persona": "P3"},
    }

    mock_fetch_train.return_value = {}

    # U1 fails recommendation completely
    # U2 missing from pool
    # U3 succeeds
    mock_evaluate.side_effect = [
        {"status": "success", "recommendation_run_id": None, "candidate_count": 0},
        {"status": "success", "recommendation_run_id": "run_2", "candidate_count": 50, "holdout_in_candidate_pool": False},
        {"status": "success", "recommendation_run_id": "run_3", "candidate_count": 50, "holdout_in_candidate_pool": True, "hit_at_10": 1, "ndcg_score": 1, "reciprocal_rank": 1, "rank_of_holdout": 1},
    ]

    rows, summary = run_task_b_eval(["Electronics"], limit=1, supabase_client=mock_supabase)

    assert summary["total_evaluated"] == 1
    assert summary["total_skipped"] == 2
    assert summary["skipped_recommendation_failed"] == 1
    assert summary["skipped_holdout_not_in_candidate_pool"] == 1
    assert summary["total_scanned"] == 3
    assert mock_evaluate.call_count == 3


@patch("src.evaluation.task_b_eval.evaluate_task_b_row")
@patch("src.evaluation.task_b_eval._fetch_persona_train_asins")
@patch("src.evaluation.task_b_eval._fetch_personas_batch")
@patch("src.evaluation.task_b_eval._fetch_products_batch")
@patch("src.evaluation.task_b_eval.fetch_task_b_holdout_reviews")
def test_task_b_eval_no_valid_rows_returns_zero(
    mock_fetch_reviews, mock_fetch_products, mock_fetch_personas,
    mock_fetch_train, mock_evaluate, mock_supabase
):
    mock_fetch_reviews.return_value = [
        {"user_id": "U1", "parent_asin": "A1", "category": "Electronics", "review_id": "R1", "rating": 5},
        {"user_id": "U2", "parent_asin": "A2", "category": "Electronics", "review_id": "R2", "rating": 5},
    ]

    # U1 missing product. U2 missing persona.
    mock_fetch_products.return_value = {
        "A2": {"parent_asin": "A2", "category": "Electronics", "title": "P2"},
    }

    mock_fetch_personas.return_value = {
        ("U1", "Electronics"): {"persona": "P1"},
    }

    mock_fetch_train.return_value = {}

    rows, summary = run_task_b_eval(["Electronics"], limit=5, supabase_client=mock_supabase)

    assert summary["total_evaluated"] == 0
    assert summary["total_skipped"] == 2
    assert summary["skipped_missing_product_metadata"] == 1
    assert summary["skipped_no_persona"] == 1
    assert mock_evaluate.call_count == 0


@patch("src.evaluation.task_b_eval.evaluate_task_b_row")
@patch("src.evaluation.task_b_eval._fetch_persona_train_asins")
@patch("src.evaluation.task_b_eval._fetch_personas_batch")
@patch("src.evaluation.task_b_eval._fetch_products_batch")
@patch("src.evaluation.task_b_eval.fetch_task_b_holdout_reviews")
def test_task_b_eval_category_mismatch(
    mock_fetch_reviews, mock_fetch_products, mock_fetch_personas,
    mock_fetch_train, mock_evaluate, mock_supabase
):
    mock_fetch_reviews.return_value = [
        {"user_id": "U1", "parent_asin": "A1", "category": "Electronics", "review_id": "R1", "rating": 5},
    ]

    mock_fetch_products.return_value = {
        "A1": {"parent_asin": "A1", "category": "WrongCategory", "title": "P1"},
    }

    mock_fetch_personas.return_value = {
        ("U1", "Electronics"): {"persona": "P1"},
    }
    mock_fetch_train.return_value = {}

    rows, summary = run_task_b_eval(["Electronics"], limit=1, supabase_client=mock_supabase)

    assert summary["total_evaluated"] == 0
    assert summary["total_skipped"] == 1
    assert summary["skipped_category_mismatch"] == 1
