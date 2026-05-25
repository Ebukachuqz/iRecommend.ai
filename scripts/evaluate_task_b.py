from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.data import popularity_baseline_recommendations, select_task_b_examples
from src.evaluation.io import evaluation_paths, write_csv, write_json
from src.evaluation.metrics import (
    hit_at_k,
    ndcg_at_k,
    rank_of_item,
    reciprocal_rank,
    round_metric,
    summarize_ranking_rows,
)
from src.task_b_recommendation import service as task_b_service
from src.task_b_recommendation.schema import RecommendationOutput, RecommendationRequest


DEFAULT_REQUEST = "Recommend products I would like."

TASK_B_FIELDS = [
    "category",
    "user_id",
    "holdout_review_id",
    "holdout_parent_asin",
    "holdout_product_title",
    "holdout_rating",
    "request",
    "recommended_parent_asins",
    "recommended_titles",
    "hit_at_k",
    "rank_of_holdout",
    "ndcg_at_k",
    "reciprocal_rank",
    "top_recommendation_parent_asin",
    "top_recommendation_title",
    "top_recommendation_reason",
    "retrieval_sources",
    "baseline_recommended_parent_asins",
    "baseline_hit_at_k",
    "baseline_rank_of_holdout",
    "baseline_ndcg_at_k",
    "baseline_reciprocal_rank",
    "recommendation_run_id",
    "model_label",
    "status",
    "error_message",
]


def task_b_row_base(example: dict[str, Any], category: str, request_text: str, model_label: str) -> dict[str, Any]:
    review = example["review"]
    product = example["product"]
    return {
        "category": category,
        "user_id": review.get("user_id"),
        "holdout_review_id": review.get("review_id"),
        "holdout_parent_asin": review.get("parent_asin"),
        "holdout_product_title": product.get("title"),
        "holdout_rating": review.get("rating"),
        "request": request_text,
        "recommended_parent_asins": [],
        "recommended_titles": [],
        "hit_at_k": False,
        "rank_of_holdout": None,
        "ndcg_at_k": 0.0,
        "reciprocal_rank": 0.0,
        "top_recommendation_parent_asin": None,
        "top_recommendation_title": None,
        "top_recommendation_reason": None,
        "retrieval_sources": None,
        "baseline_recommended_parent_asins": [],
        "baseline_hit_at_k": False,
        "baseline_rank_of_holdout": None,
        "baseline_ndcg_at_k": 0.0,
        "baseline_reciprocal_rank": 0.0,
        "recommendation_run_id": None,
        "model_label": model_label,
        "status": "pending",
        "error_message": None,
    }


def apply_ranking_metrics(row: dict[str, Any], recommendations: list[str], target: str, k: int, prefix: str = "") -> None:
    rank = rank_of_item(recommendations, target, k)
    row[f"{prefix}hit_at_k"] = hit_at_k(rank)
    row[f"{prefix}rank_of_holdout"] = rank
    row[f"{prefix}ndcg_at_k"] = round_metric(ndcg_at_k(rank))
    row[f"{prefix}reciprocal_rank"] = round_metric(reciprocal_rank(rank))


def recommendation_lists(output: RecommendationOutput, k: int) -> tuple[list[str], list[str]]:
    recommendations = output.recommendations[:k]
    parent_asins = [item.parent_asin for item in recommendations if item.parent_asin]
    titles = [item.title or "" for item in recommendations]
    return parent_asins, titles


def summarize_task_b(rows: list[dict[str, Any]], category: str, k: int, request_text: str, model_label: str) -> dict[str, Any]:
    successful = [row for row in rows if row.get("status") == "success"]
    failed = [row for row in rows if row.get("status") == "failed"]
    dry_run = [row for row in rows if row.get("status") == "dry_run"]
    baseline_summary = summarize_ranking_rows(
        [
            {
                "hit_at_k": row.get("baseline_hit_at_k"),
                "ndcg_at_k": row.get("baseline_ndcg_at_k"),
                "reciprocal_rank": row.get("baseline_reciprocal_rank"),
                "rank_of_holdout": row.get("baseline_rank_of_holdout"),
            }
            for row in successful
        ]
    )
    return {
        "task": "task_b",
        "category": category,
        "k": k,
        "request": request_text,
        "model_label": model_label,
        **summarize_ranking_rows(successful),
        "count_failed": len(failed),
        "count_dry_run": len(dry_run),
        "baseline_hit_rate_at_k": baseline_summary["hit_rate_at_k"],
        "baseline_ndcg_at_k": baseline_summary["ndcg_at_k"],
        "baseline_mrr_at_k": baseline_summary["mrr_at_k"],
        "baseline_mean_rank_of_holdout": baseline_summary["mean_rank_of_holdout"],
        "baseline_count_hits": baseline_summary["count_hits"],
    }


def evaluate_task_b(
    category: str,
    limit: int = 20,
    user_id: str | None = None,
    k: int = 10,
    request_text: str = DEFAULT_REQUEST,
    output_dir: str = "outputs/evaluation",
    dry_run: bool = False,
    model_label: str = "current/persona_recommender",
    client: Any | None = None,
    recommend_func: Callable[..., RecommendationOutput] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    examples = select_task_b_examples(category, limit=limit, user_id=user_id, client=client)
    recommend_func = recommend_func or task_b_service.recommend
    rows: list[dict[str, Any]] = []

    for example in examples:
        row = task_b_row_base(example, category, request_text, model_label)
        holdout_parent_asin = str(row["holdout_parent_asin"])
        try:
            baseline_products = popularity_baseline_recommendations(
                str(row["user_id"]),
                category,
                k,
                client=client,
            )
            baseline_asins = [product["parent_asin"] for product in baseline_products if product.get("parent_asin")]
            row["baseline_recommended_parent_asins"] = baseline_asins
            apply_ranking_metrics(row, baseline_asins, holdout_parent_asin, k, prefix="baseline_")

            if dry_run:
                row["status"] = "dry_run"
                rows.append(row)
                continue

            request = RecommendationRequest(
                user_id=str(row["user_id"]),
                category=category,
                request=request_text,
                limit=k,
                context={
                    "evaluation": True,
                    "evaluation_holdout_parent_asin": holdout_parent_asin,
                    "evaluation_holdout_review_id": row["holdout_review_id"],
                    "evaluation_allowed_parent_asins": [holdout_parent_asin],
                },
            )
            output = recommend_func(request, client=client)
            recommended_asins, recommended_titles = recommendation_lists(output, k)
            row["recommended_parent_asins"] = recommended_asins
            row["recommended_titles"] = recommended_titles
            if output.recommendations:
                top = output.recommendations[0]
                row["top_recommendation_parent_asin"] = top.parent_asin
                row["top_recommendation_title"] = top.title
                row["top_recommendation_reason"] = top.reason
            apply_ranking_metrics(row, recommended_asins, holdout_parent_asin, k)
            row["status"] = "success"
        except Exception as exc:
            row["status"] = "failed"
            row["error_message"] = str(exc)
        rows.append(row)

    summary = summarize_task_b(rows, category, k, request_text, model_label)
    paths = evaluation_paths(output_dir, "task_b", category, timestamp=timestamp)
    write_csv(paths["csv"], rows, TASK_B_FIELDS)
    write_json(paths["json"], rows)
    write_json(paths["summary"], summary)
    print(f"[evaluation] Task B results saved to {paths['csv']}")
    print(f"[evaluation] Task B summary saved to {paths['summary']}")
    return {"rows": rows, "summary": summary, "files": {key: str(value) for key, value in paths.items()}}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Task B recommendations against task_b_holdout positives.")
    parser.add_argument("--category", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--user-id")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--request", default=DEFAULT_REQUEST)
    parser.add_argument("--output-dir", default="outputs/evaluation")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model-label", default="current/persona_recommender")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evaluate_task_b(
        category=args.category,
        limit=args.limit,
        user_id=args.user_id,
        k=args.k,
        request_text=args.request,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        model_label=args.model_label,
    )


if __name__ == "__main__":
    main()
