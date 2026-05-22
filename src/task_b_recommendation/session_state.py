from __future__ import annotations

from uuid import uuid4

from supabase import Client

from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.schema import RecommendationSessionState


def create_session(
    user_id: str | None = None,
    category: str = "All_Beauty",
    persona: dict | None = None,
    session_id: str | None = None,
) -> RecommendationSessionState:
    return RecommendationSessionState(
        session_id=session_id or str(uuid4()),
        user_id=user_id,
        category=category,
        persona=persona or {},
    )


def load_session(session_id: str, client: Client | None = None) -> RecommendationSessionState | None:
    client = client or get_supabase_client()
    response = (
        client.table("recommendation_sessions")
        .select("*")
        .eq("session_id", session_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    row = response.data[0]
    return RecommendationSessionState.model_validate(row["state"])


def store_session(state: RecommendationSessionState, client: Client | None = None) -> None:
    client = client or get_supabase_client()
    client.table("recommendation_sessions").upsert(
        {
            "session_id": state.session_id,
            "user_id": state.user_id,
            "category": state.category,
            "state": state.model_dump(mode="json"),
        },
        on_conflict="session_id",
    ).execute()


def update_session_after_recommendation(
    state: RecommendationSessionState,
    shown_products: list[str],
    user_request: str | None = None,
) -> RecommendationSessionState:
    updated = state.model_copy(deep=True)
    if user_request:
        updated.conversation_history.append({"role": "user", "content": user_request})
    updated.shown_products.extend(parent_asin for parent_asin in shown_products if parent_asin not in updated.shown_products)
    return updated


def apply_user_feedback(state: RecommendationSessionState, feedback: str) -> RecommendationSessionState:
    updated = state.model_copy(deep=True)
    updated.conversation_history.append({"role": "user", "content": feedback})
    lower = feedback.lower()
    if "cheaper" in lower:
        updated.active_constraints["price_max"] = updated.active_constraints.get("price_max") or 25
    if "not that" in lower:
        updated.active_constraints.setdefault("excluded_products", [])
    return updated
