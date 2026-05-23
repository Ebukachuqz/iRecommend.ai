from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.dependencies import get_db_client
from app.api.models.responses import ProductSummary, UserPersonaSummary
from src.constants import DEFAULT_CATEGORY
from src.db.queries import fetch_persona, fetch_user_persona_summaries
from src.task_a_simulation.service import list_unseen_products


router = APIRouter(tags=["personas"])


@router.get("/users", response_model=list[UserPersonaSummary])
def list_users(
    category: str = DEFAULT_CATEGORY,
    limit: int = Query(default=20, ge=1, le=100),
    client: Client = Depends(get_db_client),
) -> list[UserPersonaSummary]:
    try:
        return [UserPersonaSummary.model_validate(row) for row in fetch_user_persona_summaries(category, limit, client=client)]
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch persona users.") from exc


@router.get("/users/{user_id}/persona")
def get_user_persona(
    user_id: str,
    category: str = DEFAULT_CATEGORY,
    client: Client = Depends(get_db_client),
) -> dict:
    try:
        row = fetch_persona(user_id, category, client=client)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch persona.") from exc
    if not row:
        raise HTTPException(status_code=404, detail="Persona not found.")
    return {
        "user_id": row.get("user_id"),
        "category": row.get("category"),
        "persona": row.get("persona"),
        "review_count": row.get("review_count"),
        "average_rating": row.get("average_rating"),
        "source_review_ids": row.get("source_review_ids") or [],
        "persona_version": row.get("persona_version"),
        "model_name": row.get("model_name"),
        "prompt_version": row.get("prompt_version"),
    }


@router.get("/users/{user_id}/unseen-products", response_model=list[ProductSummary])
def get_unseen_products(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    client: Client = Depends(get_db_client),
) -> list[ProductSummary]:
    try:
        products = list_unseen_products(user_id, limit=limit, client=client)
        return [ProductSummary.model_validate(product.model_dump(mode="json")) for product in products]
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch unseen products.") from exc


@router.post("/personas/generate-from-history")
def generate_persona_from_history_placeholder() -> dict[str, str]:
    raise HTTPException(
        status_code=501,
        detail="Cross-platform user history modelling is planned as a later feature.",
    )
