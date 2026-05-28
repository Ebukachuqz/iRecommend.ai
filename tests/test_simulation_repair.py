from __future__ import annotations

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch, MagicMock

from src.task_a_simulation.schema import ProductSnapshot, RatingPredictionBreakdown, LLMReviewSimulationOutput
from src.task_a_simulation.simulator import generate_llm_review_and_rating, ReviewSimulationLLMError, _local_repair


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setattr("src.task_a_simulation.simulator.get_settings", lambda: MagicMock(groq_model="test-model"))


@pytest.fixture
def dummy_inputs():
    persona = {"writing_style": "informal", "preferences": {}}
    product = ProductSnapshot(parent_asin="A1", title="Product 1")
    statistical = RatingPredictionBreakdown(
        statistical_predicted_rating=4.5,
        rating_count=100,
        average_rating=4.5,
        user_average_rating=4.5,
        category_average=4.5,
        category_offset=0.0,
        persona_offset=0.0,
        explanation="Test explanation"
    )
    return persona, product, statistical


def test_missing_reasoning_summary_gets_fallback():
    parsed = {
        "llm_predicted_rating": 4,
        "simulated_review_title": "Good",
        "simulated_review_text": "Good text",
        "evidence_used": []
    }
    repaired = _local_repair(parsed)
    assert repaired["reasoning_summary"] == "Generated from the user's persona, rating behavior, and product metadata."


def test_review_text_maps_to_simulated_review_text():
    parsed = {
        "llm_predicted_rating": 4,
        "simulated_review_title": "Good",
        "review_text": "Good text",
        "evidence_used": []
    }
    repaired = _local_repair(parsed)
    assert repaired["simulated_review_text"] == "Good text"


def test_simulated_review_maps_to_simulated_review_text():
    parsed = {
        "llm_predicted_rating": 4,
        "simulated_review_title": "Good",
        "simulated_review": "Good text",
        "evidence_used": []
    }
    repaired = _local_repair(parsed)
    assert repaired["simulated_review_text"] == "Good text"


@patch("src.task_a_simulation.simulator._invoke_llm")
def test_markdown_fenced_json_is_still_parsed(mock_invoke, dummy_inputs, mock_settings):
    persona, product, statistical = dummy_inputs
    valid_json = {
        "llm_predicted_rating": 4,
        "simulated_review_title": "Good",
        "simulated_review_text": "Good text",
        "reasoning_summary": "Reason",
        "evidence_used": []
    }
    mock_invoke.return_value = f"```json\n{json.dumps(valid_json)}\n```"

    output = generate_llm_review_and_rating(persona, product, statistical)
    assert output.llm_predicted_rating == 4
    assert output.simulated_review_text == "Good text"


@patch("src.task_a_simulation.simulator._invoke_repair_llm")
@patch("src.task_a_simulation.simulator._invoke_llm")
def test_invalid_output_triggers_exactly_one_repair_retry(mock_invoke, mock_repair, dummy_inputs, mock_settings):
    persona, product, statistical = dummy_inputs
    
    # First call returns invalid json (missing simulated_review_text and alternatives)
    mock_invoke.return_value = '{"llm_predicted_rating": 4, "simulated_review_title": "Good", "evidence_used": []}'
    
    # Repair call returns valid json
    mock_repair.return_value = '{"llm_predicted_rating": 4, "simulated_review_title": "Good", "simulated_review_text": "Repaired text", "reasoning_summary": "Reason", "evidence_used": []}'

    output = generate_llm_review_and_rating(persona, product, statistical)
    
    assert mock_invoke.call_count == 1
    assert mock_repair.call_count == 1
    assert output.simulated_review_text == "Repaired text"


@patch("src.task_a_simulation.simulator._invoke_repair_llm")
@patch("src.task_a_simulation.simulator._invoke_llm")
def test_invalid_output_fails_cleanly_after_retry_fails(mock_invoke, mock_repair, dummy_inputs, mock_settings):
    persona, product, statistical = dummy_inputs
    
    # First call returns totally invalid text
    mock_invoke.return_value = 'This is not json'
    
    # Repair call also returns totally invalid text
    mock_repair.return_value = 'Still not json'

    with pytest.raises(ReviewSimulationLLMError, match="Unable to parse Task A LLM output"):
        generate_llm_review_and_rating(persona, product, statistical)

    assert mock_invoke.call_count == 1
    assert mock_repair.call_count == 1
