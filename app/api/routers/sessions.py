from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.api.dependencies import get_db_client
from app.api.models.requests import SessionMessageRequest
from src.task_b_recommendation import service as recommendation_service
from src.task_b_recommendation.schema import RecommendationOutput, RecommendationRequest


router = APIRouter(tags=["sessions"])


@router.post("/sessions/{session_id}/message", response_model=RecommendationOutput)
def session_message(
    session_id: str,
    payload: SessionMessageRequest,
    client: Client = Depends(get_db_client),
) -> RecommendationOutput:
    try:
        request = RecommendationRequest(
            user_id=payload.user_id,
            category=payload.category,
            request=payload.message,
            limit=payload.limit,
            session_id=session_id,
            cold_start=payload.user_id is None,
        )
        return recommendation_service.recommend(request, client=client)
    except recommendation_service.TaskBServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Session recommendation failed.") from exc
