from __future__ import annotations

import importlib.util
import logging
import math
from typing import Any

from src.evaluation.utils import (
    fetch_all_paginated,
    get_user_average_rating,
    get_user_typical_review_length,
    resolve_category_for_reviews,
    word_count,
)
from src.db.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

BERTSCORE_AVAILABLE = importlib.util.find_spec("bert_score") is not None
if not BERTSCORE_AVAILABLE:
    logger.info("bert_score not installed. bertscore_f1 will be None for all rows.")

try:
    from rouge_score import rouge_scorer as _rouge_scorer_mod
    _ROUGE_AVAILABLE = True
except ImportError:
    _ROUGE_AVAILABLE = False


def fetch_task_a_holdout_data(
    categories: list[str],
    limit: int | None = None,
    supabase_client: Any = None,
) -> list[dict]:
    if supabase_client is None:
        supabase_client = get_supabase_client()

    reviews = fetch_all_paginated(
        supabase_client,
        "amazon_reviews",
        filters=[("task_split", "eq", "task_a_holdout")],
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

    # Match each review to a simulation result
    enriched = []
    for review in filtered:
        sim = _match_simulation(review, supabase_client)

        entry = {
            "review": review,
            "simulation": sim,
            "status": "success" if sim else "skipped",
            "error_message": None if sim else "no simulation result found",
        }
        enriched.append(entry)

    # Fetch personas and products in batch
    user_cat_keys = set()
    asin_keys = set()
    for e in enriched:
        r = e["review"]
        user_cat_keys.add((r["user_id"], r["category"]))
        asin_keys.add(r["parent_asin"])

    personas = _fetch_personas_batch(user_cat_keys, supabase_client)
    products = _fetch_products_batch(list(asin_keys), supabase_client)

    for e in enriched:
        r = e["review"]
        e["persona_row"] = personas.get((r["user_id"], r["category"]), {})
        e["product"] = products.get(r["parent_asin"], {})

    return enriched


def _match_simulation(review: dict, supabase_client: Any) -> dict | None:
    rid = review.get("review_id")
    if rid:
        resp = supabase_client.table("simulation_results").select("*").eq("holdout_review_id", rid).limit(1).execute()
        if resp.data:
            return resp.data[0]

    uid = review.get("user_id")
    asin = review.get("parent_asin")
    if uid and asin:
        resp = (
            supabase_client.table("simulation_results")
            .select("*")
            .eq("user_id", uid)
            .eq("parent_asin", asin)
            .limit(1)
            .execute()
        )
        if resp.data:
            logger.warning("Fallback simulation match used for user_id=%s parent_asin=%s", uid, asin)
            return resp.data[0]

    return None


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


def _fetch_products_batch(
    asins: list[str], supabase_client: Any
) -> dict[str, dict]:
    if not asins:
        return {}
    chunk_size = 500
    result = {}
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


def compute_task_a_row(
    review: dict,
    simulation: dict,
    persona_row: dict,
    product: dict,
) -> dict:
    persona = persona_row.get("persona", {}) if persona_row else {}
    try:
        true_rating = float(review["rating"])
        predicted_rating = float(simulation["final_predicted_rating"])
        absolute_error = abs(true_rating - predicted_rating)
        squared_error = (true_rating - predicted_rating) ** 2
        exact_match = 1 if round(predicted_rating) == round(true_rating) else 0
        within_1_star = 1 if abs(true_rating - predicted_rating) <= 1 else 0
        baseline_predicted_rating = get_user_average_rating(persona)
        baseline_absolute_error = abs(true_rating - baseline_predicted_rating)
        true_review_text = review.get("text")
        simulated_review_text = simulation.get("simulated_review_text")
        review_length_delta = word_count(simulated_review_text) - word_count(true_review_text)
        user_typical_review_length_delta = word_count(simulated_review_text) - get_user_typical_review_length(persona)
        persona_version = simulation.get("persona_version") or persona_row.get("persona_version")

        return {
            "category": review.get("category"),
            "user_id": review.get("user_id"),
            "review_id": review.get("review_id"),
            "parent_asin": review.get("parent_asin"),
            "product_title": product.get("title"),
            "true_rating": true_rating,
            "predicted_rating": predicted_rating,
            "absolute_error": absolute_error,
            "squared_error": squared_error,
            "exact_match": exact_match,
            "within_1_star": within_1_star,
            "baseline_predicted_rating": baseline_predicted_rating,
            "baseline_absolute_error": baseline_absolute_error,
            "true_review_title": review.get("title"),
            "true_review_text": true_review_text,
            "simulated_review_text": simulated_review_text,
            "rouge_l": None,
            "bertscore_f1": None,
            "review_length_delta": review_length_delta,
            "user_typical_review_length_delta": user_typical_review_length_delta,
            "dcr_classification": None,
            "status": "success",
            "error_message": None,
            "model_name": simulation.get("model_name"),
            "prompt_version": simulation.get("prompt_version"),
            "persona_version": persona_version,
        }
    except Exception as exc:
        return {
            "category": review.get("category"),
            "user_id": review.get("user_id"),
            "review_id": review.get("review_id"),
            "parent_asin": review.get("parent_asin"),
            "product_title": product.get("title"),
            "true_rating": None,
            "predicted_rating": None,
            "absolute_error": None,
            "squared_error": None,
            "exact_match": None,
            "within_1_star": None,
            "baseline_predicted_rating": None,
            "baseline_absolute_error": None,
            "true_review_title": None,
            "true_review_text": None,
            "simulated_review_text": None,
            "rouge_l": None,
            "bertscore_f1": None,
            "review_length_delta": None,
            "user_typical_review_length_delta": None,
            "dcr_classification": None,
            "status": "error",
            "error_message": str(exc),
            "model_name": None,
            "prompt_version": None,
            "persona_version": None,
        }


def _compute_rouge_l_batch(rows: list[dict]) -> None:
    if not _ROUGE_AVAILABLE:
        logger.info("rouge_score not installed. rouge_l will be None for all rows.")
        return

    scorer = _rouge_scorer_mod.RougeScorer(["rougeL"], use_stemmer=True)
    for row in rows:
        if row.get("status") != "success":
            continue
        true_text = row.get("true_review_text")
        sim_text = row.get("simulated_review_text")
        if true_text and sim_text and isinstance(true_text, str) and isinstance(sim_text, str):
            try:
                result = scorer.score(true_text, sim_text)
                row["rouge_l"] = result["rougeL"].fmeasure
            except Exception:
                row["rouge_l"] = None


def _compute_bertscore_batch(rows: list[dict], skip: bool) -> None:
    if skip or not BERTSCORE_AVAILABLE:
        return

    indices = []
    hypotheses = []
    references = []
    for i, row in enumerate(rows):
        if row.get("status") != "success":
            continue
        sim = row.get("simulated_review_text")
        true = row.get("true_review_text")
        if sim and true and isinstance(sim, str) and isinstance(true, str):
            indices.append(i)
            hypotheses.append(sim)
            references.append(true)

    if not hypotheses:
        return

    try:
        import bert_score
        P, R, F1 = bert_score.score(
            hypotheses, references,
            model_type="distilbert-base-uncased",
            verbose=False,
        )
        for idx, f1 in zip(indices, F1.tolist()):
            rows[idx]["bertscore_f1"] = f1
    except Exception as exc:
        logger.error("BERTScore computation failed: %s", exc)
        for idx in indices:
            rows[idx]["bertscore_f1"] = None


def compute_task_a_summary(rows: list[dict]) -> dict:
    success = [r for r in rows if r.get("status") == "success"]

    def _mean(key):
        vals = [float(r[key]) for r in success if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    total_evaluated = len(success)
    total_skipped = sum(1 for r in rows if r.get("status") == "skipped")
    total_errors = sum(1 for r in rows if r.get("status") == "error")

    mae = _mean("absolute_error")
    sq = _mean("squared_error")
    rmse = math.sqrt(sq) if sq is not None else None

    bias_vals = [r["predicted_rating"] - r["true_rating"] for r in success
                 if r.get("predicted_rating") is not None and r.get("true_rating") is not None]
    optimistic_bias = sum(bias_vals) / len(bias_vals) if bias_vals else None

    return {
        "MAE": mae,
        "RMSE": rmse,
        "exact_rating_accuracy": _mean("exact_match"),
        "within_1_star_accuracy": _mean("within_1_star"),
        "optimistic_bias": optimistic_bias,
        "baseline_MAE": _mean("baseline_absolute_error"),
        "avg_rouge_l": _mean("rouge_l"),
        "avg_bertscore_f1": _mean("bertscore_f1"),
        "avg_review_length_delta": _mean("review_length_delta"),
        "avg_user_typical_length_delta": _mean("user_typical_review_length_delta"),
        "total_evaluated": total_evaluated,
        "total_skipped": total_skipped,
        "total_errors": total_errors,
    }


def run_task_a_eval(
    categories: list[str],
    limit: int | None = None,
    skip_bertscore: bool = False,
    supabase_client: Any = None,
) -> tuple[list[dict], dict]:
    if supabase_client is None:
        supabase_client = get_supabase_client()

    data = fetch_task_a_holdout_data(categories, limit=limit, supabase_client=supabase_client)

    rows = []
    for entry in data:
        if entry["status"] == "skipped":
            rev = entry["review"]
            rows.append({
                "category": rev.get("category"),
                "user_id": rev.get("user_id"),
                "review_id": rev.get("review_id"),
                "parent_asin": rev.get("parent_asin"),
                "product_title": entry.get("product", {}).get("title"),
                "true_rating": rev.get("rating"), "predicted_rating": None,
                "absolute_error": None, "squared_error": None,
                "exact_match": None, "within_1_star": None,
                "baseline_predicted_rating": None, "baseline_absolute_error": None,
                "true_review_title": rev.get("title"), "true_review_text": rev.get("text"),
                "simulated_review_text": None,
                "rouge_l": None, "bertscore_f1": None,
                "review_length_delta": None, "user_typical_review_length_delta": None,
                "dcr_classification": None,
                "status": "skipped",
                "error_message": entry["error_message"],
                "model_name": None, "prompt_version": None, "persona_version": None,
            })
            continue

        row = compute_task_a_row(
            entry["review"], entry["simulation"],
            entry["persona_row"], entry["product"],
        )
        rows.append(row)

    _compute_rouge_l_batch(rows)
    _compute_bertscore_batch(rows, skip=skip_bertscore)

    summary = compute_task_a_summary(rows)
    return rows, summary
