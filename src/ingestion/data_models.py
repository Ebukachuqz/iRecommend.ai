from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AmazonReview(BaseModel):
    model_config = ConfigDict(extra="allow")

    review_id: str
    user_id: str
    parent_asin: str
    rating: float | None = None
    title: str | None = None
    text: str | None = None
    timestamp: datetime | None = None
    verified_purchase: bool | None = None
    helpful_vote: int | None = None
    raw_review: dict[str, Any] = Field(default_factory=dict)


class AmazonProductMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    parent_asin: str
    category: str
    title: str | None = None
    main_category: str | None = None
    categories: list[Any] = Field(default_factory=list)
    features: list[Any] = Field(default_factory=list)
    description: list[Any] = Field(default_factory=list)
    price: float | None = None
    average_rating: float | None = None
    rating_number: int | None = None
    store: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


def parse_amazon_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
