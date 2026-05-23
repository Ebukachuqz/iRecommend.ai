from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.constants import DEFAULT_CATEGORY


class ProductSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    parent_asin: str
    title: str | None = None
    main_category: str | None = None
    categories: list[Any] = Field(default_factory=list)
    price: float | None = None
    features: list[Any] = Field(default_factory=list)
    description: list[Any] = Field(default_factory=list)
    average_rating: float | None = Field(default=None, ge=0, le=5)
    rating_number: int | None = None
    store: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("categories", "features", "description", mode="before")
    @classmethod
    def coerce_list_fields(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    @field_validator("details", mode="before")
    @classmethod
    def coerce_details(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


ProductDetails = ProductSnapshot


class ReviewSimulationRequest(BaseModel):
    user_id: str | None = None
    category: str = DEFAULT_CATEGORY
    parent_asin: str | None = None
    persona: dict[str, Any] | str | None = None
    product: dict[str, Any] | str | ProductSnapshot | None = None
    use_holdout: bool = False
    nigerian_mode: bool = False
    context: dict[str, Any] = Field(default_factory=dict)


class LLMReviewSimulationOutput(BaseModel):
    llm_predicted_rating: float = Field(ge=1, le=5)
    simulated_review_title: str
    simulated_review_text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    reasoning_summary: str
    evidence_used: list[str] = Field(default_factory=list)


class RatingPredictionBreakdown(BaseModel):
    user_average_rating: float = Field(ge=1, le=5)
    product_average_rating: float | None = Field(default=None, ge=0, le=5)
    preference_match_score: float = 0.0
    disliked_attribute_penalty: float = 0.0
    price_fit_score: float = 0.0
    strictness_adjustment: float = 0.0
    statistical_predicted_rating: float = Field(ge=1, le=5)
    llm_predicted_rating: float | None = Field(default=None, ge=1, le=5)
    final_predicted_rating: float | None = Field(default=None, ge=1, le=5)
    explanation: str


RatingPredictionResult = RatingPredictionBreakdown


class ReviewSimulationOutput(BaseModel):
    user_id: str | None = None
    category: str
    parent_asin: str
    product_title: str | None = None
    llm_predicted_rating: float = Field(ge=1, le=5)
    statistical_predicted_rating: float = Field(ge=1, le=5)
    final_predicted_rating: float = Field(ge=1, le=5)
    simulated_review_title: str
    simulated_review_text: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    reasoning_summary: str
    evidence_used: list[str] = Field(default_factory=list)
    rating_breakdown: RatingPredictionBreakdown
    nigerian_mode: bool = False
    model_name: str | None = None
    prompt_version: str | None = None
