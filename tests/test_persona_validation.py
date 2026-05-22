import pytest

from src.personas.validator import PersonaValidationError, validate_persona


def test_validate_persona_repairs_missing_sections() -> None:
    persona = validate_persona({"writing_style": {"length": "short"}}, repair=True)

    assert persona.writing_style.length == "short"
    assert persona.rating_behavior.rating_distribution == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}


def test_validate_persona_moves_unknown_top_level_keys_to_extra_signals() -> None:
    persona = validate_persona(
        {
            "writing_style": {"length": "short"},
            "unexpected_summary": "prefers light textures",
        },
        repair=True,
    )

    assert persona.extra_persona_signals["llm_extra_fields"] == {
        "unexpected_summary": "prefers light textures"
    }


def test_validate_persona_rejects_invalid_enum() -> None:
    with pytest.raises(PersonaValidationError):
        validate_persona({"rating_behavior": {"strictness": "very strict"}}, repair=True)
