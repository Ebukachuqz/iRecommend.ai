from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.constants import DEFAULT_CATEGORY


class ReviewSimulationAPIRequest(BaseModel):
    user_id: str | None = None
    category: str = DEFAULT_CATEGORY
    parent_asin: str | None = None
    persona: dict[str, Any] | str | None = None
    product: dict[str, Any] | str | None = None
    use_holdout: bool = False
    nigerian_mode: bool = False
    context: dict[str, Any] = Field(default_factory=dict)


class RecommendationAPIRequest(BaseModel):
    user_id: str | None = None
    category: str = DEFAULT_CATEGORY
    persona: dict[str, Any] | str | None = None
    request: str | None = None
    limit: int = Field(default=5, ge=1, le=50)
    session_id: str | None = None
    cold_start: bool = False
    context: dict[str, Any] = Field(default_factory=dict)


class ColdStartRecommendationAPIRequest(BaseModel):
    request: str
    limit: int = Field(default=5, ge=1, le=50)
    context: dict[str, Any] = Field(default_factory=dict)


class SessionMessageRequest(BaseModel):
    user_id: str | None = None
    category: str = DEFAULT_CATEGORY
    message: str
    limit: int = Field(default=5, ge=1, le=50)
