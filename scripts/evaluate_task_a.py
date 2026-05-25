from __future__ import annotations

import argparse
from pathlib import Path
import sys
from statistics import mean
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from src.evaluation.data import select_task_a_examples, user_average_ratings_from_persona_train
from src.evaluation.io import evaluation_paths, utc_timestamp, write_csv, write_json
from src.evaluation.metrics import (
    exact_rating_accuracy,
    mae,
    rmse,
    round_metric,
    rounded_rating,
    within_1_star_accuracy,
)
from src.task_a_simulation import service as task_a_service
from src.task_a_simulation.schema import ReviewSimulationRequest


TASK_A_FIELDS = [
    "category",
    "user_id",
    "parent_asin",
    "review_id",
    "product_title",
    "true_rating",
    "predicted_rating",
    "absolute_error",
    "squared_error",
    "exact_match",
    "within_1_star",
    "baseline_predicted_rating",
    "baseline_absolute_error",
    "true_review_title",
    "true_review_text",
    "simulated_review_text",
    "persona_version",
    "prompt_version",
    "model_label",
    "status",
    "error_message",
]


def task_a_row_base(example: dict[str, Any], category: str, model_label: str) -> dict[str, Any]:
    review = example["review"]
    product = example["product"]
    persona = example["persona"]
    return {
        "category": category,
        "user_id": review.get("user_id"),
        "parent_asin": review.get("parent_asin"),
        "review_id": review.get("review_id"),
        "product_title": product.get("title"),
        "true_rating": review.get("rating"),
        "predicted_rating": None,
        "absolute_error": None,
        "squared_error": None,
        "exact_match": None,
        "within_1_star": None,
        "baseline_predicted_rating": None,
        "baseline_absolute_error": None,
        "true_review_title": review.get("title"),
        "true_review_text": review.get("text"),
        "simulated_review_text": None,
        "persona_version": persona.get("persona_version"),
        "prompt_version": None,
        "model_label": model_label,
        "status": "pending",
        "error_message": None,
    }


def apply_rating_metrics(row: dict[str, Any], predicted_rating: float | None, prefix: str = "") -> None:
    true_rating = row.get("true_rating")
    if predicted_rating is None or true_rating is None:
        return
    predicted = float(predicted_rating)
    actual = float(true_rating)
    row[f"{prefix}predicted_rating" if prefix else "predicted_rating"] = round_metric(predicted, 3)
    if prefix:
        row[f"{prefix}absolute_error"] = round_metric(abs(predicted - actual), 4)
    else:
        row["absolute_error"] = round_metric(abs(predicted - actual), 4)
        row["squared_error"] = round_metric((predicted - actual) ** 2, 4)
        row["exact_match"] = rounded_rating(predicted) == rounded_rating(actual)
        row["within_1_star"] = abs(predicted - actual) <= 1.0


def summarize_task_a(rows: list[dict[str, Any]], category: str, model_label: str) -> dict[str, Any]:
    successful = [row for row in rows if row.get("status") == "ok" and row.get("predicted_rating") is not None]
    failed = [row for row in rows if row.get("status") == "failed"]
    pairs = [(float(row["predicted_rating"]), float(row["true_rating"])) for row in successful]
    baseline_pairs = [
        (float(row["baseline_predicted_rating"]), float(row["true_rating"]))
        for row in rows
        if row.get("baseline_predicted_rating") is not None and row.get("true_rating") is not None
    ]
    predicted_values = [float(row["predicted_rating"]) for row in successful]
    true_values = [float(row["true_rating"]) for row in successful]
    predicted_mean = mean(predicted_values) if predicted_values else None
    true_mean = mean(true_values) if true_values else None
    return {
        "task": "task_a",
        "category": category,
        "model_label": model_label,
        "count_evaluated": len(successful),
        "count_failed": len(failed),
        "mae": round_metric(mae(pairs)),
        "rmse": round_metric(rmse(pairs)),
        "exact_rating_accuracy": round_metric(exact_rating_accuracy(pairs)),
        "within_1_star_accuracy": round_metric(within_1_star_accuracy(pairs)),
        "predicted_mean_rating": round_metric(predicted_mean),
        "true_mean_rating": round_metric(true_mean),
        "optimistic_bias": round_metric(predicted_mean - true_mean) if predicted_mean is not None and true_mean is not None else None,
        "baseline_mae": round_metric(mae(baseline_pairs)),
        "baseline_rmse": round_metric(rmse(baseline_pairs)),
        "baseline_exact_rating_accuracy": round_metric(exact_rating_accuracy(baseline_pairs)),
        "baseline_within_1_star_accuracy": round_metric(within_1_star_accuracy(baseline_pairs)),
    }


def evaluate_task_a(
    category: str,
    limit: int = 20,
    user_id: str | None = None,
    output_dir: str | Path = "outputs/evaluation",
    dry_run: bool = False,
    model_label: str = "current/persona_simulator",
    client: Any | None = None,
    simulate_func: Callable[..., Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    client = client or get_supabase_client()
    simulate_func = simulate_func or task_a_service.simulate_review
    timestamp = timestamp or utc_timestamp()
    examples = select_task_a_examples(category, limit=limit, user_id=user_id, client=client)
    averages = user_average_ratings_from_persona_train(category, client=client)
    rows: list[dict[str, Any]] = []
    for example in examples:
        row = task_a_row_base(example, category, model_label)
        baseline_rating = averages.get(str(row["user_id"]))
        apply_rating_metrics(row, baseline_rating, prefix="baseline_")
        if dry_run:
            row["status"] = "dry_run"
            rows.append(row)
            continue
        try:
            output = simulate_func(
                ReviewSimulationRequest(
                    user_id=str(row["user_id"]),
                    category=category,
                    parent_asin=str(row["parent_asin"]),
                    context={"evaluation": True, "holdout_review_id": row["review_id"]},
                ),
                client=client,
            )
            apply_rating_metrics(row, float(output.final_predicted_rating))
            row["simulated_review_text"] = output.simulated_review_text
            row["prompt_version"] = output.prompt_version
            row["status"] = "ok"
        except Exception as exc:
            row["status"] = "failed"
            row["error_message"] = str(exc)
        rows.append(row)

    summary = summarize_task_a(rows, category, model_label)
    paths = evaluation_paths(output_dir, "task_a", category, timestamp=timestamp)
    write_csv(paths["csv"], rows, TASK_A_FIELDS)
    write_json(paths["json"], rows)
    write_json(paths["summary"], summary)
    return {"rows": rows, "summary": summary, "files": {key: str(value) for key, value in paths.items()}}


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Evaluate Task A review simulation against task_a_holdout reviews.")
    parser.add_argument("--category", default=settings.default_category)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--user-id")
    parser.add_argument("--output-dir", default="outputs/evaluation")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model-label", default="current/persona_simulator")
    args = parser.parse_args()

    result = evaluate_task_a(
        category=args.category,
        limit=args.limit,
        user_id=args.user_id,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        model_label=args.model_label,
    )
    print(result["summary"])
    print(result["files"])


if __name__ == "__main__":
    main()
