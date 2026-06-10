from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from app.saas.auth import get_current_user_id, validate_organisation_owner
from app.saas.db import get_saas_client
from app.saas.models import (
    MyOrganisationResponse,
    OrganisationCreateRequest,
    OrganisationCreateResponse,
    OrganisationResponse,
    OrganisationSummaryResponse,
    OrganisationSettingsUpdateRequest,
    SuccessResponse,
)


router = APIRouter(prefix="/saas", tags=["saas-organisations"])


def fetch_user_organisation(user_id: str) -> dict | None:
    response = (
        get_saas_client()
        .table("organisations")
        .select("*")
        .eq("owner_id", user_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return dict(rows[0]) if rows else None


def count_table_rows(table_name: str, org_id: str) -> int:
    response = (
        get_saas_client()
        .table(table_name)
        .select("id", count="exact")
        .eq("organisation_id", org_id)
        .limit(1)
        .execute()
    )
    count = getattr(response, "count", None)
    if count is not None:
        return int(count)
    return len(response.data or [])


@router.get("/me/organisation", response_model=MyOrganisationResponse)
def get_my_organisation(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> MyOrganisationResponse:
    user_id = get_current_user_id(authorization)
    try:
        row = fetch_user_organisation(user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch organisation.",
        ) from exc

    return MyOrganisationResponse(
        organisation=OrganisationResponse.model_validate(row) if row else None
    )


@router.post("/organisations", response_model=OrganisationCreateResponse)
def create_organisation(
    payload: OrganisationCreateRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> OrganisationCreateResponse:
    user_id = get_current_user_id(authorization)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Business name is required.")

    try:
        existing = fetch_user_organisation(user_id)
        if existing:
            return OrganisationCreateResponse(org_id=str(existing["id"]), name=str(existing["name"]))

        response = (
            get_saas_client()
            .table("organisations")
            .insert({"name": name, "owner_id": user_id})
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organisation.",
        ) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Organisation was not created.",
        )

    row = rows[0]
    return OrganisationCreateResponse(org_id=str(row["id"]), name=str(row["name"]))


@router.patch("/organisations/{org_id}/settings", response_model=SuccessResponse)
def update_organisation_settings(
    org_id: str,
    payload: OrganisationSettingsUpdateRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> SuccessResponse:
    user_id = get_current_user_id(authorization)
    validate_organisation_owner(org_id, user_id)

    try:
        get_saas_client().table("organisations").update(
            {"market_context": payload.market_context}
        ).eq("id", org_id).eq("owner_id", user_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update organisation settings.",
        ) from exc

    return SuccessResponse(success=True)


@router.get("/organisations/{org_id}/summary", response_model=OrganisationSummaryResponse)
def get_organisation_summary(
    org_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> OrganisationSummaryResponse:
    user_id = get_current_user_id(authorization)
    validate_organisation_owner(org_id, user_id)
    latest_response = (
        get_saas_client()
        .table("csv_uploads")
        .select("*")
        .eq("organisation_id", org_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    latest_upload = (latest_response.data or [None])[0]
    return OrganisationSummaryResponse(
        persona_count=count_table_rows("merchant_personas", org_id),
        review_count=count_table_rows("merchant_reviews", org_id),
        latest_upload=latest_upload,
        latest_upload_status=(latest_upload or {}).get("status") if latest_upload else None,
    )


@router.get("/organisations/{org_id}", response_model=OrganisationResponse)
def get_organisation(
    org_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> OrganisationResponse:
    user_id = get_current_user_id(authorization)
    row = validate_organisation_owner(org_id, user_id)
    return OrganisationResponse.model_validate(row)
