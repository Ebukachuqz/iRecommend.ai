from __future__ import annotations

import json

from src.task_a_simulation import custom_product_processor


class DummyMessage:
    def __init__(self, content: str):
        self.content = content


class DummyLLM:
    def __init__(self, payload: dict):
        self.payload = payload

    def invoke(self, _prompt: str) -> DummyMessage:
        return DummyMessage(json.dumps(self.payload))


def usable_product_payload() -> dict:
    return {
        "is_usable": True,
        "reason": "Contains a clear product title and features.",
        "missing_information": [],
        "suggested_fix": "",
        "normalized_product": {
            "parent_asin": "custom_product",
            "title": "Gentle Hydrating Face Cream",
            "main_category": "Skincare",
            "categories": ["Skincare"],
            "price": 18.99,
            "features": ["fragrance-free", "hydrating", "for dry sensitive skin"],
            "description": ["A lightweight moisturizing cream for dry and sensitive skin."],
            "average_rating": 4.5,
            "rating_number": 120,
            "store": "Example",
            "details": {"custom_fields": {}},
        },
    }


def test_process_custom_product_rejects_weak_json(monkeypatch) -> None:
    monkeypatch.setattr(
        custom_product_processor,
        "get_groq_chat",
        lambda *_args, **_kwargs: DummyLLM(
            {
                "is_usable": False,
                "reason": "the input only contains an id and no usable product title, description, or features",
                "missing_information": ["title or description"],
                "suggested_fix": "add at least a product title/name/product_name or a useful description/features list",
                "normalized_product": {},
            }
        ),
    )

    try:
        custom_product_processor.process_custom_product({"id": "123"})
    except ValueError as exc:
        assert "Custom product is not usable" in str(exc)
        assert "Suggested fix" in str(exc)
    else:
        raise AssertionError("Expected weak custom product to be rejected")


def test_process_custom_product_accepts_meaningful_plain_text(monkeypatch) -> None:
    monkeypatch.setattr(
        custom_product_processor,
        "get_groq_chat",
        lambda *_args, **_kwargs: DummyLLM(usable_product_payload()),
    )

    product = custom_product_processor.process_custom_product(
        "Gentle Hydrating Face Cream, fragrance-free moisturizer for dry sensitive skin."
    )

    assert product["title"] == "Gentle Hydrating Face Cream"
    assert product["details"]["raw_custom_input"].startswith("Gentle Hydrating")
