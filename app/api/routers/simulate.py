from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.dependencies import get_db_client
from app.api.models.requests import ReviewSimulationAPIRequest
from src.task_a_simulation import service as task_a_service
from src.task_a_simulation.schema import ReviewSimulationOutput, ReviewSimulationRequest


router = APIRouter(tags=["review simulation"])


def map_task_a_error(message: str) -> int:
    lowered = message.lower()
    if "required" in lowered or "custom persona" in lowered or "custom product" in lowered or "task a requires" in lowered:
        return 400
    if "no persona" in lowered or "no product" in lowered or "no task_a_holdout" in lowered:
        return 404
    return 500


@router.post("/reviews/simulate", response_model=ReviewSimulationOutput)
def simulate_review(
    payload: ReviewSimulationAPIRequest,
) -> ReviewSimulationOutput:
    has_custom_input = payload.persona is not None or payload.product is not None
    if has_custom_input and (payload.persona is None or payload.product is None):
        raise HTTPException(status_code=400, detail="Custom Task A simulation requires both persona and product.")
    if not has_custom_input and not payload.user_id:
        raise HTTPException(
            status_code=400,
            detail="Task A requires either user_id with parent_asin/use_holdout or custom persona and product.",
        )
    try:
        request = ReviewSimulationRequest(**payload.model_dump())
        client = None if has_custom_input else get_db_client()
        return task_a_service.simulate_review(request, client=client)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except task_a_service.TaskAServiceError as exc:
        raise HTTPException(status_code=map_task_a_error(str(exc)), detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Review simulation failed.") from exc
