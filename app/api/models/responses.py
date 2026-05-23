from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, Any]


class ErrorResponse(BaseModel):
    detail: str


class UserPersonaSummary(BaseModel):
    user_id: str
    category: str
    review_count: int | None = None
    average_rating: float | None = None
    persona_version: str | None = None


class ProductSummary(BaseModel):
    parent_asin: str
    title: str | None = None
    main_category: str | None = None
    price: float | None = None
    average_rating: float | None = None
    rating_number: int | None = None
    store: str | None = None
