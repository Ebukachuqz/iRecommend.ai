from __future__ import annotations

import json
from typing import Any

from src.config import get_settings
from src.llm.groq_client import get_groq_chat
from src.llm.logging import log_llm_response
from src.llm.parsers import parse_json_from_llm_text
from src.task_b_recommendation.schema import RecommendationIntent, RecommendationSessionState


INTENT_PROMPT_VERSION = "task_b_intent_v1"

INTENT_TEMPLATE = """Convert the user's recommendation request into JSON retrieval intent.
Return JSON only.

Persona:
{persona_json}

User request:
{request_text}

Session state:
{session_json}

Output:
{{
  "interpreted_need": "string",
  "explicit_constraints": {{}},
  "implicit_constraints_from_persona": {{}},
  "avoid": [],
  "retrieval_query": "string",
  "category_filter": null,
  "price_max": null,
  "required_attributes": [],
  "excluded_attributes": []
}}
"""


def fallback_intent(request: str | None, persona: dict[str, Any] | None = None) -> RecommendationIntent:
    request = request or ""
    preferences = persona.get("preferences", {}) if isinstance(persona, dict) else {}
    return RecommendationIntent(
        interpreted_need=request or "Recommend products that fit the user's persona.",
        retrieval_query=request,
        required_attributes=list(preferences.get("liked_attributes", []) or [])[:5],
        excluded_attributes=list(preferences.get("disliked_attributes", []) or [])[:5],
    )


def plan_intent(
    persona: dict[str, Any],
    request: str | None = None,
    session_state: RecommendationSessionState | None = None,
) -> RecommendationIntent:
    if not request:
        return fallback_intent(request, persona)
    settings = get_settings()
    prompt = INTENT_TEMPLATE.format(
        persona_json=json.dumps(persona, indent=2, ensure_ascii=False),
        request_text=request,
        session_json=json.dumps(session_state.model_dump(mode="json") if session_state else {}, indent=2),
    )
    try:
        raw_message = get_groq_chat(settings.groq_model).invoke(prompt)
        raw_text = getattr(raw_message, "content", str(raw_message))
        parsed, cleaned_json_text = parse_json_from_llm_text(raw_text)
        intent = RecommendationIntent.model_validate(parsed)
        log_llm_response(
            "task_b_intent_planning",
            {
                "model_name": settings.groq_model,
                "prompt_version": INTENT_PROMPT_VERSION,
                "raw_text": raw_text,
                "cleaned_json_text": cleaned_json_text,
                "parsed_payload": intent.model_dump(mode="json"),
            },
        )
        return intent
    except Exception as exc:
        log_llm_response(
            "task_b_intent_planning_fallback",
            {
                "model_name": settings.groq_model,
                "prompt_version": INTENT_PROMPT_VERSION,
                "request": request,
                "error": str(exc),
            },
        )
        return fallback_intent(request, persona)
