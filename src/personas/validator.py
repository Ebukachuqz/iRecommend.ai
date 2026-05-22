import logging
from typing import Any

from pydantic import ValidationError

from src.personas.schema import (
    PersonaEvidence,
    Preferences,
    PurchaseBehavior,
    RatingBehavior,
    UserPersona,
    WritingStyle,
)

logger = logging.getLogger(__name__)


class PersonaValidationError(ValueError):
    pass


DEFAULT_SECTIONS = {
    "writing_style": WritingStyle().model_dump(),
    "preferences": Preferences().model_dump(),
    "rating_behavior": RatingBehavior().model_dump(),
    "purchase_behavior": PurchaseBehavior().model_dump(),
    "cultural_signals": "",
    "evidence": PersonaEvidence().model_dump(),
    "extra_persona_signals": {},
}


def repair_persona_payload(payload: dict[str, Any]) -> dict[str, Any]:
    repaired = dict(payload)
    for key, default in DEFAULT_SECTIONS.items():
        if key not in repaired or repaired[key] is None:
            repaired[key] = default
    return repaired


def validate_persona(payload: dict[str, Any], *, repair: bool = True) -> UserPersona:
    if not isinstance(payload, dict):
        raise PersonaValidationError("Persona payload must be a JSON object.")

    candidate = repair_persona_payload(payload) if repair else payload
    try:
        return UserPersona.model_validate(candidate)
    except ValidationError as exc:
        logger.warning("Persona validation failed: %s", exc)
        raise PersonaValidationError(str(exc)) from exc


def persona_to_storage_dict(persona: UserPersona) -> dict[str, Any]:
    return persona.model_dump(mode="json")
