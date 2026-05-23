from __future__ import annotations

from typing import Any

from supabase import Client

from src.config import get_settings
from src.db import queries
from src.db.supabase_client import get_supabase_client
from src.personas.custom_persona_processor import process_custom_persona
from src.personas.validator import validate_persona
from src.task_a_simulation.calibration import calibrate_rating
from src.task_a_simulation.custom_product_processor import process_custom_product
from src.task_a_simulation.prompts import TASK_A_PROMPT_VERSION
from src.task_a_simulation.rating_predictor import predict_statistical_rating
from src.task_a_simulation.schema import (
    ProductSnapshot,
    ReviewSimulationOutput,
    ReviewSimulationRequest,
)
from src.task_a_simulation.simulator import generate_llm_review_and_rating


class TaskAServiceError(RuntimeError):
    pass


def coerce_product(product: dict[str, Any] | ProductSnapshot) -> ProductSnapshot:
    return product if isinstance(product, ProductSnapshot) else ProductSnapshot.model_validate(product)


def is_custom_simulation_request(request: ReviewSimulationRequest) -> bool:
    return request.persona is not None and request.product is not None


def resolve_persona(
    user_id: str | None,
    category: str,
    persona: dict[str, Any] | str | None,
    client: Client | None,
) -> tuple[dict[str, Any], str | None]:
    if persona is not None:
        return process_custom_persona(persona), None

    if not user_id:
        raise TaskAServiceError("Task A requires either user_id with parent_asin/use_holdout or custom persona and product.")
    row = queries.fetch_persona(user_id, category, client=client)
    if not row:
        raise TaskAServiceError(f"No persona found for user_id={user_id!r}, category={category!r}.")
    payload = row.get("persona") or {}
    validated = validate_persona(payload, repair=True)
    return validated.model_dump(mode="json"), row.get("persona_version")


def resolve_product(parent_asin: str, product: dict[str, Any] | str | ProductSnapshot | None, client: Client | None) -> ProductSnapshot:
    if product is not None:
        if isinstance(product, ProductSnapshot):
            normalized = product.model_dump(mode="json")
        else:
            normalized = process_custom_product(product)
        if parent_asin and normalized.get("parent_asin") == "custom_product":
            normalized["parent_asin"] = parent_asin
        return ProductSnapshot.model_validate(normalized)

    row = queries.fetch_product(parent_asin, client=client)
    if not row:
        raise TaskAServiceError(f"No product found for parent_asin={parent_asin!r}.")
    return ProductSnapshot.model_validate(row)


def build_simulation_payload(
    request: ReviewSimulationRequest,
    persona: dict[str, Any],
    product: ProductSnapshot,
    output: ReviewSimulationOutput,
    persona_version: str | None,
    holdout_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "user_id": output.user_id,
        "category": output.category,
        "parent_asin": output.parent_asin,
        "holdout_review_id": holdout_review.get("review_id") if holdout_review else None,
        "real_review_text": holdout_review.get("text") if holdout_review else None,
        "real_rating": holdout_review.get("rating") if holdout_review else None,
        "product_snapshot": product.model_dump(mode="json"),
        "input_persona": persona,
        "llm_predicted_rating": output.llm_predicted_rating,
        "statistical_predicted_rating": output.statistical_predicted_rating,
        "final_predicted_rating": output.final_predicted_rating,
        "simulated_review_title": output.simulated_review_title,
        "simulated_review_text": output.simulated_review_text,
        "confidence": output.confidence,
        "reasoning_summary": output.reasoning_summary,
        "evidence_used": output.evidence_used,
        "rating_breakdown": output.rating_breakdown.model_dump(mode="json"),
        "nigerian_mode": request.nigerian_mode,
        "model_name": output.model_name,
        "prompt_version": output.prompt_version,
        "persona_version": persona_version,
    }


def simulate_review(request: ReviewSimulationRequest, client: Client | None = None) -> ReviewSimulationOutput:
    settings = get_settings()
    custom_mode = is_custom_simulation_request(request)
    client = None if custom_mode else (client or get_supabase_client())
    holdout_review = None

    if custom_mode:
        parent_asin = request.parent_asin or "custom_product"
    elif request.use_holdout:
        if not request.user_id:
            raise TaskAServiceError("user_id is required when use_holdout is true.")
        holdout_review = queries.fetch_task_a_holdout_review(request.user_id, client=client)
        if not holdout_review:
            raise TaskAServiceError(f"No task_a_holdout review found for user_id={request.user_id!r}.")
        parent_asin = holdout_review["parent_asin"]
    else:
        if not request.parent_asin:
            raise TaskAServiceError("Task A requires either user_id with parent_asin/use_holdout or custom persona and product.")
        if not request.user_id:
            raise TaskAServiceError("Task A requires either user_id with parent_asin/use_holdout or custom persona and product.")
        parent_asin = request.parent_asin

    persona, persona_version = resolve_persona(request.user_id, request.category, request.persona, client)
    product = resolve_product(parent_asin, request.product, client)
    statistical_prediction = predict_statistical_rating(persona, product)
    llm_output = generate_llm_review_and_rating(
        persona,
        product,
        statistical_prediction,
        nigerian_mode=request.nigerian_mode,
        context=request.context,
    )
    rating_breakdown = calibrate_rating(
        persona,
        statistical_prediction,
        llm_output.llm_predicted_rating,
    )
    output = ReviewSimulationOutput(
        user_id=request.user_id,
        category=request.category,
        parent_asin=product.parent_asin,
        product_title=product.title,
        llm_predicted_rating=llm_output.llm_predicted_rating,
        statistical_predicted_rating=rating_breakdown.statistical_predicted_rating,
        final_predicted_rating=rating_breakdown.final_predicted_rating or rating_breakdown.statistical_predicted_rating,
        simulated_review_title=llm_output.simulated_review_title,
        simulated_review_text=llm_output.simulated_review_text,
        confidence=llm_output.confidence,
        reasoning_summary=llm_output.reasoning_summary,
        evidence_used=llm_output.evidence_used,
        rating_breakdown=rating_breakdown,
        nigerian_mode=request.nigerian_mode,
        model_name=settings.groq_model,
        prompt_version=TASK_A_PROMPT_VERSION,
    )
    if not custom_mode and client is not None:
        queries.store_simulation_result(
            build_simulation_payload(request, persona, product, output, persona_version, holdout_review),
            client=client,
        )
    return output


def simulate_review_for_product(
    user_id: str,
    parent_asin: str,
    category: str = "All_Beauty",
    nigerian_mode: bool = False,
    client: Client | None = None,
) -> ReviewSimulationOutput:
    request = ReviewSimulationRequest(
        user_id=user_id,
        category=category,
        parent_asin=parent_asin,
        nigerian_mode=nigerian_mode,
    )
    return simulate_review(request, client=client)


def simulate_review_for_holdout(
    user_id: str,
    category: str = "All_Beauty",
    nigerian_mode: bool = False,
    client: Client | None = None,
) -> ReviewSimulationOutput:
    request = ReviewSimulationRequest(
        user_id=user_id,
        category=category,
        use_holdout=True,
        nigerian_mode=nigerian_mode,
    )
    return simulate_review(request, client=client)


def list_unseen_products(user_id: str, limit: int = 20, client: Client | None = None) -> list[ProductSnapshot]:
    rows = queries.fetch_unseen_products(user_id, limit=limit, client=client)
    return [ProductSnapshot.model_validate(row) for row in rows]
