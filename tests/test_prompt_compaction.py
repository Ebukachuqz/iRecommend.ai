from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.task_a_simulation.prompt_compaction import (
    MAX_FIELD_CHARS,
    MAX_LIST_ITEMS,
    MAX_TOTAL_PRODUCT_CHARS,
    compact_persona,
    compact_product,
    _truncate_str,
    _truncate_list,
)


def test_truncate_str_short():
    assert _truncate_str("hello", 300) == "hello"


def test_truncate_str_long():
    long = "x" * 500
    result = _truncate_str(long, 100)
    assert len(result) == 100
    assert result.endswith("...")


def test_truncate_list_limits_items():
    items = [f"item_{i}" for i in range(20)]
    result = _truncate_list(items, max_items=5)
    assert len(result) == 5


def test_truncate_list_truncates_strings():
    items = ["x" * 500]
    result = _truncate_list(items, max_items=5, max_chars=100)
    assert len(result[0]) == 100
    assert result[0].endswith("...")


def test_compact_persona_keeps_required_sections():
    persona = {
        "rating_behavior": {"average_rating": 4.2, "strictness": "moderate"},
        "purchase_behavior": {"price_sensitivity": "high"},
        "preferences": {"liked_attributes": ["quality"]},
        "writing_style": {"tone": "casual", "length": "short"},
        "evidence": {"positive_examples": ["great product"], "negative_examples": ["bad"]},
        "extra_persona_signals": {"some_key": "some_value"},
        "cultural_signals": "test",
    }
    result = compact_persona(persona)
    assert "rating_behavior" in result
    assert "purchase_behavior" in result
    assert "preferences" in result
    assert "writing_style" in result
    assert "cultural_signals" in result
    assert "evidence" not in result
    assert "extra_persona_signals" not in result


def test_compact_persona_aggressive_drops_cultural():
    persona = {
        "rating_behavior": {"average_rating": 4.0},
        "cultural_signals": "some cultural note",
    }
    result = compact_persona(persona, aggressive=True)
    assert "cultural_signals" not in result


def test_compact_persona_truncates_long_values():
    persona = {
        "preferences": {
            "liked_attributes": [f"attr_{i}" for i in range(20)],
            "what_they_value": ["x" * 500],
        }
    }
    result = compact_persona(persona)
    assert len(result["preferences"]["liked_attributes"]) == MAX_LIST_ITEMS
    assert len(result["preferences"]["what_they_value"][0]) <= MAX_FIELD_CHARS


def test_compact_product_keeps_core_fields():
    product = {
        "parent_asin": "B001",
        "title": "Test Product",
        "main_category": "Electronics",
        "average_rating": 4.5,
        "rating_number": 100,
        "price": 29.99,
        "store": "Amazon",
        "category": "Electronics",
        "features": ["feature1", "feature2"],
        "description": ["short desc"],
        "details": {"Brand": "TestBrand"},
        "categories": ["Cat1"],
    }
    result = compact_product(product)
    assert result["parent_asin"] == "B001"
    assert result["title"] == "Test Product"
    assert result["average_rating"] == 4.5
    assert result["price"] == 29.99
    assert "features" in result
    assert "description" in result


def test_compact_product_truncates_long_fields():
    product = {
        "parent_asin": "B001",
        "title": "Test",
        "features": [f"feature {i} " + "x" * 500 for i in range(20)],
        "description": ["d" * 500 for _ in range(10)],
        "details": {f"key_{i}": "v" * 500 for i in range(20)},
    }
    result = compact_product(product)
    assert len(result.get("features", [])) <= MAX_LIST_ITEMS
    assert len(result.get("description", [])) <= MAX_LIST_ITEMS
    assert len(result.get("details", {})) <= MAX_LIST_ITEMS


def test_compact_product_drops_fields_when_over_limit():
    product = {
        "parent_asin": "B001",
        "title": "Test Product",
        "features": ["f" * 300 for _ in range(5)],
        "description": ["d" * 300 for _ in range(5)],
        "details": {f"k{i}": "v" * 300 for i in range(5)},
        "categories": ["c" * 300 for _ in range(5)],
    }
    result = compact_product(product)
    text = json.dumps(result, ensure_ascii=False)
    # After compaction, oversized fields are progressively dropped
    assert len(text) <= MAX_TOTAL_PRODUCT_CHARS + 500  # some tolerance for remaining fields


def test_compact_product_aggressive_uses_smaller_limits():
    product = {
        "parent_asin": "B001",
        "title": "Test",
        "features": [f"feature_{i}" for i in range(10)],
    }
    normal = compact_product(product, aggressive=False)
    aggressive = compact_product(product, aggressive=True)
    assert len(aggressive.get("features", [])) <= 3
    assert len(normal.get("features", [])) <= 5


def test_compact_persona_aggressive_uses_smaller_limits():
    persona = {
        "preferences": {
            "liked_attributes": [f"attr_{i}" for i in range(10)],
        }
    }
    normal = compact_persona(persona, aggressive=False)
    aggressive = compact_persona(persona, aggressive=True)
    assert len(aggressive["preferences"]["liked_attributes"]) <= 3
    assert len(normal["preferences"]["liked_attributes"]) <= 5
