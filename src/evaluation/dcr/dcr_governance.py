from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def check_task_a_governance(row: dict) -> dict:
    simulation_result_stored = _present(row.get("simulated_review_text"))
    real_rating_stored = row.get("true_rating") is not None
    predicted_rating_stored = row.get("predicted_rating") is not None
    real_review_stored = _present(row.get("true_review_text"))
    simulated_review_stored = _present(row.get("simulated_review_text"))
    model_name_recorded = _present(row.get("model_name"))
    prompt_version_recorded = _present(row.get("prompt_version"))
    persona_version_recorded = _present(row.get("persona_version"))

    governance_passed = all([
        simulation_result_stored,
        real_rating_stored,
        predicted_rating_stored,
        real_review_stored,
        simulated_review_stored,
        model_name_recorded,
        prompt_version_recorded,
        persona_version_recorded,
    ])

    return {
        "simulation_result_stored": simulation_result_stored,
        "real_rating_stored": real_rating_stored,
        "predicted_rating_stored": predicted_rating_stored,
        "real_review_stored": real_review_stored,
        "simulated_review_stored": simulated_review_stored,
        "model_name_recorded": model_name_recorded,
        "prompt_version_recorded": prompt_version_recorded,
        "persona_version_recorded": persona_version_recorded,
        "governance_passed": governance_passed,
    }


def check_task_b_governance(row: dict, supabase_client: Any) -> dict:
    run_id = row.get("recommendation_run_id")

    # 1. recommendation_run_stored
    if run_id is None:
        recommendation_run_stored = False
    else:
        try:
            resp = supabase_client.table("recommendation_runs").select("id").eq("id", run_id).limit(1).execute()
            recommendation_run_stored = bool(resp.data)
        except Exception:
            recommendation_run_stored = None

    # 2. intent_plan_stored + sub-fields
    intent_plan_stored: bool | None = None
    intent_plan_has_retrieval_query: bool | None = None
    intent_plan_has_constraints: bool | None = None
    intent_plan_has_model_recorded: bool | None = None

    if run_id is None:
        intent_plan_stored = None
    else:
        try:
            resp = supabase_client.table("intent_plans").select("*").eq("recommendation_run_id", run_id).limit(1).execute()
            if not resp.data:
                intent_plan_stored = False
            else:
                intent_plan_stored = True
                ip = resp.data[0]
                intent_plan_has_retrieval_query = _present(ip.get("retrieval_query"))
                explicit = ip.get("explicit_constraints")
                implicit = ip.get("implicit_constraints")
                intent_plan_has_constraints = (
                    (explicit is not None and explicit != {})
                    or (implicit is not None and implicit != {})
                )
                intent_plan_has_model_recorded = _present(ip.get("model_name"))
        except Exception:
            intent_plan_stored = None

    # 3. candidates_stored
    cc = row.get("candidate_count")
    candidates_stored = cc is not None and cc > 0

    # 4. retrieval_sources_stored
    rs = row.get("retrieval_sources")
    retrieval_sources_stored = rs is not None and rs != {}

    # 5. score_breakdown_stored
    recs = row.get("recommendations")
    score_breakdown_stored: bool | None = None
    if isinstance(recs, list) and len(recs) > 0:
        first = recs[0]
        if isinstance(first, dict):
            score_breakdown_stored = first.get("score_breakdown") is not None
        else:
            score_breakdown_stored = None

    # 6-9. metadata fields
    model_name_recorded = _present(row.get("model_name"))
    prompt_version_recorded = _present(row.get("prompt_version"))
    persona_version_recorded = _present(row.get("persona_version"))
    embedding_model_recorded = _present(row.get("embedding_model"))

    all_checks = [
        recommendation_run_stored,
        intent_plan_stored,
        candidates_stored,
        retrieval_sources_stored,
        score_breakdown_stored,
        model_name_recorded,
        prompt_version_recorded,
        persona_version_recorded,
        embedding_model_recorded,
    ]
    governance_passed = all(c is True for c in all_checks if c is not None)

    return {
        "recommendation_run_stored": recommendation_run_stored,
        "intent_plan_stored": intent_plan_stored,
        "intent_plan_has_retrieval_query": intent_plan_has_retrieval_query,
        "intent_plan_has_constraints": intent_plan_has_constraints,
        "intent_plan_has_model_recorded": intent_plan_has_model_recorded,
        "candidates_stored": candidates_stored,
        "retrieval_sources_stored": retrieval_sources_stored,
        "score_breakdown_stored": score_breakdown_stored,
        "model_name_recorded": model_name_recorded,
        "prompt_version_recorded": prompt_version_recorded,
        "persona_version_recorded": persona_version_recorded,
        "embedding_model_recorded": embedding_model_recorded,
        "governance_passed": governance_passed,
    }
