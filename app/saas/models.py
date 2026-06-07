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


class UploadStatusResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    upload_id: str
    upload_type: str
    status: str
    total_rows: int = 0
    processed_rows: int = 0
    personas_generated: int = 0
    error_message: str | None = None
    processing_summary: dict[str, Any] = Field(default_factory=dict)


class UploadCreateResponse(BaseModel):
    upload_id: str
    total_rows: int


class OrganisationSummaryResponse(BaseModel):
    persona_count: int
    review_count: int
    latest_upload: dict[str, Any] | None = None
    latest_upload_status: str | None = None
