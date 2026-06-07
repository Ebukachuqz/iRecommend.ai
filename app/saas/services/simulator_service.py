from __future__ import annotations

from typing import Any

from supabase import Client

from app.saas.db import get_saas_client
from app.saas.models import MerchantProductInput, MerchantSimulationResponse
from src.task_a_simulation.schema import ReviewSimulationRequest
from src.task_a_simulation.service import simulate_review


class MerchantSimulationError(RuntimeError):
    pass


def build_product_snapshot(product: MerchantProductInput) -> dict[str, Any]:
    return {
        "parent_asin": "saas_custom_product",
        "title": product.title,
        "main_category": product.category,
        "categories": [product.category],
        "price": product.price,
        "features": product.features,
        "description": [product.description] if product.description else [],
        "average_rating": 4.0,
        "rating_number": 20,
        "store": "Merchant uploaded catalog",
        "details": {},
    }


class MerchantSimulator:
    def __init__(self, client: Client | None = None) -> None:
        self.client = client or get_saas_client()

    def fetch_persona(self, org_id: str, customer_id: str) -> dict[str, Any]:
        response = (
            self.client.table("merchant_personas")
            .select("customer_id, persona")
            .eq("organisation_id", org_id)
            .eq("customer_id", customer_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise MerchantSimulationError(f"No merchant persona found for customer_id={customer_id!r}.")
        persona = rows[0].get("persona") or {}
        if not isinstance(persona, dict):
            raise MerchantSimulationError("Stored merchant persona is not a JSON object.")
        return persona

    def simulate(self, org_id: str, customer_id: str, product: MerchantProductInput) -> MerchantSimulationResponse:
        persona = self.fetch_persona(org_id, customer_id)
        request = ReviewSimulationRequest(
            user_id=None,
            category=product.category,
            parent_asin="saas_custom_product",
            persona=persona,
            product=build_product_snapshot(product),
            context={"source": "saas_dashboard", "organisation_id": org_id},
        )
        output = simulate_review(request, client=None)
        return MerchantSimulationResponse(
            customer_id=customer_id,
            product_title=output.product_title,
            final_predicted_rating=output.final_predicted_rating,
            simulated_review_title=output.simulated_review_title,
            simulated_review_text=output.simulated_review_text,
            confidence=output.confidence,
            reasoning_summary=output.reasoning_summary,
            evidence_used=output.evidence_used,
        )
