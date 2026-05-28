"""
DCR-inspired reclassification analysis for iRecommend evaluation outputs.

This module compares standard task-metric pass/fail results against
DCR-inspired Green/Yellow/Red classifications. It reports how many outputs
that passed standard metrics were downgraded after behavioural, contextual,
and governance checks.
"""

from __future__ import annotations

from collections import Counter


def _task_a_downgrade_reason(row: dict) -> str:
    if row.get("error_message") is not None:
        return row["error_message"]
    if row.get("hallucination_detected") is True:
        return "hallucination_detected"
    if row.get("product_grounding_check") == "contradiction":
        return "category_contradiction"
    if row.get("correct_category_used") is False:
        return "wrong_category"
    if row.get("simulation_result_stored") is False:
        return "missing_simulation_trace"
    if row.get("review_non_empty") is False:
        return "empty_review"
    if row.get("rating_valid") is False:
        return "invalid_rating"
    rouge = row.get("rouge_l")
    if rouge is not None and rouge < 0.10:
        return "very_low_rouge"
    if row.get("governance_passed") is False:
        return "governance_trace_incomplete"
    return "other"


def _task_b_downgrade_reason(row: dict) -> str:
    if row.get("error_message") is not None:
        return row["error_message"]
    if row.get("reviewed_product_recommended") is True:
        return "reviewed_product_recommended"
    if row.get("recommendation_run_stored") is False:
        return "missing_run_trace"
    if row.get("correct_category_used") is False:
        return "wrong_category"
    if row.get("output_valid") is False:
        return "empty_recommendations"
    if row.get("holdout_not_wrongly_excluded") is False:
        return "holdout_excluded_from_pool"
    if row.get("retrieval_sources_stored") is False:
        return "missing_retrieval_sources"
    if row.get("intent_plan_stored") is False:
        return "missing_intent_plan"
    return "other"


def _build_result(
    rows: list[dict],
    standard_pass_flags: list[bool],
    reason_fn,
) -> dict:
    total = len(rows)
    sp = sum(standard_pass_flags)
    sf = total - sp

    green = sum(1 for r in rows if r.get("dcr_classification") == "Green")
    yellow = sum(1 for r in rows if r.get("dcr_classification") == "Yellow")
    red = sum(1 for r in rows if r.get("dcr_classification") == "Red")
    not_classified = sum(1 for r in rows if r.get("dcr_classification") is None)

    reasons: list[str] = []
    downgraded = 0
    for row, passed in zip(rows, standard_pass_flags):
        if passed and row.get("dcr_classification") in ("Yellow", "Red"):
            downgraded += 1
            reasons.append(reason_fn(row))

    counter = Counter(reasons)
    top_reasons = [r for r, _ in counter.most_common(5)]

    return {
        "total_rows": total,
        "standard_pass": sp,
        "standard_fail": sf,
        "green": green,
        "yellow": yellow,
        "red": red,
        "not_classified": not_classified,
        "downgraded_count": downgraded,
        "downgrade_percentage": (downgraded / sp * 100) if sp > 0 else 0.0,
        "most_common_downgrade_reasons": top_reasons,
    }


def run_task_a_reclassification(rows: list[dict]) -> dict:
    flags = []
    for r in rows:
        rouge = r.get("rouge_l")
        passed = (
            r.get("status") == "success"
            and r.get("absolute_error") is not None
            and r["absolute_error"] <= 1.5
            and (rouge is None or rouge >= 0.10)
        )
        flags.append(passed)

    return _build_result(rows, flags, _task_a_downgrade_reason)


def run_task_b_reclassification(rows: list[dict]) -> dict:
    flags = [
        r.get("status") == "success" and r.get("hit_at_10") == 1
        for r in rows
    ]
    return _build_result(rows, flags, _task_b_downgrade_reason)
