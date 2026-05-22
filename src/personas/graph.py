from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src.personas.generator import PersonaGenerator
from src.personas.validator import persona_to_storage_dict, validate_persona


class PersonaGraphState(TypedDict, total=False):
    user_id: str
    category: str
    reviews: list[dict[str, Any]]
    enriched_reviews: list[dict[str, Any]]
    stats: dict[str, Any]
    review_context: str
    raw_persona: dict[str, Any]
    persona: dict[str, Any]
    stored: bool
    error: str


def build_persona_graph(generator: PersonaGenerator | None = None):
    generator = generator or PersonaGenerator()
    graph = StateGraph(PersonaGraphState)

    def fetch_user_reviews(state: PersonaGraphState) -> PersonaGraphState:
        return {**state, "reviews": generator.fetch_user_reviews(state["user_id"], state["category"])}

    def enrich_with_product_metadata(state: PersonaGraphState) -> PersonaGraphState:
        return {**state, "enriched_reviews": generator.enrich_reviews(state["reviews"])}

    def compute_user_stats(state: PersonaGraphState) -> PersonaGraphState:
        return {**state, "stats": generator.compute_user_stats(state["reviews"])}

    def format_review_context(state: PersonaGraphState) -> PersonaGraphState:
        return {**state, "review_context": generator.format_review_context(state["enriched_reviews"])}

    def generate_persona_llm(state: PersonaGraphState) -> PersonaGraphState:
        raw_persona, stats = generator.generate_persona_payload(state["user_id"], state["category"])
        return {**state, "raw_persona": raw_persona, "stats": stats}

    def validate_or_repair_persona(state: PersonaGraphState) -> PersonaGraphState:
        persona = validate_persona(state["raw_persona"], repair=True)
        return {**state, "persona": persona_to_storage_dict(persona)}

    def store_persona(state: PersonaGraphState) -> PersonaGraphState:
        generator.store_persona(
            state["user_id"],
            state["category"],
            state["persona"],
            state["stats"]["source_review_ids"],
        )
        return {**state, "stored": True}

    graph.add_node("fetch_user_reviews", fetch_user_reviews)
    graph.add_node("enrich_with_product_metadata", enrich_with_product_metadata)
    graph.add_node("compute_user_stats", compute_user_stats)
    graph.add_node("format_review_context", format_review_context)
    graph.add_node("generate_persona_llm", generate_persona_llm)
    graph.add_node("validate_or_repair_persona", validate_or_repair_persona)
    graph.add_node("store_persona", store_persona)

    graph.set_entry_point("fetch_user_reviews")
    graph.add_edge("fetch_user_reviews", "enrich_with_product_metadata")
    graph.add_edge("enrich_with_product_metadata", "compute_user_stats")
    graph.add_edge("compute_user_stats", "format_review_context")
    graph.add_edge("format_review_context", "generate_persona_llm")
    graph.add_edge("generate_persona_llm", "validate_or_repair_persona")
    graph.add_edge("validate_or_repair_persona", "store_persona")
    graph.add_edge("store_persona", END)

    return graph.compile()
