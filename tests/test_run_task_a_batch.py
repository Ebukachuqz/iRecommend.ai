from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_task_a_batch import fetch_candidates, run_batch


@pytest.fixture
def mock_supabase():
    return MagicMock()


REVIEWS = [
    {"review_id": "R1", "user_id": "U1", "parent_asin": "A1", "task_split": "task_a_holdout", "category": "Electronics"},
    {"review_id": "R2", "user_id": "U2", "parent_asin": "A2", "task_split": "task_a_holdout", "category": "Electronics"},
    {"review_id": "R3", "user_id": "U3", "parent_asin": "A3", "task_split": "task_a_holdout", "category": "Health_and_Household"},
    {"review_id": "R4", "user_id": "U4", "parent_asin": "A4", "task_split": "task_a_holdout", "category": "Electronics"},
]


def _make_args(category="Electronics", limit=50, dry_run=False):
    return argparse.Namespace(category=category, limit=limit, dry_run=dry_run)


@patch("scripts.run_task_a_batch.resolve_category_for_reviews")
@patch("scripts.run_task_a_batch.fetch_all_paginated")
def test_selects_only_holdout_rows(mock_paginated, mock_resolve, mock_supabase):
    mixed = REVIEWS + [
        {"review_id": "R5", "user_id": "U5", "parent_asin": "A5", "task_split": "persona_train", "category": "Electronics"},
    ]
    mock_paginated.return_value = [r for r in mixed if r["task_split"] == "task_a_holdout"]
    mock_resolve.return_value = None

    result = fetch_candidates("Electronics", 50, mock_supabase)
    assert all(r["task_split"] == "task_a_holdout" for r in result)


@patch("scripts.run_task_a_batch.resolve_category_for_reviews")
@patch("scripts.run_task_a_batch.fetch_all_paginated")
def test_filters_by_category(mock_paginated, mock_resolve, mock_supabase):
    mock_paginated.return_value = list(REVIEWS)
    mock_resolve.return_value = None

    result = fetch_candidates("Electronics", 50, mock_supabase)
    assert len(result) == 3
    assert all(r["category"] == "Electronics" for r in result)


@patch("scripts.run_task_a_batch.simulate_review_for_specific_holdout")
@patch("scripts.run_task_a_batch.fetch_persona_user_ids")
@patch("scripts.run_task_a_batch.fetch_existing_simulation_review_ids")
@patch("scripts.run_task_a_batch.fetch_candidates")
@patch("scripts.run_task_a_batch.get_supabase_client")
def test_skips_existing_simulations(
    mock_client, mock_candidates, mock_existing, mock_personas, mock_simulate
):
    mock_client.return_value = MagicMock()
    mock_candidates.return_value = [REVIEWS[0], REVIEWS[1]]
    mock_existing.return_value = {"R1"}
    mock_personas.return_value = {"U1", "U2"}

    stats = run_batch(_make_args())
    assert stats["skipped_existing"] == 1
    assert mock_simulate.call_count == 1


@patch("scripts.run_task_a_batch.simulate_review_for_specific_holdout")
@patch("scripts.run_task_a_batch.fetch_persona_user_ids")
@patch("scripts.run_task_a_batch.fetch_existing_simulation_review_ids")
@patch("scripts.run_task_a_batch.fetch_candidates")
@patch("scripts.run_task_a_batch.get_supabase_client")
def test_skips_users_without_personas(
    mock_client, mock_candidates, mock_existing, mock_personas, mock_simulate
):
    mock_client.return_value = MagicMock()
    mock_candidates.return_value = [REVIEWS[0], REVIEWS[1]]
    mock_existing.return_value = set()
    mock_personas.return_value = {"U1"}

    stats = run_batch(_make_args())
    assert stats["skipped_no_persona"] == 1
    assert mock_simulate.call_count == 1


@patch("scripts.run_task_a_batch.simulate_review_for_specific_holdout")
@patch("scripts.run_task_a_batch.fetch_persona_user_ids")
@patch("scripts.run_task_a_batch.fetch_existing_simulation_review_ids")
@patch("scripts.run_task_a_batch.fetch_candidates")
@patch("scripts.run_task_a_batch.get_supabase_client")
def test_dry_run_does_not_call_service(
    mock_client, mock_candidates, mock_existing, mock_personas, mock_simulate
):
    mock_client.return_value = MagicMock()
    mock_candidates.return_value = [REVIEWS[0], REVIEWS[1]]
    mock_existing.return_value = set()
    mock_personas.return_value = {"U1", "U2"}

    stats = run_batch(_make_args(dry_run=True))
    assert mock_simulate.call_count == 0
    assert stats["created"] == 2
    assert stats["dry_run"] is True


@patch("scripts.run_task_a_batch.simulate_review_for_specific_holdout")
@patch("scripts.run_task_a_batch.fetch_persona_user_ids")
@patch("scripts.run_task_a_batch.fetch_existing_simulation_review_ids")
@patch("scripts.run_task_a_batch.fetch_candidates")
@patch("scripts.run_task_a_batch.get_supabase_client")
def test_summary_counts_are_correct(
    mock_client, mock_candidates, mock_existing, mock_personas, mock_simulate
):
    mock_client.return_value = MagicMock()
    mock_candidates.return_value = [REVIEWS[0], REVIEWS[1], REVIEWS[3]]
    mock_existing.return_value = {"R1"}
    mock_personas.return_value = {"U1", "U4"}
    mock_simulate.side_effect = [None, Exception("LLM error")]

    stats = run_batch(_make_args())
    assert stats["candidates_found"] == 3
    assert stats["skipped_existing"] == 1
    assert stats["skipped_no_persona"] == 1
    assert stats["created"] == 0
    assert stats["failed"] == 1
    assert stats["attempted"] == 1
