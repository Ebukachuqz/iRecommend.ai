from __future__ import annotations

from typing import Any

from supabase import Client

from src.config import get_settings
from src.db.queries import fetch_persona
from src.db.supabase_client import get_supabase_client
from src.personas.normalizer import normalize_custom_persona
from src.personas.validator import validate_persona
from src.task_b_recommendation.candidate_retriever import retrieve_candidates
from src.task_b_recommendation.cold_start import build_cold_start_persona
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
from src.task_b_recommendation.taste_vector import (
    build_and_store_user_taste_vector,
    fetch_user_taste_vector,
)
from src.task_b_recommendation.vector_store import VectorStore


class TaskBServiceError(RuntimeError):
    pass


def resolve_persona_for_recommendation(
    request: RecommendationRequest,
    client: Client,
) -> tuple[dict[str, Any], bool]:
    if request.persona:
        normalized = normalize_custom_persona(request.persona)
        return validate_persona(normalized, repair=True).model_dump(mode="json"), request.cold_start or request.user_id is None
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


def store_recommendation_run(
    output: RecommendationOutput,
    context: dict[str, Any],
    client: Client,
) -> dict[str, Any]:
    payload = {
        "user_id": output.user_id,
        "category": output.category,
        "request": output.request,
        "context": context,
        "candidate_count": output.candidate_count,
        "recommendations": [item.model_dump(mode="json") for item in output.recommendations],
        "cold_start": output.cold_start,
        "session_id": output.session_id,
        "model_name": output.model_name,
        "prompt_version": output.prompt_version,
    }
    response = client.table("recommendation_runs").insert(payload).execute()
    return response.data[0] if response.data else payload


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
    settings = get_settings()
    client = client or get_supabase_client()
    persona, cold_start = resolve_persona_for_recommendation(request, client)
    session = load_or_create_session(request, persona, client)
    if request.user_id and not cold_start:
        build_or_get_user_taste_vector(request.user_id, request.category, client=client)

    intent = plan_intent(persona, request.request, session)
    candidates = retrieve_candidates(
        request.user_id,
        request.category,
        intent,
        limit=max(50, request.limit * 5),
        client=client,
        vector_store=vector_store,
    )
    scored = score_candidates(candidates, persona, intent)
    reranked = rerank_recommendations(persona, request.request, intent, scored, limit=request.limit)
    session_id = request.session_id
    if session:
        updated_session = update_session_after_recommendation(
            session,
            [recommendation.parent_asin for recommendation in reranked.recommendations],
            request.request,
        )
        store_session(updated_session, client=client)
        session_id = updated_session.session_id

    output = RecommendationOutput(
        user_id=request.user_id,
        category=request.category,
        request=request.request,
        intent=intent,
        recommendations=reranked.recommendations,
        candidate_count=len(scored),
        cold_start=cold_start,
        session_id=session_id,
        model_name=settings.groq_model,
        prompt_version=f"{INTENT_PROMPT_VERSION}+{RERANKER_PROMPT_VERSION}",
    )
    store_recommendation_run(
        output,
        context={
            **request.context,
            "intent": intent.model_dump(mode="json"),
            "scored_candidates": [candidate.model_dump(mode="json") for candidate in scored[: request.limit]],
        },
        client=client,
    )
    return output


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
    persona: dict[str, Any],
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
