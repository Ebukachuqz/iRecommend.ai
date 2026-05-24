from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_filename_part(value: Any) -> str:
    text = str(value or "unknown").strip() or "unknown"
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in text)
    return safe.strip("_") or "unknown"


def save_run_summary(
    output_dir: str | Path,
    category: str | None,
    mode: str,
    payload: dict[str, Any],
    *,
    timestamp: str | None = None,
) -> Path:
    timestamp = timestamp or utc_timestamp()
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename_part(category)}_{safe_filename_part(mode)}_{timestamp}.json"
    path = directory / filename
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path


def build_run_summary(
    *,
    category: str | None,
    mode: str,
    args: dict[str, Any],
    result: dict[str, Any],
    timestamp: str | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "timestamp": timestamp or utc_timestamp(),
        "mode": mode,
        "args": args,
        "result": result,
    }
