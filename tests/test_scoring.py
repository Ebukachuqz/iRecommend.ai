from src.task_b_recommendation.schema import RecommendationCandidate, RecommendationIntent
from src.task_b_recommendation.scoring import score_candidate


def test_score_is_bounded_between_zero_and_one() -> None:
    candidate = RecommendationCandidate(
        parent_asin="asin-1",
        title="Lightweight lotion",
        semantic_similarity=0.8,
        product={
            "parent_asin": "asin-1",
            "title": "Lightweight lotion",
            "features": ["non greasy"],
            "average_rating": 4.5,
            "rating_number": 120,
            "price": 12,
        },
    )
    persona = {
        "preferences": {"liked_attributes": ["lightweight"], "disliked_attributes": []},
        "purchase_behavior": {"price_sensitivity": "high"},
    }

    scored = score_candidate(candidate, persona, RecommendationIntent(required_attributes=["non greasy"]))

    assert 0 <= scored.score_breakdown.final_score <= 1
    assert "lightweight" in scored.score_breakdown.matched_persona_signals
