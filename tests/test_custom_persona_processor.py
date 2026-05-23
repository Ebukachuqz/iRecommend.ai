from __future__ import annotations

import json

from src.personas import custom_persona_processor


class DummyMessage:
    def __init__(self, content: str):
        self.content = content


class DummyLLM:
    def __init__(self, payload: dict):
        self.payload = payload

    def invoke(self, _prompt: str) -> DummyMessage:
        return DummyMessage(json.dumps(self.payload))


def usable_persona_payload() -> dict:
    return {
        "is_usable": True,
        "reason": "Contains a meaningful skincare preference.",
        "missing_information": [],
        "suggested_fix": "",
        "normalized_persona": {
            "writing_style": {
                "tone": "casual",
                "length": "medium",
                "detail_level": "medium",
                "formality": "mixed",
                "vocabulary_markers": [],
                "common_phrases": [],
            },
            "preferences": {
                "liked_product_types": ["moisturizers"],
                "disliked_product_types": [],
                "liked_attributes": ["hydrating"],
                "disliked_attributes": ["strong fragrance"],
                "what_they_value": ["gentle skincare"],
                "common_complaints": ["dry skin"],
            },
            "rating_behavior": {
                "average_rating": 4.2,
                "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 2, "5": 3},
                "strictness": "moderate",
                "rating_patterns": "likes useful detail",
            },
            "purchase_behavior": {
                "preferred_categories": ["skincare"],
                "price_sensitivity": "medium",
                "quality_sensitivity": "medium",
                "verified_purchase_ratio": 0.0,
            },
            "cultural_signals": "none detected",
            "evidence": {"positive_examples": [], "negative_examples": []},
            "extra_persona_signals": {"normalization_notes": []},
        },
    }


def test_process_custom_persona_rejects_weak_json(monkeypatch) -> None:
    monkeypatch.setattr(
        custom_persona_processor,
        "get_groq_chat",
        lambda *_args, **_kwargs: DummyLLM(
            {
                "is_usable": False,
                "reason": "the input does not contain a meaningful preference, concern, writing style, rating pattern, budget, or shopping priority",
                "missing_information": ["meaningful user signal"],
                "suggested_fix": "add useful details such as liked product types, disliked attributes, concerns, budget, tone, or rating behavior",
                "normalized_persona": {},
            }
        ),
    )

    try:
        custom_persona_processor.process_custom_persona({"hello": "world", "likes": "nothing"})
    except ValueError as exc:
        assert "Custom persona is not usable" in str(exc)
        assert "Suggested fix" in str(exc)
    else:
        raise AssertionError("Expected weak custom persona to be rejected")


def test_process_custom_persona_accepts_meaningful_plain_text(monkeypatch) -> None:
    monkeypatch.setattr(
        custom_persona_processor,
        "get_groq_chat",
        lambda *_args, **_kwargs: DummyLLM(usable_persona_payload()),
    )

    persona = custom_persona_processor.process_custom_persona(
        "I like fragrance-free moisturizers for dry sensitive skin and usually write casually."
    )

    assert persona["preferences"]["liked_attributes"] == ["hydrating"]
    assert persona["extra_persona_signals"]["raw_custom_input"].startswith("I like")


def test_process_custom_persona_accepts_meaningful_json(monkeypatch) -> None:
    monkeypatch.setattr(
        custom_persona_processor,
        "get_groq_chat",
        lambda *_args, **_kwargs: DummyLLM(usable_persona_payload()),
    )

    persona = custom_persona_processor.process_custom_persona({"likes": ["hydrating skincare"], "tone": "casual"})

    assert persona["writing_style"]["tone"] == "casual"
    assert persona["extra_persona_signals"]["llm_validation_reason"]
