from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.db import queries
from src.db.supabase_client import get_supabase_client
from src.task_a_simulation.calibration import calibrate_rating
from src.task_a_simulation.rating_predictor import predict_statistical_rating
from src.task_a_simulation.schema import ProductSnapshot, ReviewSimulationOutput, ReviewSimulationRequest
from src.task_a_simulation.service import (
    build_simulation_payload,
    resolve_persona,
    resolve_product,
)
from src.task_a_simulation.simulator import generate_llm_review_and_rating
from src.task_a_simulation.prompts import TASK_A_PROMPT_VERSION
from src.config import get_settings


class TaskAGraphState(TypedDict, total=False):
    request: ReviewSimulationRequest
    persona: dict[str, Any]
    persona_version: str | None
    product: ProductSnapshot
    holdout_review: dict[str, Any] | None
    statistical_prediction: Any
    llm_output: Any
    rating_breakdown: Any
    output: ReviewSimulationOutput
    stored_result: dict[str, Any]


def build_task_a_graph(client=None):
    client = client or get_supabase_client()
    settings = get_settings()
    graph = StateGraph(TaskAGraphState)

    def fetch_persona_and_product(state: TaskAGraphState) -> TaskAGraphState:
        request = state["request"]
        holdout_review = None
        parent_asin = request.parent_asin
        if request.use_holdout:
            holdout_review = queries.fetch_task_a_holdout_review(request.user_id, client=client)
            if not holdout_review:
                raise ValueError(f"No task_a_holdout review found for user_id={request.user_id!r}.")
            parent_asin = holdout_review["parent_asin"]
        if not parent_asin:
            raise ValueError("parent_asin is required when use_holdout is false.")
        persona, persona_version = resolve_persona(request.user_id, request.category, request.persona, client)
        product = resolve_product(parent_asin, request.product, client)
        return {
            **state,
            "persona": persona,
            "persona_version": persona_version,
            "product": product,
            "holdout_review": holdout_review,
        }

    def statistical_rating_prediction(state: TaskAGraphState) -> TaskAGraphState:
        prediction = predict_statistical_rating(state["persona"], state["product"])
        return {**state, "statistical_prediction": prediction}

    def llm_review_and_rating_generation(state: TaskAGraphState) -> TaskAGraphState:
        request = state["request"]
        output = generate_llm_review_and_rating(
            state["persona"],
            state["product"],
            state["statistical_prediction"],
            nigerian_mode=request.nigerian_mode,
            context=request.context,
        )
        return {**state, "llm_output": output}

    def rating_calibration(state: TaskAGraphState) -> TaskAGraphState:
        breakdown = calibrate_rating(
            state["persona"],
            state["statistical_prediction"],
            state["llm_output"].llm_predicted_rating,
        )
        return {**state, "rating_breakdown": breakdown}

    def output_validation(state: TaskAGraphState) -> TaskAGraphState:
        request = state["request"]
        product = state["product"]
        llm_output = state["llm_output"]
        rating_breakdown = state["rating_breakdown"]
        output = ReviewSimulationOutput(
            user_id=request.user_id,
            category=request.category,
            parent_asin=product.parent_asin,
            product_title=product.title,
            llm_predicted_rating=llm_output.llm_predicted_rating,
            statistical_predicted_rating=rating_breakdown.statistical_predicted_rating,
            final_predicted_rating=rating_breakdown.final_predicted_rating
            or rating_breakdown.statistical_predicted_rating,
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
        return {**state, "output": output}

    def store_simulation_result(state: TaskAGraphState) -> TaskAGraphState:
        payload = build_simulation_payload(
            state["request"],
            state["persona"],
            state["product"],
            state["output"],
            state.get("persona_version"),
            state.get("holdout_review"),
        )
        stored = queries.store_simulation_result(payload, client=client)
        return {**state, "stored_result": stored}

    graph.add_node("fetch_persona_and_product", fetch_persona_and_product)
    graph.add_node("statistical_rating_prediction", statistical_rating_prediction)
    graph.add_node("llm_review_and_rating_generation", llm_review_and_rating_generation)
    graph.add_node("rating_calibration", rating_calibration)
    graph.add_node("output_validation", output_validation)
    graph.add_node("store_simulation_result", store_simulation_result)

    graph.set_entry_point("fetch_persona_and_product")
    graph.add_edge("fetch_persona_and_product", "statistical_rating_prediction")
    graph.add_edge("statistical_rating_prediction", "llm_review_and_rating_generation")
    graph.add_edge("llm_review_and_rating_generation", "rating_calibration")
    graph.add_edge("rating_calibration", "output_validation")
    graph.add_edge("output_validation", "store_simulation_result")
    graph.add_edge("store_simulation_result", END)

    return graph.compile()
