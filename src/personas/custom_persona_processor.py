from __future__ import annotations

import json
from typing import Any

from src.config import get_settings
from src.llm.groq_client import get_groq_chat
from src.llm.logging import log_llm_response
from src.llm.parsers import RobustJsonParseError, parse_json_from_llm_text
from src.personas.normalizer import normalize_custom_persona, validate_custom_persona_minimum
from src.personas.validator import validate_persona


CUSTOM_PERSONA_VALIDATION_PROMPT_VERSION = "custom_persona_validation_v1"

PERSONA_UNUSABLE_SUGGESTION = (
    "add useful details such as liked product types, disliked attributes, concerns, "
    "budget, tone, or rating behavior."
)


def serialize_custom_input(raw_input: dict[str, Any] | str) -> str:
    if isinstance(raw_input, dict):
        return json.dumps(raw_input, ensure_ascii=False, indent=2)
    return raw_input


def build_custom_persona_prompt(raw_input: dict[str, Any] | str) -> str:
    raw_kind = "JSON object" if isinstance(raw_input, dict) else "plain text"
    raw_text = serialize_custom_input(raw_input)
    return f"""
You are validating and extracting a user persona for iRecommend.

Input type: {raw_kind}
Input:
{raw_text}

Return JSON only. Do not include markdown.

The input does not need to match iRecommend's internal schema. Accept flexible but meaningful
persona descriptions. Reject meaningless, empty, contradictory, or unusable input.

Reject values like "nothing", "none", "unknown", "hello world", "test", or "anything"
if they are the only signal. Accept only if there is at least one meaningful user signal
such as likes, dislikes, interests, concerns, values, budget, tone, product category interest,
rating behaviour, strictness, or shopping priority.

Do not invent strong preferences that are not implied. Use safe defaults only for missing
schema fields.

Return exactly this JSON shape:
{{
  "is_usable": true,
  "reason": "Why this input is or is not usable",
  "missing_information": [],
  "suggested_fix": "What the user should add if unusable",
  "normalized_persona": {{
    "writing_style": {{
      "tone": "",
      "length": "medium",
      "detail_level": "medium",
      "formality": "mixed",
      "vocabulary_markers": [],
      "common_phrases": []
    }},
    "preferences": {{
      "liked_product_types": [],
      "disliked_product_types": [],
      "liked_attributes": [],
      "disliked_attributes": [],
      "what_they_value": [],
      "common_complaints": []
    }},
    "rating_behavior": {{
      "average_rating": 0.0,
      "rating_distribution": {{"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}},
      "strictness": "moderate",
      "rating_patterns": "unknown"
    }},
    "purchase_behavior": {{
      "preferred_categories": [],
      "price_sensitivity": "unknown",
      "quality_sensitivity": "medium",
      "verified_purchase_ratio": 0.0
    }},
    "cultural_signals": "none detected",
    "evidence": {{
      "positive_examples": [],
      "negative_examples": []
    }},
    "extra_persona_signals": {{
      "raw_custom_input": {{}},
      "llm_validation_reason": "",
      "missing_information": [],
      "suggested_fix": "",
      "normalization_notes": []
    }}
  }}
}}
""".strip()


def unusable_persona_error(reason: str | None, suggested_fix: str | None) -> ValueError:
    reason_text = reason or "the input does not contain a meaningful preference, concern, writing style, rating pattern, budget, or shopping priority"
    fix_text = suggested_fix or PERSONA_UNUSABLE_SUGGESTION
    return ValueError(f"Custom persona is not usable: {reason_text}. Suggested fix: {fix_text}")


def invoke_persona_validation_llm(raw_input: dict[str, Any] | str) -> tuple[dict[str, Any], str, str]:
    settings = get_settings()
    prompt = build_custom_persona_prompt(raw_input)
    raw_message = get_groq_chat(settings.groq_model).invoke(prompt)
    raw_text = getattr(raw_message, "content", str(raw_message))
    parsed, cleaned_json_text = parse_json_from_llm_text(raw_text)
    return parsed, raw_text, cleaned_json_text


def process_custom_persona(raw_input: dict[str, Any] | str) -> dict[str, Any]:
    if not isinstance(raw_input, dict | str):
        raise ValueError("Custom persona must be a JSON object or text description.")
    if isinstance(raw_input, str) and not raw_input.strip():
        raise unusable_persona_error("the input is empty", PERSONA_UNUSABLE_SUGGESTION)

    try:
        parsed, raw_text, cleaned_json_text = invoke_persona_validation_llm(raw_input)
    except RobustJsonParseError as exc:
        raise unusable_persona_error("the validation response could not be parsed", PERSONA_UNUSABLE_SUGGESTION) from exc

    log_llm_response(
        "custom_persona_validation",
        {
            "prompt_version": CUSTOM_PERSONA_VALIDATION_PROMPT_VERSION,
            "raw_text": raw_text,
            "cleaned_json_text": cleaned_json_text,
            "parsed_payload": parsed,
            "is_usable": parsed.get("is_usable"),
        },
    )

    if parsed.get("is_usable") is not True:
        raise unusable_persona_error(parsed.get("reason"), parsed.get("suggested_fix"))

    normalized_persona = parsed.get("normalized_persona")
    if not isinstance(normalized_persona, dict):
        raise unusable_persona_error("the validator did not return a normalized persona", PERSONA_UNUSABLE_SUGGESTION)

    normalized = normalize_custom_persona(normalized_persona)
    extra = dict(normalized.get("extra_persona_signals") or {})
    notes = list(extra.get("normalization_notes") or [])
    notes.append("validated by LLM custom persona processor")
    extra.update(
        {
            "raw_custom_input": raw_input,
            "llm_validation_reason": parsed.get("reason") or "",
            "missing_information": parsed.get("missing_information") or [],
            "suggested_fix": parsed.get("suggested_fix") or "",
            "normalization_notes": notes,
        }
    )
    normalized["extra_persona_signals"] = extra

    validate_custom_persona_minimum(normalized)
    return validate_persona(normalized, repair=True).model_dump(mode="json")
