import pytest

from src.personas.validator import PersonaValidationError, validate_persona


def test_validate_persona_repairs_missing_sections() -> None:
    persona = validate_persona({"writing_style": {"length": "short"}}, repair=True)

    assert persona.writing_style.length == "short"
    assert persona.rating_behavior.rating_distribution == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}


def test_validate_persona_rejects_invalid_enum() -> None:
    with pytest.raises(PersonaValidationError):
        validate_persona({"rating_behavior": {"strictness": "very strict"}}, repair=True)
