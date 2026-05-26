from types import SimpleNamespace

from src.task_b_recommendation import graph as task_b_graph
from src.task_b_recommendation import service as task_b_service
from src.task_b_recommendation.candidate_retriever import CandidateRetrievalResult
from src.task_b_recommendation.cold_start import (
    build_cold_start_persona,
    build_cross_domain_retrieval_query,
    categories_are_meaningfully_different,
)
from src.task_b_recommendation.schema import (
    RecommendationCandidate,
    RecommendationIntent,
    RecommendationRequest,
    RecommendationScoreBreakdown,
    RecommendationSessionState,
    RerankedRecommendation,
    RerankerOutput,
    ScoredRecommendationCandidate,
)


class DummyClient:
    pass


class DummyVectorStore:
    pass


PERSONA = {
    "preferences": {"liked_attributes": ["gentle"], "disliked_attributes": ["strong fragrance"]},
    "rating_behavior": {"average_rating": 4.1},
}


def make_candidate(parent_asin: str, source: str = "request_query") -> RecommendationCandidate:
    return RecommendationCandidate(
        parent_asin=parent_asin,
        title=f"Product {parent_asin}",
        product={"parent_asin": parent_asin, "title": f"Product {parent_asin}"},
        semantic_similarity=0.8,
        retrieval_source=source,
        retrieval_sources=[source],
    )


def make_scored(parent_asin: str, score: float) -> ScoredRecommendationCandidate:
    return ScoredRecommendationCandidate(
        parent_asin=parent_asin,
        title=f"Product {parent_asin}",
        product={"parent_asin": parent_asin, "title": f"Product {parent_asin}"},
        semantic_similarity=0.8,
        retrieval_source="request_query",
        retrieval_sources=["request_query"],
        score_breakdown=RecommendationScoreBreakdown(
            semantic_similarity=0.8,
            preference_match=0.7,
            product_quality=0.9,
            price_fit=0.6,
            popularity_reliability=0.5,
            final_score=score,
            matched_persona_signals=["gentle"],
        ),
    )


def patch_graph_pipeline(monkeypatch, session=None, intent=None, persona=PERSONA, cold_start=False):
    calls = {}
    intent = intent or RecommendationIntent(
        interpreted_need="gentle skincare",
        retrieval_query="gentle skincare",
        required_attributes=["gentle"],
    )
    candidates = [make_candidate("asin-1"), make_candidate("asin-2", "quality_fallback")]
    scored = [make_scored("asin-1", 0.91), make_scored("asin-2", 0.72)]
    reranked = RerankerOutput(
        recommendations=[
            RerankedRecommendation(
                parent_asin="asin-1",
                rank=1,
                title="Product asin-1",
                reason="Matches gentle skincare.",
                score_breakdown={"final_score": 0.91},
            )
        ]
    )

    monkeypatch.setattr(task_b_graph, "get_settings", lambda: SimpleNamespace(groq_model="test-model"))
    monkeypatch.setattr(task_b_graph, "resolve_persona_for_recommendation", lambda request, client: (persona, cold_start))
    monkeypatch.setattr(
        task_b_graph,
        "build_or_get_user_preference_vector",
        lambda user_id, category, client=None: {"embedding": [0.1, 0.2], "source_parent_asins": ["liked-1"]},
    )
    monkeypatch.setattr(task_b_graph, "load_or_create_session", lambda request, persona, client: session)
    monkeypatch.setattr(task_b_graph, "plan_intent", lambda persona, request_text, session_state=None: intent)
    monkeypatch.setattr(
        task_b_graph,
        "reviewed_parent_asins_for_request",
        lambda request, client: {"reviewed-1"} if request.user_id else set(),
    )

    def fake_retrieve(user_id, category, planned_intent, **kwargs):
        calls["retrieve"] = {
            "user_id": user_id,
            "category": category,
            "intent": planned_intent,
            "client": kwargs["client"],
            "vector_store": kwargs["vector_store"],
            "persona": kwargs["persona"],
            "preference_vector_row": kwargs["preference_vector_row"],
            "exclude_parent_asins": kwargs["exclude_parent_asins"],
            "reviewed_parent_asins": kwargs["reviewed_parent_asins"],
            "limit": kwargs["limit"],
        }
        return CandidateRetrievalResult(candidates=candidates, source_counts={"request_query": 1, "quality_fallback": 1})

    monkeypatch.setattr(task_b_graph, "retrieve_candidates_with_sources", fake_retrieve)
    monkeypatch.setattr(task_b_graph, "score_candidates", lambda retrieved, persona, planned_intent: scored)
    monkeypatch.setattr(task_b_graph, "rerank_recommendations", lambda *args, **kwargs: reranked)

    def fake_store(output, context, client):
        calls["store"] = {"output": output, "context": context, "client": client}
        return {"id": "run-1"}

    monkeypatch.setattr(task_b_graph, "store_recommendation_run", fake_store)
    return calls


def test_service_recommend_returns_graph_output_and_keeps_full_trace_context(monkeypatch) -> None:
    client = DummyClient()
    vector_store = DummyVectorStore()
    calls = patch_graph_pipeline(monkeypatch)

    output = task_b_service.recommend(
        RecommendationRequest(user_id="user-1", request="gentle skincare", limit=1),
        client=client,
        vector_store=vector_store,
    )

    assert output.user_id == "user-1"
    assert output.recommendations[0].parent_asin == "asin-1"
    assert output.model_name == "test-model"
    assert calls["retrieve"]["client"] is client
    assert calls["retrieve"]["vector_store"] is vector_store
    assert calls["retrieve"]["persona"] == PERSONA
    assert calls["retrieve"]["preference_vector_row"]["embedding"] == [0.1, 0.2]
    assert calls["retrieve"]["limit"] == 50
    context = calls["store"]["context"]
    assert context["retrieval_source_counts"] == {"request_query": 1, "quality_fallback": 1}
    assert len(context["retrieved_candidates"]) == 2
    assert len(context["scored_candidates"]) == 2


def test_graph_uses_requested_category_for_retrieval_and_storage(monkeypatch) -> None:
    client = DummyClient()
    calls = patch_graph_pipeline(monkeypatch)

    output = task_b_service.recommend(
        RecommendationRequest(user_id="user-1", category="Electronics", request="portable charger", limit=1),
        client=client,
        vector_store=DummyVectorStore(),
    )

    assert output.category == "Electronics"
    assert calls["retrieve"]["category"] == "Electronics"
    assert calls["store"]["output"].category == "Electronics"
    assert calls["store"]["context"]["resolved_category"] == "Electronics"


def test_graph_default_category_still_uses_all_beauty(monkeypatch) -> None:
    calls = patch_graph_pipeline(monkeypatch)

    output = task_b_service.recommend(
        RecommendationRequest(user_id="user-1", request="gentle skincare", limit=1),
        client=DummyClient(),
        vector_store=DummyVectorStore(),
    )

    assert output.category == "All_Beauty"
    assert calls["retrieve"]["category"] == "All_Beauty"
    assert calls["store"]["context"]["resolved_category"] == "All_Beauty"


def test_graph_updates_and_stores_session_state(monkeypatch) -> None:
    session = RecommendationSessionState(
        session_id="session-1",
        user_id="user-1",
        category="All_Beauty",
        persona=PERSONA,
    )
    calls = patch_graph_pipeline(monkeypatch, session=session)
    stored_sessions = []

    def fake_update(existing_session, shown_products, user_request):
        updated = existing_session.model_copy(deep=True)
        updated.shown_products.extend(shown_products)
        updated.conversation_history.append({"role": "user", "content": user_request})
        return updated

    monkeypatch.setattr(task_b_graph, "update_session_after_recommendation", fake_update)
    monkeypatch.setattr(task_b_graph, "store_session", lambda updated, client=None: stored_sessions.append(updated))

    output = task_b_service.recommend(
        RecommendationRequest(user_id="user-1", request="gentle skincare", session_id="session-1", limit=1),
        client=DummyClient(),
        vector_store=DummyVectorStore(),
    )

    assert output.session_id == "session-1"
    assert stored_sessions[0].shown_products == ["asin-1"]
    assert stored_sessions[0].conversation_history[-1]["content"] == "gentle skincare"
    assert calls["store"]["output"].session_id == "session-1"
    assert "asin-1" in stored_sessions[0].shown_products


def test_custom_persona_path_remains_available_through_service(monkeypatch) -> None:
    calls = patch_graph_pipeline(monkeypatch)
    persona_inputs = []

    def fake_resolve(request, client):
        persona_inputs.append(request.persona)
        return PERSONA, True

    monkeypatch.setattr(task_b_graph, "resolve_persona_for_recommendation", fake_resolve)
    monkeypatch.setattr(
        task_b_graph,
        "build_or_get_user_preference_vector",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("custom persona should not build a user preference vector")),
    )

    output = task_b_service.recommend(
        RecommendationRequest(persona={"likes": ["gentle skincare"]}, request="gentle moisturizer", limit=1),
        client=DummyClient(),
        vector_store=DummyVectorStore(),
    )

    assert output.user_id is None
    assert output.cold_start is True
    assert persona_inputs == [{"likes": ["gentle skincare"]}]
    assert calls["store"]["output"].cold_start is True


def test_cold_start_persona_uses_request_signals_and_low_confidence_metadata() -> None:
    persona = build_cold_start_persona("I need affordable reliable electronics")

    assert persona["persona_confidence"] == "low"
    assert persona["persona_source"] == "request_context"
    assert persona["purchase_behavior"]["price_sensitivity"] == "high"
    assert "value for money" in persona["preferences"]["what_they_value"]
    assert "electronics" in persona["purchase_behavior"]["preferred_categories"]


def test_cold_start_persona_uses_onboarding_answers_when_available() -> None:
    persona = build_cold_start_persona(
        "I need something for daily use",
        {
            "interests": ["electronics"],
            "priorities": ["affordable", "durable"],
            "dislikes": ["flimsy build"],
            "rating_strictness": "strict",
            "loved_product_examples": ["A reliable power bank"],
            "disliked_product_examples": ["A cheap charger that broke"],
        },
    )

    assert persona["persona_confidence"] == "low"
    assert persona["persona_source"] == "onboarding"
    assert "electronics" in persona["preferences"]["liked_product_types"]
    assert "value for money" in persona["preferences"]["what_they_value"]
    assert "durable" in persona["preferences"]["what_they_value"]
    assert "flimsy build" in persona["preferences"]["disliked_attributes"]
    assert persona["rating_behavior"]["strictness"] == "strict"
    assert persona["purchase_behavior"]["price_sensitivity"] == "high"
    assert persona["purchase_behavior"]["quality_sensitivity"] == "high"
    assert persona["evidence"]["positive_examples"] == ["A reliable power bank"]
    assert persona["evidence"]["negative_examples"] == ["A cheap charger that broke"]


def test_cold_start_graph_does_not_fetch_or_build_preference_vector(monkeypatch) -> None:
    calls = patch_graph_pipeline(monkeypatch, persona=build_cold_start_persona("affordable skincare"), cold_start=True)
    monkeypatch.setattr(
        task_b_graph,
        "build_or_get_user_preference_vector",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cold-start should not fetch preference vector")),
    )

    output = task_b_service.recommend(
        RecommendationRequest(request="affordable skincare", cold_start=True, limit=1),
        client=DummyClient(),
        vector_store=DummyVectorStore(),
    )

    assert output.cold_start is True
    assert calls["retrieve"]["preference_vector_row"] is None
    assert calls["store"]["context"]["cold_start_metadata"]["persona_confidence"] == "low"


def test_cold_start_graph_passes_onboarding_answers_to_starter_persona(monkeypatch) -> None:
    captured = {}
    original_resolve = task_b_graph.resolve_persona_for_recommendation
    calls = patch_graph_pipeline(monkeypatch, persona=build_cold_start_persona("affordable skincare"), cold_start=True)

    def fake_build_cold_start_persona(request_text, onboarding_answers=None):
        captured["request_text"] = request_text
        captured["onboarding_answers"] = onboarding_answers
        return build_cold_start_persona(request_text, onboarding_answers)

    monkeypatch.setattr(task_b_graph, "build_cold_start_persona", fake_build_cold_start_persona)
    monkeypatch.setattr(task_b_graph, "resolve_persona_for_recommendation", original_resolve)
    monkeypatch.setattr(
        task_b_graph,
        "build_or_get_user_preference_vector",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cold-start should not fetch preference vector")),
    )

    output = task_b_service.recommend(
        RecommendationRequest(
            request="affordable skincare",
            cold_start=True,
            onboarding_answers={"priorities": ["affordable"], "rating_strictness": "strict"},
            limit=1,
        ),
        client=DummyClient(),
        vector_store=DummyVectorStore(),
    )

    assert output.cold_start is True
    assert captured["onboarding_answers"] == {"priorities": ["affordable"], "rating_strictness": "strict"}
    assert calls["store"]["context"]["cold_start_metadata"]["has_onboarding_answers"] is True


def test_cold_start_accepts_onboarding_answers_from_context() -> None:
    persona, cold_start = task_b_graph.resolve_persona_for_recommendation(
        RecommendationRequest(
            request="daily use",
            cold_start=True,
            context={"onboarding_answers": {"interests": ["books"], "rating_strictness": "generous"}},
        ),
        DummyClient(),
    )

    assert cold_start is True
    assert persona["persona_source"] == "onboarding"
    assert persona["rating_behavior"]["strictness"] == "generous"
    assert "books" in persona["preferences"]["liked_product_types"]


def test_cross_domain_detection_is_conservative() -> None:
    assert categories_are_meaningfully_different("All_Beauty", "Electronics") is True
    assert categories_are_meaningfully_different("All_Beauty", "Books") is True
    assert categories_are_meaningfully_different("Beauty_and_Personal_Care", "Electronics") is True
    assert categories_are_meaningfully_different("All_Beauty", "Beauty_and_Personal_Care") is False
    assert categories_are_meaningfully_different("Skincare", "Beauty") is False


def test_cross_domain_query_uses_transferable_values_not_source_product_terms() -> None:
    persona = {
        "preferences": {
            "liked_attributes": ["fragrance free"],
            "liked_product_types": ["moisturizer"],
            "what_they_value": ["value for money", "durability"],
            "common_complaints": ["overhyped products", "strong fragrance"],
        },
        "purchase_behavior": {"price_sensitivity": "high", "quality_sensitivity": "high"},
        "rating_behavior": {"strictness": "strict"},
    }

    query = build_cross_domain_retrieval_query(persona, "Electronics", "something for daily use")

    assert "Electronics" in query
    assert "value for money" in query
    assert "durability" in query
    assert "fragrance" not in query
    assert "moisturizer" not in query


def test_graph_applies_cross_domain_metadata_and_excludes_shown_products(monkeypatch) -> None:
    session = RecommendationSessionState(
        session_id="session-1",
        user_id="user-1",
        category="All_Beauty",
        persona=PERSONA,
        shown_products=["shown-1"],
    )
    persona = {
        **PERSONA,
        "purchase_behavior": {"price_sensitivity": "high", "quality_sensitivity": "high"},
        "preferences": {
            "liked_attributes": ["fragrance free"],
            "liked_product_types": ["moisturizer"],
            "what_they_value": ["value for money"],
            "common_complaints": ["overhyped products"],
        },
    }
    intent = RecommendationIntent(
        interpreted_need="electronics",
        retrieval_query="electronics",
        category_filter="Electronics",
        required_attributes=["electronics"],
    )
    calls = patch_graph_pipeline(monkeypatch, session=session, intent=intent, persona=persona)
    monkeypatch.setattr(task_b_graph, "store_session", lambda *args, **kwargs: None)

    output = task_b_service.recommend(
        RecommendationRequest(user_id="user-1", category="All_Beauty", request="I need electronics", session_id="session-1", limit=1),
        client=DummyClient(),
        vector_store=DummyVectorStore(),
    )

    context = calls["store"]["context"]
    assert output.recommendations[0].parent_asin == "asin-1"
    assert context["cross_domain"]["cross_domain"] is True
    assert context["cross_domain"]["target_category"] == "Electronics"
    assert "shown-1" in context["excluded_parent_asins"]
    assert "shown-1" in calls["retrieve"]["exclude_parent_asins"]
    assert "fragrance free" not in calls["retrieve"]["persona"]["preferences"]["liked_attributes"]
