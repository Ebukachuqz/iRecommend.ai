from __future__ import annotations

import json
import logging
from typing import Any

from src.config import get_settings
from src.llm.groq_client import get_groq_chat
from src.llm.logging import log_llm_response
from src.llm.parsers import parse_json_from_llm_text
from src.task_a_simulation.prompt_compaction import compact_persona, compact_product
from src.task_a_simulation.prompts import (
    NIGERIAN_CONTEXT_SECTION,
    NO_NIGERIAN_CONTEXT_SECTION,
    TASK_A_PROMPT_VERSION,
    TASK_A_REVIEW_PROMPT,
)
from src.task_a_simulation.schema import LLMReviewSimulationOutput, ProductSnapshot, RatingPredictionBreakdown

logger = logging.getLogger(__name__)


class ReviewSimulationLLMError(RuntimeError):
    pass


def _is_payload_too_large(exc: Exception) -> bool:
    text = str(exc).lower()
    return "413" in text or "payload too large" in text or "request too large" in text


def _build_prompt_input(
    persona: dict[str, Any],
    product: ProductSnapshot,
    statistical_prediction: RatingPredictionBreakdown,
    nigerian_mode: bool,
    context: dict[str, Any] | None,
    aggressive: bool = False,
) -> dict[str, str]:
    compact_p = compact_persona(persona, aggressive=aggressive)
    compact_prod = compact_product(product.model_dump(mode="json"), aggressive=aggressive)

    return {
        "persona_json": json.dumps(compact_p, indent=2, ensure_ascii=False),
        "product_json": json.dumps(compact_prod, indent=2, ensure_ascii=False),
        "statistical_prediction_json": json.dumps(
            statistical_prediction.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
        ),
        "context_json": json.dumps(context or {}, indent=2, ensure_ascii=False),
        "nigerian_context": NIGERIAN_CONTEXT_SECTION if nigerian_mode else NO_NIGERIAN_CONTEXT_SECTION,
    }


def _invoke_llm(prompt_input: dict[str, str], model_name: str) -> str:
    llm = get_groq_chat(model_name)
    chain = TASK_A_REVIEW_PROMPT | llm
    raw_message = chain.invoke(prompt_input)
    return getattr(raw_message, "content", str(raw_message))


def generate_llm_review_and_rating(
    persona: dict[str, Any],
    product: ProductSnapshot,
    statistical_prediction: RatingPredictionBreakdown,
    *,
    nigerian_mode: bool = False,
    context: dict[str, Any] | None = None,
) -> LLMReviewSimulationOutput:
    settings = get_settings()

    prompt_input = _build_prompt_input(
        persona, product, statistical_prediction,
        nigerian_mode, context, aggressive=False,
    )

    try:
        raw_text = _invoke_llm(prompt_input, settings.groq_model)
    except Exception as first_exc:
        if not _is_payload_too_large(first_exc):
            raise
        logger.warning("Groq 413 — retrying with aggressive compaction")
        prompt_input = _build_prompt_input(
            persona, product, statistical_prediction,
            nigerian_mode, context, aggressive=True,
        )
        raw_text = _invoke_llm(prompt_input, settings.groq_model)

    try:
        parsed, cleaned_json_text = parse_json_from_llm_text(raw_text)
        output = LLMReviewSimulationOutput.model_validate(parsed)
    except Exception as exc:
        log_llm_response(
            "task_a_simulation_parse_failure",
            {
                "model_name": settings.groq_model,
                "prompt_version": TASK_A_PROMPT_VERSION,
                "raw_text": raw_text,
                "error": str(exc),
            },
        )
        raise ReviewSimulationLLMError(f"Unable to parse Task A LLM output: {exc}") from exc

    log_llm_response(
        "task_a_simulation",
        {
            "model_name": settings.groq_model,
            "prompt_version": TASK_A_PROMPT_VERSION,
            "raw_text": raw_text,
            "cleaned_json_text": cleaned_json_text,
            "parsed_payload": output.model_dump(mode="json"),
        },
    )
    return output
