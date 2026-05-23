from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.api.dependencies import get_db_client
from app.api.models.requests import ColdStartRecommendationAPIRequest, RecommendationAPIRequest
from src.task_b_recommendation import service as recommendation_service
from src.task_b_recommendation.schema import RecommendationOutput, RecommendationRequest


router = APIRouter(tags=["recommendations"])


@router.post("/recommendations/generate", response_model=RecommendationOutput)
def generate_recommendations(
    payload: RecommendationAPIRequest,
    client: Client = Depends(get_db_client),
) -> RecommendationOutput:
    if not payload.user_id and payload.persona is None and not payload.cold_start:
        raise HTTPException(status_code=400, detail="Provide user_id, persona, or cold_start=true.")
    try:
        request = RecommendationRequest(**payload.model_dump())
        return recommendation_service.recommend(request, client=client)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except recommendation_service.TaskBServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Recommendation generation failed.") from exc


@router.post("/recommendations/cold-start", response_model=RecommendationOutput)
def cold_start_recommendations(
    payload: ColdStartRecommendationAPIRequest,
    client: Client = Depends(get_db_client),
) -> RecommendationOutput:
    try:
        request = RecommendationRequest(
            request=payload.request,
            limit=payload.limit,
            cold_start=True,
            context=payload.context,
        )
        return recommendation_service.recommend(request, client=client)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except recommendation_service.TaskBServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Cold-start recommendation failed.") from exc
