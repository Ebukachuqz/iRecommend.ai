from __future__ import annotations

import logging
from typing import Any

from src.evaluation.dcr.dcr_behavioural import check_task_a_behaviour, check_task_b_behaviour
from src.evaluation.dcr.dcr_governance import check_task_a_governance, check_task_b_governance
from src.evaluation.dcr.dcr_contextual import check_task_a_context, check_task_b_context
from src.evaluation.utils import word_count

logger = logging.getLogger(__name__)


def classify_task_a_row(row: dict, behaviour: dict, governance: dict, context: dict) -> str:
    # Hard failures → Red
    review_text = row.get("simulated_review_text")
    if not review_text or (isinstance(review_text, str) and not review_text.strip()):
        return "Red"
    try:
        pr = float(row.get("predicted_rating"))
        if pr < 1 or pr > 5:
            return "Red"
    except (TypeError, ValueError):
        return "Red"
    if behaviour.get("hallucination_detected") is True:
        return "Red"
    if behaviour.get("product_grounding_check") == "contradiction":
        return "Red"
    if governance.get("simulation_result_stored") is False:
        return "Red"
    if governance.get("real_review_stored") is False:
        return "Red"
    if context.get("correct_category_used") is False:
        return "Red"

    # Green conditions
    if (
        behaviour.get("behaviour_passed") is True
        and governance.get("governance_passed") is True
        and context.get("context_passed") is True
    ):
        abs_error = row.get("absolute_error")
        rouge_l = row.get("rouge_l")
        error_ok = abs_error is not None and abs_error <= 1.5
        rouge_ok = rouge_l is None or rouge_l >= 0.10
        if error_ok and rouge_ok:
            return "Green"

    return "Yellow"


def classify_task_b_row(row: dict, behaviour: dict, governance: dict, context: dict) -> str:
    # Hard failures → Red
    recs = row.get("recommendations")
    if not recs or not isinstance(recs, list) or len(recs) == 0:
        return "Red"
    if behaviour.get("reviewed_product_recommended") is True:
        return "Red"
    if (
        context.get("holdout_not_wrongly_excluded") is False
        and (row.get("candidate_count") is None or row.get("candidate_count") == 0)
    ):
        return "Red"
    if governance.get("recommendation_run_stored") is False:
        return "Red"
    if context.get("correct_category_used") is False:
        return "Red"

    # Green conditions
    if (
        behaviour.get("behaviour_passed") is True
        and governance.get("governance_passed") is True
        and context.get("context_passed") is True
    ):
        hit = row.get("hit_at_10")
        rank = row.get("rank_of_holdout")
        if hit == 1 or rank is not None:
            return "Green"

    return "Yellow"


def apply_task_a_classifications(
    rows: list[dict],
    product_snapshots: dict[str, dict],
    supabase_client: Any,
) -> list[dict]:
    for row in rows:
        if row.get("status") != "success":
            row["dcr_classification"] = None
            continue

        asin = row.get("parent_asin")
        product_snapshot = product_snapshots.get(asin) if asin else None
        if product_snapshot is None:
            row["dcr_classification"] = "Red"
            logger.warning("Missing product snapshot for parent_asin %s — classified Red.", asin)
            continue

        behaviour = check_task_a_behaviour(row, product_snapshot)
        governance = check_task_a_governance(row)
        context = check_task_a_context(row, product_snapshot)

        classification = classify_task_a_row(row, behaviour, governance, context)
        row.update(behaviour)
        row.update(governance)
        row.update(context)
        row["dcr_classification"] = classification

        if classification == "Red":
            reasons = []
            if not behaviour.get("behaviour_passed"):
                reasons.append(f"behaviour_failed({behaviour})")
            if not governance.get("governance_passed"):
                reasons.append(f"governance_failed({governance})")
            if not context.get("context_passed"):
                reasons.append(f"context_failed({context})")
            logger.warning(
                "Task A Red — user=%s asin=%s reasons=%s",
                row.get("user_id"), asin, "; ".join(reasons) if reasons else "hard_failure",
            )

    return rows


def apply_task_b_classifications(
    rows: list[dict],
    product_snapshots: dict[str, dict],
    persona_train_asins: dict[str, list[str]],
    supabase_client: Any,
) -> list[dict]:
    for row in rows:
        if row.get("status") != "success":
            row["dcr_classification"] = None
            continue

        user_id = row.get("user_id")
        train_asins = persona_train_asins.get(user_id, []) if user_id else []

        asin = row.get("holdout_asin") or row.get("parent_asin")
        product_snapshot = product_snapshots.get(asin) if asin else None
        if product_snapshot is None:
            row["dcr_classification"] = "Red"
            logger.warning("Missing product snapshot for asin %s — classified Red.", asin)
            continue

        behaviour = check_task_b_behaviour(row, train_asins)
        governance = check_task_b_governance(row, supabase_client)
        context = check_task_b_context(
            row,
            product_snapshot,
            train_asins,
            is_evaluation_run=bool(row.get("evaluation_mode") or row.get("is_evaluation_run")),
            holdout_asin=row.get("holdout_asin", ""),
            supabase_client=supabase_client,
        )

        classification = classify_task_b_row(row, behaviour, governance, context)
        row.update(behaviour)
        row.update(governance)
        row.update(context)
        row["dcr_classification"] = classification

        if classification == "Red":
            reasons = []
            if not behaviour.get("behaviour_passed"):
                reasons.append(f"behaviour_failed({behaviour})")
            if not governance.get("governance_passed"):
                reasons.append(f"governance_failed({governance})")
            if not context.get("context_passed"):
                reasons.append(f"context_failed({context})")
            logger.warning(
                "Task B Red — user=%s asin=%s reasons=%s",
                user_id, asin, "; ".join(reasons) if reasons else "hard_failure",
            )

    return rows
