from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from supabase import Client

from src.config import get_settings
from src.db.queries import fetch_persona
from src.db.supabase_client import get_supabase_client
from src.personas.custom_persona_processor import process_custom_persona
from src.personas.validator import validate_persona
from src.task_b_recommendation.candidate_retriever import CandidateRetrievalResult, retrieve_candidates_with_sources
from src.task_b_recommendation.cold_start import build_cold_start_persona
from src.task_b_recommendation.embeddings import DEFAULT_EMBEDDING_MODEL
from src.task_b_recommendation.intent_planner import INTENT_PROMPT_VERSION, plan_intent
from src.task_b_recommendation.reranker import RERANKER_PROMPT_VERSION, rerank_recommendations
from src.task_b_recommendation.schema import (
    RecommendationOutput,
    RecommendationRequest,
    RecommendationSessionState,
)
from src.task_b_recommendation.scoring import score_candidates
from src.task_b_recommendation.session_state import (
    create_session,
    load_session,
    store_session,
    update_session_after_recommendation,
)
from src.task_b_recommendation.taste_vector import build_and_store_user_taste_vector, fetch_user_taste_vector
from src.task_b_recommendation.vector_store import VectorStore


logger = logging.getLogger(__name__)


class TaskBGraphState(TypedDict, total=False):
    request: RecommendationRequest
    persona: dict[str, Any]
    cold_start: bool
    session: RecommendationSessionState | None
    taste_vector_row: dict[str, Any] | None
    intent: Any
    retrieval_result: CandidateRetrievalResult
    candidates: list[Any]
    scored_candidates: list[Any]
    reranked: Any
    output: RecommendationOutput


def resolve_persona_for_recommendation(
    request: RecommendationRequest,
    client: Client,
) -> tuple[dict[str, Any], bool]:
    if request.persona is not None:
        return process_custom_persona(request.persona), request.cold_start or request.user_id is None
    if request.user_id and not request.cold_start:
        row = fetch_persona(request.user_id, request.category, client=client)
        if row and row.get("persona"):
            return validate_persona(row["persona"], repair=True).model_dump(mode="json"), False
    return build_cold_start_persona(request.request, request.context), True


def build_or_get_user_taste_vector(
    user_id: str,
    category: str = "All_Beauty",
    client: Client | None = None,
) -> dict[str, Any] | None:
    client = client or get_supabase_client()
    existing = fetch_user_taste_vector(user_id, category, client=client)
    if existing:
        return existing
    embedding, sources = build_and_store_user_taste_vector(user_id, category, client=client)
    if not embedding:
        return None
    return {
        "user_id": user_id,
        "category": category,
        "embedding": embedding,
        "source_parent_asins": sources,
    }


def load_or_create_session(
    request: RecommendationRequest,
    persona: dict[str, Any],
    client: Client,
) -> RecommendationSessionState | None:
    if not request.session_id:
        return None
    existing = load_session(request.session_id, client=client)
    if existing:
        return existing
    session = create_session(request.user_id, request.category, persona, session_id=request.session_id)
    store_session(session, client=client)
    return session


def build_intent_plan_payload(
    output: RecommendationOutput,
    recommendation_run_id: str,
) -> dict[str, Any]:
    intent = output.intent
    return {
        "recommendation_run_id": recommendation_run_id,
        "session_id": output.session_id,
        "user_id": output.user_id,
        "category": output.category,
        "raw_request": output.request,
        "interpreted_need": intent.interpreted_need,
        "explicit_constraints": intent.explicit_constraints,
        "implicit_constraints": intent.implicit_constraints_from_persona,
        "retrieval_query": intent.retrieval_query,
        "avoid": intent.avoid,
        "category_filter": intent.category_filter,
        "price_max": intent.price_max,
        "required_attributes": intent.required_attributes,
        "excluded_attributes": intent.excluded_attributes,
        "model_name": output.model_name,
        "prompt_version": output.prompt_version,
    }


def store_intent_plan_trace(
    output: RecommendationOutput,
    recommendation_run_id: str | None,
    client: Client,
) -> None:
    if not recommendation_run_id:
        logger.warning("Skipping intent plan trace persistence because recommendation_run_id is missing.")
        return
    payload = build_intent_plan_payload(output, recommendation_run_id)
    client.table("intent_plans").insert(payload).execute()


def final_rank_by_parent_asin(output: RecommendationOutput) -> dict[str, int]:
    return {
        recommendation.parent_asin: recommendation.rank
        for recommendation in output.recommendations
        if recommendation.parent_asin
    }


def candidate_trace_rows(
    output: RecommendationOutput,
    context: dict[str, Any],
    recommendation_run_id: str | None,
) -> list[dict[str, Any]]:
    if not recommendation_run_id:
        logger.warning("Skipping candidate trace persistence because recommendation_run_id is missing.")
        return []
    final_ranks = final_rank_by_parent_asin(output)
    rows: list[dict[str, Any]] = []
    for rank_before, candidate in enumerate(context.get("scored_candidates") or [], start=1):
        parent_asin = candidate.get("parent_asin")
        if not parent_asin:
            continue
        score_breakdown = candidate.get("score_breakdown") or {}
        retrieval_sources = candidate.get("retrieval_sources") or []
        if not retrieval_sources and candidate.get("retrieval_source"):
            retrieval_sources = [candidate["retrieval_source"]]
        rows.append(
            {
                "recommendation_run_id": recommendation_run_id,
                "parent_asin": parent_asin,
                "candidate_rank": rank_before,
                "rank_before_rerank": rank_before,
                "rank_after_rerank": final_ranks.get(parent_asin),
                "retrieval_source": candidate.get("retrieval_source") or (retrieval_sources[0] if retrieval_sources else None),
                "retrieval_sources": retrieval_sources,
                "semantic_similarity": candidate.get("semantic_similarity"),
                "collaborative_similarity": candidate.get("collaborative_similarity"),
                "final_score": score_breakdown.get("final_score"),
                "score_breakdown": score_breakdown,
            }
        )
    return rows


def store_candidate_traces(
    output: RecommendationOutput,
    context: dict[str, Any],
    recommendation_run_id: str | None,
    client: Client,
) -> None:
    rows = candidate_trace_rows(output, context, recommendation_run_id)
    if not rows:
        return
    client.table("recommendation_candidates").insert(rows).execute()


def store_recommendation_traces_best_effort(
    output: RecommendationOutput,
    context: dict[str, Any],
    recommendation_run_id: str | None,
    client: Client,
) -> None:
    try:
        store_intent_plan_trace(output, recommendation_run_id, client)
    except Exception as exc:
        logger.warning("Failed to persist Task B intent plan trace: %s", exc)
    try:
        store_candidate_traces(output, context, recommendation_run_id, client)
    except Exception as exc:
        logger.warning("Failed to persist Task B candidate traces: %s", exc)


def store_recommendation_run(
    output: RecommendationOutput,
    context: dict[str, Any],
    client: Client,
) -> dict[str, Any]:
    recommendations = [item.model_dump(mode="json") for item in output.recommendations]
    retrieval_sources: dict[str, int] = dict(context.get("retrieval_source_counts") or {})
    if not retrieval_sources:
        for candidate in context.get("retrieved_candidates") or context.get("scored_candidates") or []:
            sources = candidate.get("retrieval_sources") or [candidate.get("retrieval_source") or "unknown"]
            for source in sources:
                retrieval_sources[source] = retrieval_sources.get(source, 0) + 1

    payload = {
        "user_id": output.user_id,
        "category": output.category,
        "request": output.request,
        "context": context,
        "candidate_count": output.candidate_count,
        "retrieval_sources": retrieval_sources,
        "recommendations": recommendations,
        "top_asin": recommendations[0]["parent_asin"] if recommendations else None,
        "cold_start": output.cold_start,
        "cold_start_type": "new_user" if output.cold_start and not output.user_id else None,
        "session_id": output.session_id,
        "model_name": output.model_name,
        "prompt_version": output.prompt_version,
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
    }
    response = client.table("recommendation_runs").insert(payload).execute()
    recommendation_run = response.data[0] if response.data else payload
    store_recommendation_traces_best_effort(
        output,
        context,
        recommendation_run.get("id"),
        client,
    )
    return recommendation_run


def build_task_b_graph(client=None, vector_store: VectorStore | None = None):
    client = client or get_supabase_client()
    settings = get_settings()
    graph = StateGraph(TaskBGraphState)

    def load_or_create_persona(state: TaskBGraphState) -> TaskBGraphState:
        request = state["request"]
        persona, cold_start = resolve_persona_for_recommendation(request, client)
        taste_vector_row = None
        if request.user_id and not cold_start:
            taste_vector_row = build_or_get_user_taste_vector(request.user_id, request.category, client=client)
        return {**state, "persona": persona, "cold_start": cold_start, "taste_vector_row": taste_vector_row}

    def load_session_state(state: TaskBGraphState) -> TaskBGraphState:
        session = load_or_create_session(state["request"], state["persona"], client)
        return {**state, "session": session}

    def plan_request_intent(state: TaskBGraphState) -> TaskBGraphState:
        request = state["request"]
        intent = plan_intent(state["persona"], request.request, state.get("session"))
        return {**state, "intent": intent}

    def retrieve_recommendation_candidates(state: TaskBGraphState) -> TaskBGraphState:
        request = state["request"]
        retrieval_result = retrieve_candidates_with_sources(
            request.user_id,
            request.category,
            state["intent"],
            limit=max(50, request.limit * 5),
            client=client,
            vector_store=vector_store,
            persona=state["persona"],
            taste_vector_row=state.get("taste_vector_row"),
        )
        return {**state, "retrieval_result": retrieval_result, "candidates": retrieval_result.candidates}

    def score_recommendation_candidates(state: TaskBGraphState) -> TaskBGraphState:
        scored = score_candidates(state["candidates"], state["persona"], state["intent"])
        return {**state, "scored_candidates": scored}

    def llm_rerank(state: TaskBGraphState) -> TaskBGraphState:
        request = state["request"]
        reranked = rerank_recommendations(
            state["persona"],
            request.request,
            state["intent"],
            state["scored_candidates"],
            limit=request.limit,
        )
        return {**state, "reranked": reranked}

    def update_session_state(state: TaskBGraphState) -> TaskBGraphState:
        session = state.get("session")
        if not session:
            return state
        request = state["request"]
        updated = update_session_after_recommendation(
            session,
            [recommendation.parent_asin for recommendation in state["reranked"].recommendations],
            request.request,
        )
        store_session(updated, client=client)
        return {**state, "session": updated}

    def store_recommendation_run_node(state: TaskBGraphState) -> TaskBGraphState:
        request = state["request"]
        session = state.get("session")
        retrieval_result = state["retrieval_result"]
        output = RecommendationOutput(
            user_id=request.user_id,
            category=request.category,
            request=request.request,
            intent=state["intent"],
            recommendations=state["reranked"].recommendations,
            candidate_count=len(state["scored_candidates"]),
            cold_start=state["cold_start"],
            session_id=session.session_id if session else request.session_id,
            model_name=settings.groq_model,
            prompt_version=f"{INTENT_PROMPT_VERSION}+{RERANKER_PROMPT_VERSION}",
        )
        store_recommendation_run(
            output,
            context={
                **request.context,
                "intent": state["intent"].model_dump(mode="json"),
                "retrieval_source_counts": retrieval_result.source_counts,
                "retrieved_candidates": [candidate.model_dump(mode="json") for candidate in state["candidates"]],
                "scored_candidates": [candidate.model_dump(mode="json") for candidate in state["scored_candidates"]],
            },
            client=client,
        )
        return {**state, "output": output}

    graph.add_node("load_or_create_persona", load_or_create_persona)
    graph.add_node("load_session_state", load_session_state)
    graph.add_node("plan_intent", plan_request_intent)
    graph.add_node("retrieve_candidates", retrieve_recommendation_candidates)
    graph.add_node("score_candidates", score_recommendation_candidates)
    graph.add_node("llm_rerank", llm_rerank)
    graph.add_node("update_session_state", update_session_state)
    graph.add_node("store_recommendation_run", store_recommendation_run_node)

    graph.set_entry_point("load_or_create_persona")
    graph.add_edge("load_or_create_persona", "load_session_state")
    graph.add_edge("load_session_state", "plan_intent")
    graph.add_edge("plan_intent", "retrieve_candidates")
    graph.add_edge("retrieve_candidates", "score_candidates")
    graph.add_edge("score_candidates", "llm_rerank")
    graph.add_edge("llm_rerank", "update_session_state")
    graph.add_edge("update_session_state", "store_recommendation_run")
    graph.add_edge("store_recommendation_run", END)

    return graph.compile()


def run_task_b_graph(
    request: RecommendationRequest,
    client: Client | None = None,
    vector_store: VectorStore | None = None,
) -> RecommendationOutput:
    graph = build_task_b_graph(client=client, vector_store=vector_store)
    final_state = graph.invoke({"request": request})
    return final_state["output"]
