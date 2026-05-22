import re
from typing import Any

from langchain_core.output_parsers import JsonOutputParser


class RobustJsonParseError(ValueError):
    pass


def get_json_parser() -> JsonOutputParser:
    return JsonOutputParser()


def strip_thinking_blocks(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)


def strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    fenced_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    return fenced_match.group(1).strip() if fenced_match else stripped


def clean_llm_json_text(text: str) -> str:
    return strip_markdown_fences(strip_thinking_blocks(text)).strip()


def extract_json_object_text(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RobustJsonParseError("LLM response does not contain a JSON object.")
    return text[start : end + 1].strip()


def parse_json_from_llm_text(text: str, parser: JsonOutputParser | None = None) -> tuple[dict[str, Any], str]:
    parser = parser or get_json_parser()
    cleaned = clean_llm_json_text(text)
    try:
        parsed = parser.parse(cleaned)
        if not isinstance(parsed, dict):
            raise RobustJsonParseError("Parsed LLM JSON must be an object.")
        return parsed, cleaned
    except Exception as first_error:
        try:
            extracted = extract_json_object_text(cleaned)
            parsed = parser.parse(extracted)
            if not isinstance(parsed, dict):
                raise RobustJsonParseError("Parsed LLM JSON must be an object.")
            return parsed, extracted
        except Exception as second_error:
            raise RobustJsonParseError(
                f"Unable to parse JSON object from LLM response: {second_error}"
            ) from first_error
