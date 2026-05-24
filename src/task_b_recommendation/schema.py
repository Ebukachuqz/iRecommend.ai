from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.constants import DEFAULT_CATEGORY


class RecommendationIntent(BaseModel):
    interpreted_need: str = ""
    explicit_constraints: dict[str, Any] = Field(default_factory=dict)
    implicit_constraints_from_persona: dict[str, Any] = Field(default_factory=dict)
    avoid: list[str] = Field(default_factory=list)
    retrieval_query: str = ""
    category_filter: str | None = None
    price_max: float | None = None
    required_attributes: list[str] = Field(default_factory=list)
    excluded_attributes: list[str] = Field(default_factory=list)

    @field_validator("avoid", "required_attributes", "excluded_attributes", mode="before")
    @classmethod
    def coerce_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None and str(item).strip()]
        return [str(value)]


class RecommendationRequest(BaseModel):
    user_id: str | None = None
    category: str = DEFAULT_CATEGORY
    request: str | None = None
    persona: dict[str, Any] | str | None = None
    onboarding_answers: dict[str, Any] | None = None
    limit: int = Field(default=5, ge=1, le=50)
    session_id: str | None = None
    cold_start: bool = False
    context: dict[str, Any] = Field(default_factory=dict)


class RecommendationCandidate(BaseModel):
    parent_asin: str
    title: str | None = None
    product: dict[str, Any] = Field(default_factory=dict)
    semantic_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    collaborative_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieval_source: str = "fallback"
    retrieval_sources: list[str] = Field(default_factory=list)
    source_evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("retrieval_sources", "source_evidence", "warnings", mode="before")
    @classmethod
    def coerce_string_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(item) for item in value if item is not None and str(item).strip()]
        return [str(value)]


class RecommendationScoreBreakdown(BaseModel):
    semantic_similarity: float = Field(ge=0.0, le=1.0)
    preference_match: float = Field(ge=0.0, le=1.0)
    product_quality: float = Field(ge=0.0, le=1.0)
    price_fit: float = Field(ge=0.0, le=1.0)
    popularity_reliability: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    is_discovery_candidate: bool = False
    matched_persona_signals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ScoredRecommendationCandidate(RecommendationCandidate):
    score_breakdown: RecommendationScoreBreakdown


class RerankedRecommendation(BaseModel):
    parent_asin: str
    rank: int = Field(ge=1)
    title: str | None = None
    reason: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    is_discovery_candidate: bool = False
    evidence: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


class RerankerOutput(BaseModel):
    recommendations: list[RerankedRecommendation]


class RecommendationOutput(BaseModel):
    user_id: str | None = None
    category: str = DEFAULT_CATEGORY
    request: str | None = None
    intent: RecommendationIntent
    recommendations: list[RerankedRecommendation]
    candidate_count: int
    cold_start: bool = False
    session_id: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None


class RecommendationSessionState(BaseModel):
    session_id: str
    user_id: str | None = None
    category: str = DEFAULT_CATEGORY
    persona: dict[str, Any] = Field(default_factory=dict)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    active_constraints: dict[str, Any] = Field(
        default_factory=lambda: {
            "price_max": None,
            "excluded_products": [],
            "required_attributes": [],
            "excluded_attributes": [],
            "category_filter": None,
        }
    )
    shown_products: list[str] = Field(default_factory=list)
