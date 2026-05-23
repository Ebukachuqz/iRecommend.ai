from src.task_b_recommendation.reranker import fallback_rerank
from src.task_b_recommendation.schema import (
    RecommendationCandidate,
    RecommendationIntent,
    RecommendationScoreBreakdown,
    ScoredRecommendationCandidate,
)


def test_fallback_reason_mentions_concrete_request_and_product_evidence() -> None:
    candidate = ScoredRecommendationCandidate(
        **RecommendationCandidate(
            parent_asin="skin-1",
            title="Oil-Free Facial Toner for Oily Skin",
            product={
                "title": "Oil-Free Facial Toner for Oily Skin",
                "features": ["gentle toner", "non-comedogenic"],
                "description": "Facial skincare for oily skin.",
            },
            semantic_similarity=0.82,
            retrieval_source="request_query",
        ).model_dump(),
        score_breakdown=RecommendationScoreBreakdown(
            semantic_similarity=0.82,
            preference_match=0.9,
            product_quality=0.88,
            price_fit=0.8,
            popularity_reliability=0.5,
            final_score=0.84,
            matched_persona_signals=["oily skin", "oil-free"],
            warnings=[],
        ),
    )

    output = fallback_rerank(
        [candidate],
        limit=1,
        intent=RecommendationIntent(required_attributes=["oily skin", "oil-free", "skincare"]),
    )

    reason = output.recommendations[0].reason.lower()
    assert "oily skin" in reason
    assert "matching the request" in reason
    assert "ranks well" not in reason
