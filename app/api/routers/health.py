from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_settings
from app.api.models.responses import HealthResponse, ReadyResponse
from src.config import Settings
from src.db.queries import check_table_reachable
from src.db.supabase_client import create_supabase_client


router = APIRouter(tags=["health"])

READINESS_TABLES = [
    "user_personas",
    "amazon_product_metadata",
    "simulation_results",
    "recommendation_runs",
    "product_embeddings",
]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="iRecommend API")


@router.get("/ready", response_model=ReadyResponse)
def ready(settings: Settings = Depends(get_app_settings)) -> ReadyResponse:
    checks: dict[str, object] = {
        "supabase_url_configured": bool(settings.supabase_url),
        "supabase_secret_key_configured": bool(settings.supabase_secret_key),
        "groq_api_key_configured": bool(settings.groq_api_key),
        "hf_token_configured": bool(settings.hf_token),
        "embedding_model": "configured" if settings.hf_token else "not_checked",
    }

    if not settings.supabase_url or not settings.supabase_secret_key:
        checks["supabase_connection"] = "not_configured"
        for table in READINESS_TABLES:
            checks[f"{table}_reachable"] = "not_checked"
        return ReadyResponse(status="not_ready", checks=checks)

    try:
        client = create_supabase_client(settings)
        checks["supabase_connection"] = "ok"
        for table in READINESS_TABLES:
            try:
                checks[f"{table}_reachable"] = check_table_reachable(table, client=client)
            except Exception as exc:
                checks[f"{table}_reachable"] = False
                checks[f"{table}_error"] = exc.__class__.__name__
    except Exception as exc:
        checks["supabase_connection"] = False
        checks["supabase_error"] = exc.__class__.__name__

    required_ok = bool(
        checks.get("supabase_connection") == "ok"
        and checks.get("groq_api_key_configured")
        and all(checks.get(f"{table}_reachable") is True for table in READINESS_TABLES)
    )
    return ReadyResponse(status="ready" if required_ok else "not_ready", checks=checks)
