from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class CountItem(BaseModel):
    label: str
    count: int


class DashboardOverviewResponse(BaseModel):
    total_personas: int
    avg_strictness: str | None = None
    top_values: list[str] = Field(default_factory=list)
    top_values_counts: list[CountItem] = Field(default_factory=list)
    top_complaints: list[str] = Field(default_factory=list)
    top_complaints_counts: list[CountItem] = Field(default_factory=list)
    categories_covered: list[str] = Field(default_factory=list)
    categories_covered_counts: list[CountItem] = Field(default_factory=list)
    last_upload_at: str | None = None


class CustomerSummary(BaseModel):
    customer_id: str
    review_count: int = 0
    avg_rating: float = 0.0
    strictness: str = "moderate"
    top_values: list[str] = Field(default_factory=list)
    top_category: str | None = None


class CustomersResponse(BaseModel):
    customers: list[CustomerSummary]
    total: int
    page: int
    per_page: int


class CustomerProfileResponse(BaseModel):
    customer_id: str
    persona: dict[str, Any]
    review_count: int = 0


class MerchantProductInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=120)
    price: float | None = Field(default=None, ge=0)
    features: list[str] = Field(default_factory=list)
    description: str | None = None


class MerchantProductResponse(BaseModel):
    id: str | None = None
    product_id: str | None = None
    product_name: str
    category: str
    price: float | None = None
    description: str | None = None
    features: list[str] = Field(default_factory=list)


class MerchantProductsResponse(BaseModel):
    products: list[MerchantProductResponse] = Field(default_factory=list)


class MerchantSimulationRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    product: MerchantProductInput


class MerchantSimulationResponse(BaseModel):
    customer_id: str
    product_title: str | None = None
    final_predicted_rating: float
    simulated_review_title: str
    simulated_review_text: str
    confidence: float | None = None
    reasoning_summary: str | None = None
    evidence_used: list[str] = Field(default_factory=list)


class MerchantBulkSimulationRequest(BaseModel):
    product: MerchantProductInput
    customer_ids: list[str] | None = None
    sample_size: int = Field(default=3, ge=1, le=10)

    @field_validator("sample_size")
    @classmethod
    def validate_sample_size(cls, value: int) -> int:
        if value not in {3, 5, 10}:
            raise ValueError("sample_size must be one of 3, 5, or 10.")
        return value


class MerchantBulkSimulationResponse(BaseModel):
    simulations: list[MerchantSimulationResponse] = Field(default_factory=list)
    avg_predicted_rating: float = 0.0
    pct_4_plus: float = 0.0
    pct_3_or_below: float = 0.0
    top_praises: list[str] = Field(default_factory=list)
    top_concerns: list[str] = Field(default_factory=list)
    interpretation: str
