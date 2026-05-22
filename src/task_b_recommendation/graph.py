from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.config import get_settings
from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.candidate_retriever import retrieve_candidates
from src.task_b_recommendation.intent_planner import INTENT_PROMPT_VERSION, plan_intent
from src.task_b_recommendation.reranker import RERANKER_PROMPT_VERSION, rerank_recommendations
from src.task_b_recommendation.schema import RecommendationOutput, RecommendationRequest
from src.task_b_recommendation.scoring import score_candidates
from src.task_b_recommendation.service import (
    load_or_create_session,
    resolve_persona_for_recommendation,
    store_recommendation_run as persist_recommendation_run,
)
from src.task_b_recommendation.session_state import store_session, update_session_after_recommendation
from src.task_b_recommendation.taste_vector import build_and_store_user_taste_vector, fetch_user_taste_vector
from src.task_b_recommendation.vector_store import VectorStore


class TaskBGraphState(TypedDict, total=False):
    request: RecommendationRequest
    persona: dict[str, Any]
    cold_start: bool
    session: Any
    intent: Any
    candidates: list[Any]
    scored_candidates: list[Any]
    reranked: Any
    output: RecommendationOutput


def build_task_b_graph(client=None, vector_store: VectorStore | None = None):
    client = client or get_supabase_client()
    settings = get_settings()
    graph = StateGraph(TaskBGraphState)

    def load_or_create_persona(state: TaskBGraphState) -> TaskBGraphState:
        request = state["request"]
        persona, cold_start = resolve_persona_for_recommendation(request, client)
        if request.user_id and not cold_start and not fetch_user_taste_vector(request.user_id, request.category, client=client):
            build_and_store_user_taste_vector(request.user_id, request.category, client=client)
        return {**state, "persona": persona, "cold_start": cold_start}

    def load_session_state(state: TaskBGraphState) -> TaskBGraphState:
        session = load_or_create_session(state["request"], state["persona"], client)
        return {**state, "session": session}

    def plan_request_intent(state: TaskBGraphState) -> TaskBGraphState:
        request = state["request"]
        intent = plan_intent(state["persona"], request.request, state.get("session"))
        return {**state, "intent": intent}

    def retrieve_recommendation_candidates(state: TaskBGraphState) -> TaskBGraphState:
        request = state["request"]
        candidates = retrieve_candidates(
            request.user_id,
            request.category,
            state["intent"],
            limit=max(50, request.limit * 5),
            client=client,
            vector_store=vector_store,
        )
        return {**state, "candidates": candidates}

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

    def store_recommendation_run(state: TaskBGraphState) -> TaskBGraphState:
        request = state["request"]
        session = state.get("session")
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
        persist_recommendation_run(
            output,
            {
                **request.context,
                "intent": state["intent"].model_dump(mode="json"),
                "scored_candidates": [candidate.model_dump(mode="json") for candidate in state["scored_candidates"][: request.limit]],
            },
            client,
        )
        return {**state, "output": output}

    graph.add_node("load_or_create_persona", load_or_create_persona)
    graph.add_node("load_session_state", load_session_state)
    graph.add_node("plan_intent", plan_request_intent)
    graph.add_node("retrieve_candidates", retrieve_recommendation_candidates)
    graph.add_node("score_candidates", score_recommendation_candidates)
    graph.add_node("llm_rerank", llm_rerank)
    graph.add_node("update_session_state", update_session_state)
    graph.add_node("store_recommendation_run", store_recommendation_run)

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
