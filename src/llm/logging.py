from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from src.config import get_settings


def log_llm_response(event: str, payload: dict[str, Any]) -> Path:
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    path = settings.log_dir / "llm_responses.jsonl"
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
