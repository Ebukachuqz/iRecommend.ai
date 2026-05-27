from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def check_task_a_context(row: dict, product_snapshot: dict) -> dict:
    row_cat = row.get("category")
    prod_cat = product_snapshot.get("category")

    if row_cat is None or prod_cat is None:
        correct_category_used = None
    else:
        correct_category_used = row_cat == prod_cat

    persona_evidence_present = (
        row.get("persona_version") is not None
        and str(row.get("persona_version", "")).strip() != ""
        and row.get("simulated_review_text") is not None
        and str(row.get("simulated_review_text", "")).strip() != ""
    )

    non_none = [v for v in [correct_category_used, persona_evidence_present] if v is not None]
    context_passed = all(non_none) if non_none else True

    return {
        "correct_category_used": correct_category_used,
        "persona_evidence_present": persona_evidence_present,
        "context_passed": context_passed,
    }


def _extract_rec_asins(recommendations: Any) -> set[str]:
    if not isinstance(recommendations, list):
        return set()
    asins = set()
    for r in recommendations:
        asin = r.get("parent_asin") if isinstance(r, dict) else r
        if asin:
            asins.add(str(asin))
    return asins


def check_task_b_context(
    row: dict,
    product_snapshot: dict,
    persona_train_asins: list[str],
    is_evaluation_run: bool,
    holdout_asin: str,
    supabase_client: Any = None,
) -> dict:
    # 1. correct_category_used
    row_cat = row.get("category")
    prod_cat = product_snapshot.get("category")
    if row_cat is None or prod_cat is None:
        correct_category_used = None
    else:
        correct_category_used = row_cat == prod_cat

    # 2. request_constraints_reflected
    rs = row.get("retrieval_sources")
    if rs is None:
        request_constraints_reflected = None
    else:
        request_constraints_reflected = bool(rs) and rs != {}

    # 3. persona_train_products_excluded
    recs = row.get("recommendations")
    rec_asins = _extract_rec_asins(recs)
    if not rec_asins:
        persona_train_products_excluded = None
    else:
        train_set = set(str(a) for a in persona_train_asins) if persona_train_asins else set()
        persona_train_products_excluded = not bool(rec_asins & train_set)

    # 4. holdout_not_wrongly_excluded
    holdout_not_wrongly_excluded: bool | None = None
    holdout_in_candidate_pool: bool | None = None
    if not is_evaluation_run:
        holdout_not_wrongly_excluded = None
    else:
        run_id = row.get("recommendation_run_id")
        resolved_via_candidates = False

        if supabase_client is not None and run_id is not None:
            try:
                resp = (
                    supabase_client.table("recommendation_candidates")
                    .select("parent_asin")
                    .eq("recommendation_run_id", run_id)
                    .eq("parent_asin", holdout_asin)
                    .limit(1)
                    .execute()
                )
                holdout_in_candidate_pool = bool(resp.data)
                if resp.data:
                    holdout_not_wrongly_excluded = True
                else:
                    holdout_not_wrongly_excluded = False
                    logger.warning(
                        "Holdout %s not found in candidate pool for run %s. "
                        "Evaluation may be invalid.",
                        holdout_asin, run_id,
                    )
                resolved_via_candidates = True
            except Exception:
                pass

        if not resolved_via_candidates:
            cc = row.get("candidate_count")
            if cc is None or cc == 0:
                holdout_not_wrongly_excluded = False
            elif holdout_asin and holdout_asin in rec_asins:
                holdout_not_wrongly_excluded = True
                holdout_in_candidate_pool = True
            else:
                holdout_not_wrongly_excluded = None
                logger.warning(
                    "Cannot verify holdout pool inclusion for user %s. "
                    "recommendation_candidates unavailable. "
                    "Holdout may have been excluded or ranked below K.",
                    row.get("user_id"),
                )

    # 5. cross_domain_values_used
    cross_domain_values_used: bool | None = None
    rs_dict = row.get("retrieval_sources")
    if isinstance(rs_dict, dict) and rs_dict.get("cross_domain") is True:
        cross_domain_values_used = True

    # context_passed
    checks = [
        correct_category_used,
        request_constraints_reflected,
        persona_train_products_excluded,
        holdout_not_wrongly_excluded,
        cross_domain_values_used,
    ]
    non_none = [v for v in checks if v is not None]
    context_passed = all(non_none) if non_none else True

    if (
        holdout_not_wrongly_excluded is False
        and (row.get("candidate_count") is None or row.get("candidate_count") == 0)
    ):
        context_passed = False

    return {
        "correct_category_used": correct_category_used,
        "request_constraints_reflected": request_constraints_reflected,
        "persona_train_products_excluded": persona_train_products_excluded,
        "holdout_not_wrongly_excluded": holdout_not_wrongly_excluded,
        "holdout_in_candidate_pool": holdout_in_candidate_pool,
        "cross_domain_values_used": cross_domain_values_used,
        "context_passed": context_passed,
    }

