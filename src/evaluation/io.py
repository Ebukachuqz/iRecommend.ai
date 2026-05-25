from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_name(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(value or "unknown"))
    return safe.strip("_") or "unknown"


def json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=json_default), encoding="utf-8")
    return path


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def evaluation_paths(output_dir: str | Path, task: str, category: str, timestamp: str | None = None) -> dict[str, Path]:
    timestamp = timestamp or utc_timestamp()
    directory = Path(output_dir)
    category_name = safe_name(category)
    return {
        "csv": directory / f"{task}_results_{category_name}_{timestamp}.csv",
        "json": directory / f"{task}_results_{category_name}_{timestamp}.json",
        "summary": directory / f"{task}_summary_{category_name}_{timestamp}.json",
    }
