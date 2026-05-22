import pytest

from src.llm.parsers import RobustJsonParseError, parse_json_from_llm_text


def test_parse_valid_raw_json() -> None:
    parsed, cleaned = parse_json_from_llm_text('{"answer": 4}')

    assert parsed == {"answer": 4}
    assert cleaned == '{"answer": 4}'


def test_parse_json_inside_markdown_fences() -> None:
    parsed, cleaned = parse_json_from_llm_text('```json\n{"answer": 4}\n```')

    assert parsed == {"answer": 4}
    assert cleaned == '{"answer": 4}'


def test_parse_json_after_thinking_block() -> None:
    parsed, cleaned = parse_json_from_llm_text(
        '<think>\nprivate reasoning\n</think>\n\n{"answer": 4}'
    )

    assert parsed == {"answer": 4}
    assert cleaned == '{"answer": 4}'


def test_invalid_response_raises_clear_error() -> None:
    with pytest.raises(RobustJsonParseError, match="Unable to parse JSON object|does not contain"):
        parse_json_from_llm_text("not json")
