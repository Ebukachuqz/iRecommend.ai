from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.api.dependencies import get_db_client
from app.api.models.requests import ReviewSimulationAPIRequest
from src.task_a_simulation import service as task_a_service
from src.task_a_simulation.schema import ReviewSimulationOutput, ReviewSimulationRequest


router = APIRouter(tags=["review simulation"])


def map_task_a_error(message: str) -> int:
    lowered = message.lower()
    if "required" in lowered:
        return 400
    if "no persona" in lowered or "no product" in lowered or "no task_a_holdout" in lowered:
        return 404
    return 500


@router.post("/reviews/simulate", response_model=ReviewSimulationOutput)
def simulate_review(
    payload: ReviewSimulationAPIRequest,
    client: Client = Depends(get_db_client),
) -> ReviewSimulationOutput:
    try:
        request = ReviewSimulationRequest(**payload.model_dump())
        return task_a_service.simulate_review(request, client=client)
    except task_a_service.TaskAServiceError as exc:
        raise HTTPException(status_code=map_task_a_error(str(exc)), detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Review simulation failed.") from exc
