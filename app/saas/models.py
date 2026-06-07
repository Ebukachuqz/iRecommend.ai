from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrganisationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class OrganisationCreateResponse(BaseModel):
    org_id: str
    name: str


class OrganisationSettingsUpdateRequest(BaseModel):
    market_context: str = Field(default="global", min_length=1, max_length=80)


class SuccessResponse(BaseModel):
    success: bool = True


class OrganisationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    market_context: str | None = None
    owner_id: str | None = None
    created_at: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict, exclude=True)


class MyOrganisationResponse(BaseModel):
    organisation: OrganisationResponse | None = None
