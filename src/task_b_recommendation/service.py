from __future__ import annotations

from typing import Any

from supabase import Client

from src.task_b_recommendation.candidate_retriever import retrieve_candidates
from src.task_b_recommendation.graph import (
    build_intent_plan_payload,
    build_or_get_user_taste_vector,
    candidate_trace_rows,
    final_rank_by_parent_asin,
    load_or_create_session,
    resolve_persona_for_recommendation,
    run_task_b_graph,
    store_candidate_traces,
    store_intent_plan_trace,
    store_recommendation_run,
    store_recommendation_traces_best_effort,
)
from src.task_b_recommendation.intent_planner import plan_intent
from src.task_b_recommendation.schema import RecommendationOutput, RecommendationRequest
from src.task_b_recommendation.scoring import score_candidates
from src.task_b_recommendation.vector_store import VectorStore


class TaskBServiceError(RuntimeError):
    pass


def list_recommendation_candidates(
    user_id: str | None,
    category: str,
    persona: dict[str, Any],
    request_text: str | None = None,
    limit: int = 50,
    client: Client | None = None,
    vector_store: VectorStore | None = None,
):
    intent = plan_intent(persona, request_text)
    candidates = retrieve_candidates(user_id, category, intent, limit=limit, client=client, vector_store=vector_store)
    return score_candidates(candidates, persona, intent)


def recommend(request: RecommendationRequest, client: Client | None = None, vector_store: VectorStore | None = None) -> RecommendationOutput:
    return run_task_b_graph(request, client=client, vector_store=vector_store)


def recommend_for_user(
    user_id: str,
    category: str = "All_Beauty",
    request: str | None = None,
    limit: int = 5,
    session_id: str | None = None,
    cold_start: bool = False,
    client: Client | None = None,
    vector_store: VectorStore | None = None,
) -> RecommendationOutput:
    return recommend(
        RecommendationRequest(
            user_id=user_id,
            category=category,
            request=request,
            limit=limit,
            session_id=session_id,
            cold_start=cold_start,
        ),
        client=client,
        vector_store=vector_store,
    )


def recommend_from_persona(
    persona: dict[str, Any] | str,
    request: str | None = None,
    limit: int = 5,
    client: Client | None = None,
    vector_store: VectorStore | None = None,
) -> RecommendationOutput:
    return recommend(
        RecommendationRequest(
            persona=persona,
            request=request,
            limit=limit,
            cold_start=True,
        ),
        client=client,
        vector_store=vector_store,
    )
