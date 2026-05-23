from __future__ import annotations

import json
from typing import Any

from src.config import get_settings
from src.llm.groq_client import get_groq_chat
from src.llm.logging import log_llm_response
from src.llm.parsers import RobustJsonParseError, parse_json_from_llm_text
from src.task_a_simulation.product_normalizer import normalize_custom_product, validate_custom_product_minimum
from src.task_a_simulation.schema import ProductSnapshot


CUSTOM_PRODUCT_VALIDATION_PROMPT_VERSION = "custom_product_validation_v1"
PRODUCT_UNUSABLE_SUGGESTION = "add at least a product title/name/product_name or a useful description/features list."


def serialize_custom_input(raw_input: dict[str, Any] | str) -> str:
    if isinstance(raw_input, dict):
        return json.dumps(raw_input, ensure_ascii=False, indent=2)
    return raw_input


def build_custom_product_prompt(raw_input: dict[str, Any] | str) -> str:
    raw_kind = "JSON object" if isinstance(raw_input, dict) else "plain text"
    raw_text = serialize_custom_input(raw_input)
    return f"""
You are validating and extracting product metadata for iRecommend review simulation.

Input type: {raw_kind}
Input:
{raw_text}

Return JSON only. Do not include markdown.

Accept flexible but meaningful product descriptions or product JSON. Reject meaningless input
like {{"id": "123"}}, "hello world", "random product", or "nothing".

Minimum useful product signal: title/name OR description/features.
Do not invent product facts. If price, rating, or review count are missing, leave them null.

Return exactly this JSON shape:
{{
  "is_usable": true,
  "reason": "Why usable/unusable",
  "missing_information": [],
  "suggested_fix": "",
  "normalized_product": {{
    "parent_asin": "custom_product",
    "title": "",
    "main_category": "",
    "categories": [],
    "price": null,
    "features": [],
    "description": [],
    "average_rating": null,
    "rating_number": null,
    "store": null,
    "details": {{
      "custom_fields": {{}},
      "raw_custom_input": {{}},
      "llm_validation_reason": "",
      "missing_information": [],
      "suggested_fix": ""
    }}
  }}
}}
""".strip()


def unusable_product_error(reason: str | None, suggested_fix: str | None) -> ValueError:
    reason_text = reason or "the input does not contain a useful product title, description, or features"
    fix_text = suggested_fix or PRODUCT_UNUSABLE_SUGGESTION
    return ValueError(f"Custom product is not usable: {reason_text}. Suggested fix: {fix_text}")


def invoke_product_validation_llm(raw_input: dict[str, Any] | str) -> tuple[dict[str, Any], str, str]:
    settings = get_settings()
    prompt = build_custom_product_prompt(raw_input)
    raw_message = get_groq_chat(settings.groq_model).invoke(prompt)
    raw_text = getattr(raw_message, "content", str(raw_message))
    parsed, cleaned_json_text = parse_json_from_llm_text(raw_text)
    return parsed, raw_text, cleaned_json_text


def process_custom_product(raw_input: dict[str, Any] | str) -> dict[str, Any]:
    if not isinstance(raw_input, dict | str):
        raise ValueError("Custom product must be a JSON object or text description.")
    if isinstance(raw_input, str) and not raw_input.strip():
        raise unusable_product_error("the input is empty", PRODUCT_UNUSABLE_SUGGESTION)

    try:
        parsed, raw_text, cleaned_json_text = invoke_product_validation_llm(raw_input)
    except RobustJsonParseError as exc:
        raise unusable_product_error("the validation response could not be parsed", PRODUCT_UNUSABLE_SUGGESTION) from exc

    log_llm_response(
        "custom_product_validation",
        {
            "prompt_version": CUSTOM_PRODUCT_VALIDATION_PROMPT_VERSION,
            "raw_text": raw_text,
            "cleaned_json_text": cleaned_json_text,
            "parsed_payload": parsed,
            "is_usable": parsed.get("is_usable"),
        },
    )

    if parsed.get("is_usable") is not True:
        raise unusable_product_error(parsed.get("reason"), parsed.get("suggested_fix"))

    normalized_product = parsed.get("normalized_product")
    if not isinstance(normalized_product, dict):
        raise unusable_product_error("the validator did not return normalized product metadata", PRODUCT_UNUSABLE_SUGGESTION)

    normalized = normalize_custom_product(normalized_product)
    details = dict(normalized.get("details") or {})
    details.update(
        {
            "raw_custom_input": raw_input,
            "llm_validation_reason": parsed.get("reason") or "",
            "missing_information": parsed.get("missing_information") or [],
            "suggested_fix": parsed.get("suggested_fix") or "",
        }
    )
    normalized["details"] = details

    validate_custom_product_minimum(normalized)
    return ProductSnapshot.model_validate(normalized).model_dump(mode="json")
