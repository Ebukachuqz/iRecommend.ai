from __future__ import annotations

import importlib.util
from pathlib import Path


HELPERS_PATH = Path(__file__).resolve().parents[1] / "client" / "streamlit" / "ui_helpers.py"
spec = importlib.util.spec_from_file_location("streamlit_ui_helpers", HELPERS_PATH)
ui_helpers = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(ui_helpers)


def test_format_score_handles_missing_values() -> None:
    assert ui_helpers.format_score(None) == "n/a"


def test_format_score_formats_numbers() -> None:
    assert ui_helpers.format_score(0.876) == "0.88"


def test_format_score_handles_text() -> None:
    assert ui_helpers.format_score("not-a-number") == "not-a-number"


def test_persona_average_rating_prefers_db_column() -> None:
    row = {
        "average_rating": 4.25,
        "persona": {"rating_behavior": {"average_rating": 3.5}},
    }

    assert ui_helpers.get_persona_average_rating(row) == 4.25


def test_persona_average_rating_falls_back_to_persona_json() -> None:
    row = {
        "average_rating": None,
        "persona": {"rating_behavior": {"average_rating": 3.75}},
    }

    assert ui_helpers.get_persona_average_rating(row) == 3.75


def test_persona_average_rating_returns_na_when_missing() -> None:
    assert ui_helpers.get_persona_average_rating({"persona": {}}) == "n/a"


def test_persona_section_detects_json_renderable_values() -> None:
    assert ui_helpers.is_json_renderable({"tone": "direct"}) is True
    assert ui_helpers.is_json_renderable(["concise", "specific"]) is True


def test_persona_section_treats_plain_strings_as_non_json_renderable() -> None:
    assert ui_helpers.is_json_renderable("none detected") is False
