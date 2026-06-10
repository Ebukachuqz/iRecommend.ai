from __future__ import annotations

from fastapi import HTTPException, status

from app.saas.db import get_saas_client


def get_current_user_id(authorization: str | None) -> str:
    """Validate a Supabase bearer token and return the authenticated user id."""

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be in the format: Bearer <token>.",
        )

    try:
        response = get_saas_client().auth.get_user(token.strip())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from exc

    user = getattr(response, "user", None)
    user_id = getattr(user, "id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )
    return str(user_id)


def validate_organisation_owner(org_id: str, user_id: str) -> dict:
    """Return an organisation row if it belongs to the authenticated user."""

    try:
        response = (
            get_saas_client()
            .table("organisations")
            .select("*")
            .eq("id", org_id)
            .eq("owner_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to validate organisation ownership.",
        ) from exc

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organisation does not belong to the authenticated user.",
        )
    return dict(rows[0])
