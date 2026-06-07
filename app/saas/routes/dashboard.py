from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.saas.auth import get_current_user_id, validate_organisation_owner
from app.saas.db import get_saas_client
from app.saas.models import (
    CustomerProfileResponse,
    CustomerSummary,
    CustomersResponse,
    DashboardOverviewResponse,
    MerchantSimulationRequest,
    MerchantSimulationResponse,
)
from app.saas.services.dashboard_service import build_overview, summarize_customer
from app.saas.services.simulator_service import MerchantSimulationError, MerchantSimulator


router = APIRouter(prefix="/saas", tags=["saas-dashboard"])


def require_org(org_id: str, authorization: str | None) -> None:
    user_id = get_current_user_id(authorization)
    validate_organisation_owner(org_id, user_id)


def fetch_persona_rows(org_id: str) -> list[dict]:
    response = (
        get_saas_client()
        .table("merchant_personas")
        .select("*")
        .eq("organisation_id", org_id)
        .execute()
    )
    return [dict(row) for row in response.data or []]


def fetch_latest_upload(org_id: str) -> dict | None:
    response = (
        get_saas_client()
        .table("csv_uploads")
        .select("*")
        .eq("organisation_id", org_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return dict(rows[0]) if rows else None


@router.get("/organisations/{org_id}/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    org_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> DashboardOverviewResponse:
    require_org(org_id, authorization)
    return DashboardOverviewResponse.model_validate(
        build_overview(fetch_persona_rows(org_id), fetch_latest_upload(org_id))
    )


@router.get("/organisations/{org_id}/customers", response_model=CustomersResponse)
def get_dashboard_customers(
    org_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
) -> CustomersResponse:
    require_org(org_id, authorization)
    rows = fetch_persona_rows(org_id)
    if search and search.strip():
        needle = search.strip().lower()
        rows = [row for row in rows if needle in str(row.get("customer_id") or "").lower()]
    rows = sorted(rows, key=lambda row: str(row.get("customer_id") or ""))
    total = len(rows)
    start = (page - 1) * per_page
    page_rows = rows[start : start + per_page]
    return CustomersResponse(
        customers=[CustomerSummary.model_validate(summarize_customer(row)) for row in page_rows],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/organisations/{org_id}/customers/{customer_id}", response_model=CustomerProfileResponse)
def get_dashboard_customer(
    org_id: str,
    customer_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> CustomerProfileResponse:
    require_org(org_id, authorization)
    response = (
        get_saas_client()
        .table("merchant_personas")
        .select("*")
        .eq("organisation_id", org_id)
        .eq("customer_id", customer_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer persona not found.")
    row = dict(rows[0])
    return CustomerProfileResponse(
        customer_id=str(row.get("customer_id") or customer_id),
        persona=dict(row.get("persona") or {}),
        review_count=int(row.get("review_count") or 0),
    )


@router.post("/organisations/{org_id}/simulate", response_model=MerchantSimulationResponse)
def simulate_customer_reaction(
    org_id: str,
    payload: MerchantSimulationRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> MerchantSimulationResponse:
    require_org(org_id, authorization)
    try:
        return MerchantSimulator().simulate(org_id, payload.customer_id, payload.product)
    except MerchantSimulationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to simulate this customer reaction.",
        ) from exc
