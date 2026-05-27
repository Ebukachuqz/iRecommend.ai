from __future__ import annotations

import logging
import math
from typing import Any

from src.evaluation.utils import (
    fetch_all_paginated,
    resolve_category_for_reviews,
)
from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.service import recommend
from src.task_b_recommendation.schema import RecommendationRequest

logger = logging.getLogger(__name__)


def fetch_task_b_holdout_data(
    categories: list[str],
    limit: int | None = None,
    supabase_client: Any = None,
) -> dict:
    if supabase_client is None:
        supabase_client = get_supabase_client()

    reviews = fetch_all_paginated(
        supabase_client,
        "amazon_reviews",
        filters=[
            ("task_split", "eq", "task_b_holdout"),
            ("rating", "gte", 4),
        ],
    )

    resolve_category_for_reviews(reviews, supabase_client)

    filtered = []
    for r in reviews:
        cat = r.get("category")
        if cat is None:
            logger.warning("Skipping review %s — category could not be resolved.", r.get("review_id"))
            continue
        if cat in categories:
            filtered.append(r)

    if limit is not None:
        filtered = filtered[:limit]

    asin_set = set()
    user_cat_keys = set()
    user_ids = set()
    for r in filtered:
        asin_set.add(r["parent_asin"])
        user_cat_keys.add((r["user_id"], r["category"]))
        user_ids.add(r["user_id"])

    product_lookup = _fetch_products_batch(list(asin_set), supabase_client)
    persona_lookup = _fetch_personas_batch(user_cat_keys, supabase_client)
    persona_train_asins_lookup = _fetch_persona_train_asins(list(user_ids), supabase_client)

    return {
        "reviews": filtered,
        "product_lookup": product_lookup,
        "persona_lookup": persona_lookup,
        "persona_train_asins_lookup": persona_train_asins_lookup,
    }


def _fetch_products_batch(asins: list[str], supabase_client: Any) -> dict[str, dict]:
    if not asins:
        return {}
    result = {}
    chunk_size = 500
    for start in range(0, len(asins), chunk_size):
        chunk = asins[start : start + chunk_size]
        rows = fetch_all_paginated(
            supabase_client,
            "amazon_product_metadata",
            filters=[("parent_asin", "in_", chunk)],
        )
        for row in rows:
            result[row["parent_asin"]] = row
    return result


def _fetch_personas_batch(
    keys: set[tuple[str, str]], supabase_client: Any
) -> dict[tuple[str, str], dict]:
    if not keys:
        return {}
    rows = fetch_all_paginated(supabase_client, "user_personas")
    result = {}
    for row in rows:
        k = (row["user_id"], row["category"])
        if k in keys:
            result[k] = row
    return result


def _fetch_persona_train_asins(
    user_ids: list[str], supabase_client: Any
) -> dict[str, list[str]]:
    if not user_ids:
        return {}
    chunk_size = 500
    all_rows: list[dict] = []
    for start in range(0, len(user_ids), chunk_size):
        chunk = user_ids[start : start + chunk_size]
        rows = fetch_all_paginated(
            supabase_client,
            "amazon_reviews",
            select="user_id,parent_asin",
            filters=[
                ("user_id", "in_", chunk),
                ("task_split", "eq", "persona_train"),
            ],
        )
        all_rows.extend(rows)

    result: dict[str, list[str]] = {}
    for row in all_rows:
        uid = row["user_id"]
        result.setdefault(uid, []).append(row["parent_asin"])
    return result


def _extract_rec_asins(output: Any) -> list[str]:
    recs = getattr(output, "recommendations", None) or []
    asins = []
    for r in recs:
        if hasattr(r, "parent_asin"):
            asins.append(r.parent_asin)
        elif isinstance(r, dict):
            asins.append(r.get("parent_asin", ""))
        else:
            asins.append(str(r))
    return asins


def _extract_rec_reasons(output: Any) -> list[str]:
    recs = getattr(output, "recommendations", None) or []
    reasons = []
    for r in recs:
        if hasattr(r, "reason"):
            reasons.append(r.reason)
        elif isinstance(r, dict):
            reasons.append(r.get("reason", ""))
        else:
            reasons.append("")
    return reasons


def _compute_ranking_metrics(holdout_asin: str, rec_asins: list[str]) -> dict:
    rank_of_holdout = None
    for i, asin in enumerate(rec_asins, 1):
        if asin == holdout_asin:
            rank_of_holdout = i
            break

    hit_at_10 = 1 if rank_of_holdout is not None else 0

    if rank_of_holdout is not None:
        dcg = 1.0 / math.log2(rank_of_holdout + 1)
        idcg = 1.0 / math.log2(2)
        ndcg_score = dcg / idcg
    else:
        ndcg_score = 0.0

    reciprocal_rank = 1.0 / rank_of_holdout if rank_of_holdout else 0.0

    return {
        "rank_of_holdout": rank_of_holdout,
        "hit_at_10": hit_at_10,
        "ndcg_score": ndcg_score,
        "reciprocal_rank": reciprocal_rank,
    }


def _check_holdout_in_candidate_pool(
    recommendation_run_id: str | None,
    holdout_asin: str,
    hit_at_10: int,
    candidate_count: int | None,
    supabase_client: Any,
) -> bool | None:
    if recommendation_run_id and supabase_client:
        try:
            resp = (
                supabase_client.table("recommendation_candidates")
                .select("parent_asin")
                .eq("recommendation_run_id", recommendation_run_id)
                .eq("parent_asin", holdout_asin)
                .limit(1)
                .execute()
            )
            return bool(resp.data)
        except Exception:
            pass

    if hit_at_10 == 1:
        return True
    if candidate_count is not None and candidate_count == 0:
        return False
    return None


def _compute_baseline(
    category: str,
    holdout_asin: str,
    persona_train_asins: list[str],
    k: int,
    supabase_client: Any,
) -> dict:
    rows = fetch_all_paginated(
        supabase_client,
        "amazon_product_metadata",
        select="parent_asin,average_rating,rating_number",
        filters=[("category", "eq", category)],
    )

    train_set = set(persona_train_asins) if persona_train_asins else set()
    eligible = [r for r in rows if r["parent_asin"] not in train_set]
    eligible.sort(
        key=lambda r: (r.get("rating_number") or 0, r.get("average_rating") or 0.0),
        reverse=True,
    )

    baseline_asins = [r["parent_asin"] for r in eligible[:k]]
    metrics = _compute_ranking_metrics(holdout_asin, baseline_asins)

    return {
        "baseline_recommendations": baseline_asins,
        "baseline_rank_of_holdout": metrics["rank_of_holdout"],
        "baseline_hit_at_10": metrics["hit_at_10"],
        "baseline_ndcg_score": metrics["ndcg_score"],
        "baseline_reciprocal_rank": metrics["reciprocal_rank"],
    }


def _build_empty_row(review: dict, product: dict, status: str, error_message: str | None) -> dict:
    return {
        "category": review.get("category"),
        "user_id": review.get("user_id"),
        "holdout_review_id": review.get("review_id"),
        "holdout_asin": review.get("parent_asin"),
        "holdout_product_title": product.get("title"),
        "holdout_rating": review.get("rating"),
        "rank_of_holdout": None, "hit_at_10": None,
        "ndcg_score": None, "reciprocal_rank": None,
        "holdout_in_candidate_pool": None, "evaluation_mode": True,
        "recommendations": None, "recommendation_reasons": [],
        "candidate_count": None, "retrieval_sources": None,
        "baseline_recommendations": None,
        "baseline_rank_of_holdout": None, "baseline_hit_at_10": None,
        "baseline_ndcg_score": None, "baseline_reciprocal_rank": None,
        "recommendation_run_id": None, "dcr_classification": None,
        "status": status, "error_message": error_message,
        "model_name": None, "prompt_version": None,
        "persona_version": None, "embedding_model": None,
    }


def evaluate_task_b_row(
    review: dict,
    persona_row: dict,
    product: dict,
    persona_train_asins: list[str],
    k: int = 10,
    force_rerun: bool = False,
    supabase_client: Any = None,
) -> dict:
    if supabase_client is None:
        supabase_client = get_supabase_client()

    holdout_asin = review["parent_asin"]
    user_id = review["user_id"]
    category = review.get("category")

    try:
        existing_run = None
        if not force_rerun:
            resp = (
                supabase_client.table("recommendation_runs")
                .select("*")
                .eq("user_id", user_id)
                .eq("holdout_asin", holdout_asin)
                .eq("is_evaluation_run", True)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if resp.data:
                existing_run = resp.data[0]

        if existing_run:
            stored_recs = (existing_run.get("recommendations") or [])[:k]
            rec_asins = []
            rec_reasons = []
            for r in stored_recs:
                if isinstance(r, dict):
                    rec_asins.append(r.get("parent_asin", ""))
                    rec_reasons.append(r.get("reason", ""))
                else:
                    rec_asins.append(str(r))
                    rec_reasons.append("")

            candidate_count = existing_run.get("candidate_count")
            retrieval_sources = existing_run.get("retrieval_sources")
            model_name = existing_run.get("model_name")
            prompt_version = existing_run.get("prompt_version")
            embedding_model = existing_run.get("embedding_model")
            recommendation_run_id = existing_run.get("id")
        else:
            req = RecommendationRequest(
                user_id=user_id,
                category=category,
                request=f"Recommend products I would like",
                limit=k,
                evaluation_mode=True,
                holdout_asin=holdout_asin,
            )
            output = recommend(req, client=supabase_client)

            rec_asins = _extract_rec_asins(output)[:k]
            rec_reasons = _extract_rec_reasons(output)[:k]
            candidate_count = getattr(output, "candidate_count", None)
            retrieval_sources = None
            model_name = getattr(output, "model_name", None)
            prompt_version = getattr(output, "prompt_version", None)
            embedding_model = None

            # Fetch stored run for run_id and any missing metadata
            resp = (
                supabase_client.table("recommendation_runs")
                .select("id,retrieval_sources,embedding_model,model_name,prompt_version,candidate_count")
                .eq("user_id", user_id)
                .eq("holdout_asin", holdout_asin)
                .eq("is_evaluation_run", True)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if resp.data:
                stored = resp.data[0]
                recommendation_run_id = stored.get("id")
                retrieval_sources = retrieval_sources or stored.get("retrieval_sources")
                embedding_model = embedding_model or stored.get("embedding_model")
                model_name = model_name or stored.get("model_name")
                prompt_version = prompt_version or stored.get("prompt_version")
                candidate_count = candidate_count if candidate_count is not None else stored.get("candidate_count")
            else:
                recommendation_run_id = None

        ranking = _compute_ranking_metrics(holdout_asin, rec_asins)

        holdout_in_candidate_pool = _check_holdout_in_candidate_pool(
            recommendation_run_id, holdout_asin,
            ranking["hit_at_10"], candidate_count, supabase_client,
        )

        baseline = _compute_baseline(
            category, holdout_asin, persona_train_asins, k, supabase_client,
        )

        # Update recommendation_runs with evaluation metrics if run exists
        if recommendation_run_id:
            try:
                supabase_client.table("recommendation_runs").update({
                    "is_evaluation_run": True,
                    "holdout_asin": holdout_asin,
                    "hit_at_10": ranking["hit_at_10"] == 1,
                    "rank_of_holdout": ranking["rank_of_holdout"],
                }).eq("id", recommendation_run_id).execute()
            except Exception as exc:
                logger.warning("Failed to update recommendation_runs: %s", exc)

        persona_version = persona_row.get("persona_version")

        return {
            "category": category,
            "user_id": user_id,
            "holdout_review_id": review.get("review_id"),
            "holdout_asin": holdout_asin,
            "holdout_product_title": product.get("title"),
            "holdout_rating": review.get("rating"),
            "rank_of_holdout": ranking["rank_of_holdout"],
            "hit_at_10": ranking["hit_at_10"],
            "ndcg_score": ranking["ndcg_score"],
            "reciprocal_rank": ranking["reciprocal_rank"],
            "holdout_in_candidate_pool": holdout_in_candidate_pool,
            "evaluation_mode": True,
            "recommendations": rec_asins,
            "recommendation_reasons": rec_reasons,
            "candidate_count": candidate_count,
            "retrieval_sources": retrieval_sources,
            "baseline_recommendations": baseline["baseline_recommendations"],
            "baseline_rank_of_holdout": baseline["baseline_rank_of_holdout"],
            "baseline_hit_at_10": baseline["baseline_hit_at_10"],
            "baseline_ndcg_score": baseline["baseline_ndcg_score"],
            "baseline_reciprocal_rank": baseline["baseline_reciprocal_rank"],
            "recommendation_run_id": recommendation_run_id,
            "dcr_classification": None,
            "status": "success",
            "error_message": None,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "persona_version": persona_version,
            "embedding_model": embedding_model,
        }

    except Exception as exc:
        logger.error("Task B evaluation error for user=%s asin=%s: %s", user_id, holdout_asin, exc)
        return _build_empty_row(review, product, "error", str(exc))


def compute_task_b_summary(rows: list[dict]) -> dict:
    success = [r for r in rows if r.get("status") == "success"]

    def _mean(key):
        vals = [float(r[key]) for r in success if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    return {
        "HitRate_at_10": _mean("hit_at_10"),
        "NDCG_at_10": _mean("ndcg_score"),
        "MRR_at_10": _mean("reciprocal_rank"),
        "avg_rank_of_holdout": _mean("rank_of_holdout"),
        "baseline_HitRate_at_10": _mean("baseline_hit_at_10"),
        "baseline_NDCG_at_10": _mean("baseline_ndcg_score"),
        "baseline_MRR_at_10": _mean("baseline_reciprocal_rank"),
        "holdout_pool_verified_count": sum(1 for r in success if r.get("holdout_in_candidate_pool") is True),
        "holdout_pool_excluded_count": sum(1 for r in success if r.get("holdout_in_candidate_pool") is False),
        "holdout_pool_unknown_count": sum(1 for r in success if r.get("holdout_in_candidate_pool") is None),
        "total_evaluated": len(success),
        "total_skipped": sum(1 for r in rows if r.get("status") == "skipped"),
        "total_errors": sum(1 for r in rows if r.get("status") == "error"),
    }


def run_task_b_eval(
    categories: list[str],
    k: int = 10,
    limit: int | None = None,
    force_rerun: bool = False,
    supabase_client: Any = None,
) -> tuple[list[dict], dict]:
    if supabase_client is None:
        supabase_client = get_supabase_client()

    data = fetch_task_b_holdout_data(categories, limit=limit, supabase_client=supabase_client)

    reviews = data["reviews"]
    product_lookup = data["product_lookup"]
    persona_lookup = data["persona_lookup"]
    train_lookup = data["persona_train_asins_lookup"]

    rows = []
    for review in reviews:
        uid = review["user_id"]
        cat = review.get("category")
        asin = review["parent_asin"]

        persona_row = persona_lookup.get((uid, cat), {})
        product = product_lookup.get(asin, {})
        train_asins = train_lookup.get(uid, [])

        if not product:
            rows.append(_build_empty_row(review, {}, "skipped", "missing holdout product metadata"))
            continue

        if not persona_row:
            rows.append(_build_empty_row(review, product, "skipped", "no persona found"))
            continue

        row = evaluate_task_b_row(
            review, persona_row, product, train_asins,
            k=k, force_rerun=force_rerun, supabase_client=supabase_client,
        )
        rows.append(row)

    summary = compute_task_b_summary(rows)
    return rows, summary
