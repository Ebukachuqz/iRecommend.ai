from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_task_a import evaluate_task_a
from scripts.evaluate_task_b import DEFAULT_REQUEST, evaluate_task_b
from src.evaluation.io import utc_timestamp, write_json


DEFAULT_CATEGORIES = ["Health_and_Household", "Electronics", "Beauty_and_Personal_Care"]


def run_all_evaluations(
    categories: list[str],
    limit: int = 20,
    k: int = 10,
    output_dir: str = "outputs/evaluation",
    request_text: str = DEFAULT_REQUEST,
    dry_run: bool = False,
    task_a_model_label: str = "current/persona_simulator",
    task_b_model_label: str = "current/persona_recommender",
    task_a_runner: Callable[..., dict[str, Any]] = evaluate_task_a,
    task_b_runner: Callable[..., dict[str, Any]] = evaluate_task_b,
    timestamp: str | None = None,
) -> dict[str, Any]:
    timestamp = timestamp or utc_timestamp()
    output_path = Path(output_dir)
    output_files: list[str] = []
    category_runs: list[dict[str, Any]] = []
    notes: list[str] = []

    for category in categories:
        category_entry: dict[str, Any] = {"category": category, "task_a": None, "task_b": None, "status": "success"}
        try:
            task_a_result = task_a_runner(
                category=category,
                limit=limit,
                output_dir=output_dir,
                dry_run=dry_run,
                model_label=task_a_model_label,
                timestamp=timestamp,
            )
            category_entry["task_a"] = task_a_result["summary"]
            output_files.extend(task_a_result.get("files", {}).values())
        except Exception as exc:
            category_entry["status"] = "partial"
            category_entry["task_a_error"] = str(exc)
            notes.append(f"{category} Task A failed: {exc}")

        try:
            task_b_result = task_b_runner(
                category=category,
                limit=limit,
                k=k,
                request_text=request_text,
                output_dir=output_dir,
                dry_run=dry_run,
                model_label=task_b_model_label,
                timestamp=timestamp,
            )
            category_entry["task_b"] = task_b_result["summary"]
            output_files.extend(task_b_result.get("files", {}).values())
        except Exception as exc:
            category_entry["status"] = "partial"
            category_entry["task_b_error"] = str(exc)
            notes.append(f"{category} Task B failed: {exc}")

        task_a_summary = category_entry.get("task_a") or {}
        task_b_summary = category_entry.get("task_b") or {}
        if task_a_summary.get("count_evaluated", 0) == 0 and task_b_summary.get("count_evaluated", 0) == 0:
            category_entry["status"] = "skipped"
            notes.append(f"{category} produced no successful evaluation examples.")
        category_runs.append(category_entry)

    manifest = {
        "timestamp": timestamp,
        "categories": categories,
        "task_a_limit": limit,
        "task_b_limit": limit,
        "k": k,
        "request": request_text,
        "dry_run": dry_run,
        "model_labels": {
            "task_a": task_a_model_label,
            "task_b": task_b_model_label,
        },
        "output_files": output_files,
        "category_runs": category_runs,
        "notes": notes,
    }
    manifest_path = output_path / f"evaluation_manifest_{timestamp}.json"
    write_json(manifest_path, manifest)
    print(f"[evaluation] Manifest saved to {manifest_path}")
    return {"manifest": manifest, "file": str(manifest_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run iRecommend Task A and Task B evaluations for all categories.")
    parser.add_argument("--categories", nargs="+", default=DEFAULT_CATEGORIES)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--output-dir", default="outputs/evaluation")
    parser.add_argument("--request", default=DEFAULT_REQUEST)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--task-a-model-label", default="current/persona_simulator")
    parser.add_argument("--task-b-model-label", default="current/persona_recommender")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_all_evaluations(
        categories=args.categories,
        limit=args.limit,
        k=args.k,
        output_dir=args.output_dir,
        request_text=args.request,
        dry_run=args.dry_run,
        task_a_model_label=args.task_a_model_label,
        task_b_model_label=args.task_b_model_label,
    )


if __name__ == "__main__":
    main()
