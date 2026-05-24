from src.task_b_recommendation.schema import RecommendationCandidate, RecommendationIntent
from src.task_b_recommendation.scoring import normalize_intent_term, score_candidate, score_candidates


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
    intent = RecommendationIntent(required_attributes=["skincare", "oily skin", "oil_free"])
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


def test_underscored_intent_attributes_are_normalized_before_matching() -> None:
    assert normalize_intent_term("suitable_for_dry_skin") == "dry skin"
    assert normalize_intent_term("value_for_money") == "value for money"
    assert normalize_intent_term("non_comedogenic") == "non comedogenic"

    candidate = RecommendationCandidate(
        parent_asin="skin-1",
        title="Cream for Dry Skin",
        semantic_similarity=0.5,
        product={"title": "Cream for Dry Skin", "features": ["hydrating moisturizer"], "price": 9},
    )
    scored = score_candidate(candidate, {}, RecommendationIntent(required_attributes=["suitable_for_dry_skin"]))

    assert "dry skin" in scored.score_breakdown.matched_persona_signals


def test_dry_skin_request_rewards_moisturizer_and_hydrating_products() -> None:
    intent = RecommendationIntent(required_attributes=["dry skin", "skincare"])
    persona = {"purchase_behavior": {"price_sensitivity": "high"}}
    moisturizer = RecommendationCandidate(
        parent_asin="skin-1",
        title="Hydrating Face Moisturizer for Dry Skin",
        semantic_similarity=0.6,
        product={
            "title": "Hydrating Face Moisturizer for Dry Skin",
            "features": ["soft cream", "sensitive skin"],
            "average_rating": 4.4,
            "rating_number": 120,
            "price": 12,
        },
    )
    eye_pads = RecommendationCandidate(
        parent_asin="eye-1",
        title="Anti Aging Under Eye Pads",
        semantic_similarity=0.6,
        product={
            "title": "Anti Aging Under Eye Pads",
            "features": ["eye mask", "hydration"],
            "average_rating": 4.6,
            "rating_number": 160,
            "price": 12,
        },
    )

    scored = score_candidates([eye_pads, moisturizer], persona, intent)

    assert scored[0].parent_asin == "skin-1"
    assert "dry skin" in scored[0].score_breakdown.matched_persona_signals


def test_oily_skin_request_rewards_oil_control_products() -> None:
    intent = RecommendationIntent(required_attributes=["oily skin", "oil_free"])
    cleanser = RecommendationCandidate(
        parent_asin="skin-1",
        title="Oil Control Cleanser for Oily Skin",
        semantic_similarity=0.5,
        product={"title": "Oil Control Cleanser for Oily Skin", "features": ["oil free toner"], "price": 10},
    )
    cream = RecommendationCandidate(
        parent_asin="cream-1",
        title="Rich Night Cream",
        semantic_similarity=0.5,
        product={"title": "Rich Night Cream", "features": ["heavy cream"], "price": 10},
    )

    scored = score_candidates([cream, cleanser], {}, intent)

    assert scored[0].parent_asin == "skin-1"
    assert "oil free" in scored[0].score_breakdown.matched_persona_signals


def test_broad_skincare_request_penalizes_hair_nail_and_travel_products() -> None:
    intent = RecommendationIntent(required_attributes=["skincare"])
    cleanser = RecommendationCandidate(
        parent_asin="skin-1",
        title="Gentle Facial Cleanser",
        semantic_similarity=0.6,
        product={"title": "Gentle Facial Cleanser", "features": ["skincare cleanser"], "price": 12},
    )
    travel_kit = RecommendationCandidate(
        parent_asin="travel-1",
        title="Travel Hair and Nail Brush Kit",
        semantic_similarity=0.6,
        product={"title": "Travel Hair and Nail Brush Kit", "features": ["brush kit"], "price": 12},
    )

    scored = score_candidates([travel_kit, cleanser], {}, intent)

    assert scored[0].parent_asin == "skin-1"
    assert scored[1].score_breakdown.warnings


def test_low_review_products_are_flagged_but_not_excluded() -> None:
    candidate = RecommendationCandidate(
        parent_asin="new-1",
        title="New Gentle Gadget",
        semantic_similarity=0.7,
        product={
            "title": "New Gentle Gadget",
            "features": ["simple reliable design"],
            "average_rating": 0,
            "rating_number": 2,
            "price": 20,
        },
    )

    scored = score_candidates([candidate], {}, RecommendationIntent(required_attributes=["reliable"]))

    assert scored[0].parent_asin == "new-1"
    assert scored[0].score_breakdown.is_discovery_candidate is True
    assert "Discovery candidate: limited review history." in scored[0].score_breakdown.warnings
