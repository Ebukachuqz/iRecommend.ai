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
