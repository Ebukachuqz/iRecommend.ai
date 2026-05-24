from __future__ import annotations

import re
from uuid import uuid4

from supabase import Client

from src.db.supabase_client import get_supabase_client
from src.task_b_recommendation.schema import RecommendationSessionState


def append_unique(values: list, additions: list) -> list:
    output = list(values or [])
    for addition in additions:
        if addition not in output:
            output.append(addition)
    return output


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
    state_payload = row.get("state")
    if isinstance(state_payload, dict):
        return RecommendationSessionState.model_validate(state_payload)
    return RecommendationSessionState.model_validate(
        {
            "session_id": row.get("session_id"),
            "user_id": row.get("user_id"),
            "category": row.get("category"),
            "persona": row.get("persona") or {},
            "conversation_history": row.get("conversation_history") or [],
            "active_constraints": row.get("active_constraints") or {},
            "shown_products": row.get("shown_products") or [],
        }
    )


def store_session(state: RecommendationSessionState, client: Client | None = None) -> None:
    client = client or get_supabase_client()
    client.table("recommendation_sessions").upsert(
        {
            "session_id": state.session_id,
            "user_id": state.user_id,
            "category": state.category,
            "state": state.model_dump(mode="json"),
            "persona": state.persona,
            "conversation_history": state.conversation_history,
            "active_constraints": state.active_constraints,
            "shown_products": state.shown_products,
        },
        on_conflict="session_id",
    ).execute()


def update_session_after_recommendation(
    state: RecommendationSessionState,
    shown_products: list[str],
    user_request: str | None = None,
) -> RecommendationSessionState:
    updated = apply_request_constraints(state, user_request, append_history=True)
    updated.shown_products.extend(parent_asin for parent_asin in shown_products if parent_asin not in updated.shown_products)
    return updated


def asin_like_tokens(text: str) -> list[str]:
    return re.findall(r"\b[A-Z0-9]{6,12}\b", text.upper())


def extract_constraint_updates(message: str | None, shown_products: list[str] | None = None) -> dict:
    text = (message or "").lower()
    shown_products = shown_products or []
    updates: dict = {}
    required: list[str] = []
    excluded: list[str] = []
    excluded_products: list[str] = []
    excluded_brands: list[str] = []

    if any(term in text for term in ("cheaper", "less expensive", "lower price", "budget", "affordable")):
        updates["price_max"] = 25
        required.extend(["affordable", "value for money"])
    if any(term in text for term in ("premium", "higher quality", "high quality", "more expensive")):
        updates["price_min"] = 25
        required.append("premium")
    if "fragrance-free" in text or "fragrance free" in text:
        required.append("fragrance free")
    if "skincare" in text or "skin care" in text:
        updates["category_filter"] = "skincare"
        required.append("skincare")
    if "not haircare" in text or "not hair care" in text or "not hair" in text:
        excluded.extend(["haircare", "hair"])
    if "not skincare" in text or "not skin care" in text:
        excluded.append("skincare")
    if "actually" in text and ("electronics" in text or "electronic" in text):
        updates["category_filter"] = "Electronics"
    if "actually" in text and "book" in text:
        updates["category_filter"] = "Books"

    if "avoid that product" in text or "not that product" in text or "not that" in text:
        if shown_products:
            excluded_products.append(shown_products[-1])
    excluded_products.extend(asin_like_tokens(message or ""))

    brand_match = re.search(r"(?:not|avoid)\s+(?:that\s+)?brand\s+([a-z0-9 &'-]+)", text)
    if brand_match:
        excluded_brands.append(brand_match.group(1).strip())

    if required:
        updates["required_attributes"] = required
    if excluded:
        updates["excluded_attributes"] = excluded
    if excluded_products:
        updates["excluded_products"] = excluded_products
    if excluded_brands:
        updates["excluded_brands"] = excluded_brands
    return updates


def apply_constraint_updates(state: RecommendationSessionState, updates: dict) -> RecommendationSessionState:
    updated = state.model_copy(deep=True)
    constraints = dict(updated.active_constraints or {})
    for key in ("required_attributes", "excluded_attributes", "excluded_products", "excluded_brands"):
        if key in updates:
            constraints[key] = append_unique(list(constraints.get(key) or []), list(updates[key] or []))
    for key in ("price_max", "price_min", "category_filter"):
        if key in updates and updates[key] is not None:
            constraints[key] = updates[key]
    updated.active_constraints = constraints
    return updated


def apply_request_constraints(
    state: RecommendationSessionState,
    user_request: str | None,
    append_history: bool = False,
) -> RecommendationSessionState:
    updated = apply_constraint_updates(state, extract_constraint_updates(user_request, state.shown_products))
    if append_history and user_request:
        updated.conversation_history.append({"role": "user", "content": user_request})
    return updated


def apply_user_feedback(state: RecommendationSessionState, feedback: str) -> RecommendationSessionState:
    return apply_request_constraints(state, feedback, append_history=True)
