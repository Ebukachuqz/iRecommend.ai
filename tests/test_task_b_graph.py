from types import SimpleNamespace

from src.task_b_recommendation import graph as task_b_graph
from src.task_b_recommendation import service as task_b_service
from src.task_b_recommendation.candidate_retriever import CandidateRetrievalResult
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


def patch_graph_pipeline(monkeypatch, session=None):
    calls = {}
    intent = RecommendationIntent(
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
    monkeypatch.setattr(task_b_graph, "resolve_persona_for_recommendation", lambda request, client: (PERSONA, False))
    monkeypatch.setattr(
        task_b_graph,
        "build_or_get_user_taste_vector",
        lambda user_id, category, client=None: {"embedding": [0.1, 0.2], "source_parent_asins": ["liked-1"]},
    )
    monkeypatch.setattr(task_b_graph, "load_or_create_session", lambda request, persona, client: session)
    monkeypatch.setattr(task_b_graph, "plan_intent", lambda persona, request_text, session_state=None: intent)

    def fake_retrieve(user_id, category, planned_intent, **kwargs):
        calls["retrieve"] = {
            "user_id": user_id,
            "category": category,
            "intent": planned_intent,
            "client": kwargs["client"],
            "vector_store": kwargs["vector_store"],
            "persona": kwargs["persona"],
            "taste_vector_row": kwargs["taste_vector_row"],
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
    assert calls["retrieve"]["taste_vector_row"]["embedding"] == [0.1, 0.2]
    assert calls["retrieve"]["limit"] == 50
    context = calls["store"]["context"]
    assert context["retrieval_source_counts"] == {"request_query": 1, "quality_fallback": 1}
    assert len(context["retrieved_candidates"]) == 2
    assert len(context["scored_candidates"]) == 2


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


def test_custom_persona_path_remains_available_through_service(monkeypatch) -> None:
    calls = patch_graph_pipeline(monkeypatch)
    persona_inputs = []

    def fake_resolve(request, client):
        persona_inputs.append(request.persona)
        return PERSONA, True

    monkeypatch.setattr(task_b_graph, "resolve_persona_for_recommendation", fake_resolve)
    monkeypatch.setattr(
        task_b_graph,
        "build_or_get_user_taste_vector",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("custom persona should not build a user taste vector")),
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
