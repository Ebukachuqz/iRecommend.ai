from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Strictness = Literal["strict", "moderate", "generous"]
Length = Literal["short", "medium", "long"]
DetailLevel = Literal["low", "medium", "high"]
Formality = Literal["casual", "mixed", "formal"]
SensitivityWithUnknown = Literal["low", "medium", "high", "unknown"]
QualitySensitivity = Literal["low", "medium", "high"]


class WritingStyle(BaseModel):
    tone: str = "unknown"
    length: Length = "medium"
    detail_level: DetailLevel = "medium"
    formality: Formality = "mixed"
    vocabulary_markers: list[str] = Field(default_factory=list)
    common_phrases: list[str] = Field(default_factory=list)

    @field_validator("vocabulary_markers", "common_phrases", mode="before")
    @classmethod
    def coerce_string_lists(cls, value: Any) -> list[str]:
        return coerce_list_of_strings(value)


class Preferences(BaseModel):
    liked_product_types: list[str] = Field(default_factory=list)
    disliked_product_types: list[str] = Field(default_factory=list)
    liked_attributes: list[str] = Field(default_factory=list)
    disliked_attributes: list[str] = Field(default_factory=list)
    what_they_value: list[str] = Field(default_factory=list)
    common_complaints: list[str] = Field(default_factory=list)

    @field_validator(
        "liked_product_types",
        "disliked_product_types",
        "liked_attributes",
        "disliked_attributes",
        "what_they_value",
        "common_complaints",
        mode="before",
    )
    @classmethod
    def coerce_string_lists(cls, value: Any) -> list[str]:
        return coerce_list_of_strings(value)


class RatingBehavior(BaseModel):
    average_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    rating_distribution: dict[Literal["1", "2", "3", "4", "5"], int] = Field(
        default_factory=lambda: {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    )
    strictness: Strictness = "moderate"
    rating_patterns: str = "unknown"

    @field_validator("rating_distribution", mode="before")
    @classmethod
    def normalize_distribution(cls, value: Any) -> dict[str, int]:
        if not isinstance(value, dict):
            value = {}
        return {str(key): int(value.get(str(key), value.get(key, 0)) or 0) for key in range(1, 6)}

    @model_validator(mode="after")
    def require_distribution_keys(self) -> "RatingBehavior":
        expected = {"1", "2", "3", "4", "5"}
        if set(self.rating_distribution.keys()) != expected:
            raise ValueError("rating_distribution must contain keys 1, 2, 3, 4, and 5")
        return self


class PurchaseBehavior(BaseModel):
    preferred_categories: list[str] = Field(default_factory=list)
    price_sensitivity: SensitivityWithUnknown = "unknown"
    quality_sensitivity: QualitySensitivity = "medium"
    verified_purchase_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("preferred_categories", mode="before")
    @classmethod
    def coerce_string_lists(cls, value: Any) -> list[str]:
        return coerce_list_of_strings(value)


class PersonaEvidence(BaseModel):
    positive_examples: list[str] = Field(default_factory=list)
    negative_examples: list[str] = Field(default_factory=list)

    @field_validator("positive_examples", "negative_examples", mode="before")
    @classmethod
    def coerce_string_lists(cls, value: Any) -> list[str]:
        return coerce_list_of_strings(value)


class UserPersona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    writing_style: WritingStyle = Field(default_factory=WritingStyle)
    preferences: Preferences = Field(default_factory=Preferences)
    rating_behavior: RatingBehavior = Field(default_factory=RatingBehavior)
    purchase_behavior: PurchaseBehavior = Field(default_factory=PurchaseBehavior)
    cultural_signals: str = ""
    evidence: PersonaEvidence = Field(default_factory=PersonaEvidence)
    extra_persona_signals: dict[str, Any] = Field(default_factory=dict)


def coerce_list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item).strip()]
    return [str(value)]
