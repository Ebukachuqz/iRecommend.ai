from src.task_b_recommendation.schema import RecommendationCandidate, RecommendationIntent
from src.task_b_recommendation.scoring import score_candidate, score_candidates


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


def test_oily_skin_skincare_scores_above_off_type_products() -> None:
    intent = RecommendationIntent(required_attributes=["skincare", "oily skin", "oil-free"])
    persona = {
        "preferences": {"liked_attributes": [], "disliked_attributes": []},
        "purchase_behavior": {"price_sensitivity": "high"},
    }
    oily_skin_toner = RecommendationCandidate(
        parent_asin="skin-1",
        title="Oil-Free Facial Toner for Oily Skin",
        semantic_similarity=0.7,
        product={
            "parent_asin": "skin-1",
            "title": "Oil-Free Facial Toner for Oily Skin",
            "features": ["gentle facial toner", "non-comedogenic", "for oily skin"],
            "average_rating": 4.4,
            "rating_number": 120,
            "price": 11,
        },
    )
    shampoo = RecommendationCandidate(
        parent_asin="hair-1",
        title="Hydrating Shampoo for Dry Hair",
        semantic_similarity=0.7,
        product={
            "parent_asin": "hair-1",
            "title": "Hydrating Shampoo for Dry Hair",
            "features": ["hair care shampoo"],
            "average_rating": 4.8,
            "rating_number": 400,
            "price": 10,
        },
    )

    scored = score_candidates([shampoo, oily_skin_toner], persona, intent)

    assert scored[0].parent_asin == "skin-1"
    assert scored[0].score_breakdown.final_score > scored[1].score_breakdown.final_score
    assert scored[1].score_breakdown.warnings
