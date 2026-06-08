from __future__ import annotations

from typing import Any

from app.saas.models import MerchantProductInput, MerchantSimulationResponse
from app.saas.routes import dashboard
from app.saas.services.dashboard_service import build_overview, summarize_customer
from app.saas.services.simulator_service import MerchantSimulator, build_product_snapshot


def sample_persona(strictness: str = "strict") -> dict[str, Any]:
    return {
        "preferences": {
            "what_they_value": ["quality", "value for money", "quality"],
            "common_complaints": ["slow shipping", "poor quality"],
        },
        "rating_behavior": {
            "average_rating": 3.8,
            "strictness": strictness,
        },
        "purchase_behavior": {
            "preferred_categories": ["Electronics", "Accessories"],
        },
    }


def test_build_overview_returns_arrays_and_counts() -> None:
    rows = [
        {"customer_id": "C-1", "persona": sample_persona("strict")},
        {
            "customer_id": "C-2",
            "persona": {
                "preferences": {
                    "what_they_value": ["quality", "durability"],
                    "common_complaints": ["slow shipping"],
                },
                "rating_behavior": {"average_rating": 4.2, "strictness": "moderate"},
                "purchase_behavior": {"preferred_categories": ["Electronics"]},
            },
        },
    ]

    overview = build_overview(rows, {"completed_at": "2026-06-07T12:00:00Z"})

    assert overview["total_personas"] == 2
    assert overview["avg_strictness"] in {"strict", "moderate"}
    assert overview["top_values"][0] == "quality"
    assert overview["top_values_counts"][0] == {"label": "quality", "count": 3}
    assert overview["top_complaints_counts"][0] == {"label": "slow shipping", "count": 2}
    assert overview["categories_covered_counts"][0] == {"label": "Electronics", "count": 2}
    assert overview["last_upload_at"] == "2026-06-07T12:00:00Z"


def test_summarize_customer_extracts_persona_fields() -> None:
    summary = summarize_customer({"customer_id": "C-1", "review_count": 9, "persona": sample_persona()})

    assert summary["customer_id"] == "C-1"
    assert summary["review_count"] == 9
    assert summary["avg_rating"] == 3.8
    assert summary["strictness"] == "strict"
    assert summary["top_values"][:2] == ["quality", "value for money"]
    assert summary["top_category"] == "Electronics"


class FakeResponse:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class FakeTable:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data

    def select(self, *_args: Any, **_kwargs: Any) -> "FakeTable":
        return self

    def eq(self, *_args: Any, **_kwargs: Any) -> "FakeTable":
        return self

    def limit(self, *_args: Any, **_kwargs: Any) -> "FakeTable":
        return self

    def order(self, *_args: Any, **_kwargs: Any) -> "FakeTable":
        return self

    def execute(self) -> FakeResponse:
        return FakeResponse(self.data)


class FakeClient:
    def __init__(self, persona: dict[str, Any]) -> None:
        self.persona = persona

    def table(self, name: str) -> FakeTable:
        assert name == "merchant_personas"
        return FakeTable([{"customer_id": "C-1", "persona": self.persona}])


def test_build_product_snapshot_uses_custom_product_identity() -> None:
    snapshot = build_product_snapshot(
        MerchantProductInput(title="Desk lamp", category="Office", price=25, features=["metal body"])
    )

    assert snapshot["parent_asin"] == "saas_custom_product"
    assert snapshot["title"] == "Desk lamp"
    assert snapshot["categories"] == ["Office"]


def test_merchant_simulator_uses_custom_mode_without_client_persistence(monkeypatch) -> None:
    calls: list[Any] = []

    def fake_simulate_review(request: Any, client: Any = None) -> Any:
        calls.append((request, client))

        class Output:
            product_title = "Desk lamp"
            final_predicted_rating = 4.0
            simulated_review_title = "Solid choice"
            simulated_review_text = "This customer would likely appreciate the build quality."
            confidence = 0.8
            reasoning_summary = "Custom persona and product were used."
            evidence_used = ["quality"]

        return Output()

    monkeypatch.setattr("app.saas.services.simulator_service.simulate_review", fake_simulate_review)
    simulator = MerchantSimulator(client=FakeClient(sample_persona()))  # type: ignore[arg-type]

    result = simulator.simulate(
        "org-1",
        "C-1",
        MerchantProductInput(title="Desk lamp", category="Office", features=["metal body"]),
    )

    assert result.final_predicted_rating == 4.0
    assert len(calls) == 1
    request, client = calls[0]
    assert client is None
    assert request.persona is not None
    assert request.product is not None
    assert request.user_id is None


def test_dashboard_routes_validate_organisation_ownership(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(dashboard, "get_current_user_id", lambda authorization: "user-1")
    monkeypatch.setattr(
        dashboard,
        "validate_organisation_owner",
        lambda org_id, user_id: calls.append((org_id, user_id)) or {"id": org_id},
    )

    dashboard.require_org("org-1", "Bearer token")

    assert calls == [("org-1", "user-1")]


class ProductFakeClient:
    def __init__(self) -> None:
        self.products = [
            {
                "id": "prod-row-1",
                "product_id": "SKU-1",
                "product_name": "Air purifier",
                "category": "Home",
                "price": 79.99,
                "description": "Compact cleaner",
                "features": ["HEPA", "Quiet"],
            }
        ]

    def table(self, name: str) -> FakeTable:
        assert name == "merchant_products"
        return FakeTable(self.products)


def test_product_listing_returns_merchant_catalog(monkeypatch) -> None:
    monkeypatch.setattr(dashboard, "require_org", lambda org_id, authorization: None)
    monkeypatch.setattr(dashboard, "get_saas_client", lambda: ProductFakeClient())

    response = dashboard.get_merchant_products("org-1", "Bearer token")

    assert response.products[0].product_name == "Air purifier"
    assert response.products[0].features == ["HEPA", "Quiet"]


def test_bulk_simulation_aggregates_sampled_personas(monkeypatch) -> None:
    rows = [
        {"customer_id": "C-1", "persona": sample_persona("strict")},
        {"customer_id": "C-2", "persona": sample_persona("moderate")},
        {"customer_id": "C-3", "persona": sample_persona("generous")},
        {"customer_id": "C-4", "persona": sample_persona("strict")},
    ]

    class BulkFakeClient:
        def table(self, name: str) -> FakeTable:
            assert name == "merchant_personas"
            return FakeTable(rows)

    def fake_simulate_with_persona(self: MerchantSimulator, **kwargs: Any) -> Any:
        customer_id = kwargs["customer_id"]
        rating = {"C-1": 5.0, "C-2": 4.0, "C-3": 3.0, "C-4": 2.0}[customer_id]
        return MerchantSimulationResponse(
            customer_id=customer_id,
            product_title="Desk lamp",
            final_predicted_rating=rating,
            simulated_review_title="Launch reaction",
            simulated_review_text="A concise simulated review.",
            confidence=0.7,
            reasoning_summary="Persona fit.",
            evidence_used=[],
        )

    monkeypatch.setattr("app.saas.services.simulator_service.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(MerchantSimulator, "simulate_with_persona", fake_simulate_with_persona)
    simulator = MerchantSimulator(client=BulkFakeClient())  # type: ignore[arg-type]

    result = simulator.simulate_bulk(
        org_id="org-1",
        product=MerchantProductInput(title="Desk lamp", category="Office"),
        sample_size=3,
    )

    assert len(result.simulations) == 3
    assert result.avg_predicted_rating > 0
    assert 0 <= result.pct_4_plus <= 1
    assert result.top_praises
    assert result.top_concerns
