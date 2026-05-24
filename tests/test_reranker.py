from src.task_b_recommendation.reranker import fallback_rerank, normalize_product_title
from src.task_b_recommendation.schema import (
    RecommendationCandidate,
    RecommendationIntent,
    RecommendationScoreBreakdown,
    ScoredRecommendationCandidate,
)


def make_scored_candidate(
    parent_asin: str,
    title: str,
    features: list[str] | None = None,
    description: str | None = None,
    matched_signals: list[str] | None = None,
    final_score: float = 0.84,
) -> ScoredRecommendationCandidate:
    return ScoredRecommendationCandidate(
        **RecommendationCandidate(
            parent_asin=parent_asin,
            title=title,
            product={
                "title": title,
                "features": features or [],
                "description": description,
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
            final_score=final_score,
            matched_persona_signals=matched_signals or [],
            warnings=[],
        ),
    )


def test_fallback_reason_mentions_concrete_request_and_product_evidence() -> None:
    candidate = make_scored_candidate(
        "skin-1",
        "Oil-Free Facial Toner for Oily Skin",
        features=["gentle toner", "non-comedogenic"],
        description="Facial skincare for oily skin.",
        matched_signals=["oily skin", "oil-free"],
    )

    output = fallback_rerank(
        [candidate],
        limit=1,
        intent=RecommendationIntent(required_attributes=["oily skin", "oil-free", "skincare"]),
    )

    reason = output.recommendations[0].reason.lower()
    assert "oily skin" in reason
    assert "matches the request" in reason
    assert "ranks well" not in reason


def test_normalize_product_title_removes_common_size_tokens() -> None:
    assert normalize_product_title("Zia Natural Skincare Ultimate Body Butter, 6 oz") == normalize_product_title(
        "Zia Natural Skincare Ultimate Body Butter"
    )


def test_duplicate_titles_are_not_repeated_and_backfill_is_used() -> None:
    candidates = [
        make_scored_candidate(
            "asin-1",
            "Zia Natural Skincare Ultimate Body Butter, 6 oz",
            features=["body butter for dry skin"],
            matched_signals=["dry skin"],
            final_score=0.91,
        ),
        make_scored_candidate(
            "asin-2",
            "Zia Natural Skincare Ultimate Body Butter",
            features=["moisturizer for dry skin"],
            matched_signals=["dry skin"],
            final_score=0.89,
        ),
        make_scored_candidate(
            "asin-3",
            "Gentle Dry Skin Facial Moisturizer",
            features=["facial moisturizer", "dry skin"],
            matched_signals=["dry skin", "moisturizer"],
            final_score=0.82,
        ),
    ]

    output = fallback_rerank(
        candidates,
        limit=2,
        intent=RecommendationIntent(required_attributes=["skincare", "dry skin", "moisturizer"]),
    )

    assert [item.parent_asin for item in output.recommendations] == ["asin-1", "asin-3"]
    assert len(output.recommendations) == 2


def test_evidence_terms_are_deduplicated() -> None:
    candidate = make_scored_candidate(
        "asin-1",
        "Dry Skin Skincare Moisturizer",
        features=["dry skin moisturizer"],
        matched_signals=["skincare", "skincare", "dry skin"],
    )

    output = fallback_rerank(
        [candidate],
        limit=1,
        intent=RecommendationIntent(required_attributes=["skincare", "dry skin", "skincare"]),
    )

    evidence = output.recommendations[0].evidence
    assert len(evidence) == len(set(evidence))
    assert "skincare" in evidence
    assert "dry skin" in evidence
    assert all("_" not in term for term in evidence)


def test_cold_start_fallback_reason_prefers_concrete_request_evidence() -> None:
    candidate = make_scored_candidate(
        "asin-1",
        "Affordable Moisturizer for Dry Skin",
        features=["dry skin skincare", "gentle moisturizer"],
        matched_signals=[],
    )

    output = fallback_rerank(
        [candidate],
        limit=1,
        intent=RecommendationIntent(required_attributes=["affordable", "skincare", "dry skin", "moisturizer"]),
    )

    reason = output.recommendations[0].reason.lower()
    assert "dry skin" in reason
    assert "moisturizer" in reason
    assert "transparent score breakdown" not in reason


def test_fallback_reason_does_not_include_extremely_long_full_title() -> None:
    long_title = (
        "AZURE Hyaluronic & Retinol Anti Aging Under Eye Pads for Wrinkles "
        "Dark Circles Puffy Eyes Fine Lines 24K Gold Skincare Treatment"
    )
    candidate = make_scored_candidate(
        "asin-1",
        long_title,
        features=["hydrating skincare"],
        matched_signals=[],
    )

    output = fallback_rerank(
        [candidate],
        limit=1,
        intent=RecommendationIntent(required_attributes=["skincare", "hydrating"]),
    )

    reason = output.recommendations[0].reason
    assert long_title not in reason
    assert len(reason) < 150


def test_evidence_normalizes_underscored_terms_to_readable_phrases() -> None:
    candidate = make_scored_candidate(
        "asin-1",
        "Oil Free Non Comedogenic Cleanser",
        features=["oil free", "non comedogenic"],
        matched_signals=["oil_free", "non_comedogenic", "oil free"],
    )

    output = fallback_rerank(
        [candidate],
        limit=1,
        intent=RecommendationIntent(required_attributes=["oil_free", "non_comedogenic"]),
    )

    assert "oil free" in output.recommendations[0].evidence
    assert "non comedogenic" in output.recommendations[0].evidence
    assert all("_" not in term for term in output.recommendations[0].evidence)


def test_fallback_rerank_preserves_discovery_candidate_flag() -> None:
    candidate = make_scored_candidate("asin-1", "Limited Review Face Cream")
    candidate.score_breakdown.is_discovery_candidate = True

    output = fallback_rerank([candidate], limit=1, intent=RecommendationIntent(required_attributes=["skincare"]))

    recommendation = output.recommendations[0]
    assert recommendation.is_discovery_candidate is True
    assert recommendation.score_breakdown["is_discovery_candidate"] is True
