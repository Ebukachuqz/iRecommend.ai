from __future__ import annotations

from app.api.main import app


def test_unified_backend_registers_prototype_and_saas_routes() -> None:
    paths = {route.path for route in app.routes}

    assert "/users" in paths
    assert "/reviews/simulate" in paths
    assert "/saas/me/organisation" in paths
    assert "/saas/uploads/reviews" in paths
    assert "/saas/organisations/{org_id}/simulate/bulk" in paths
