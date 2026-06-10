from __future__ import annotations

import random
import time
from collections import Counter
from typing import Any

from supabase import Client

from app.saas.db import get_saas_client
from app.saas.models import MerchantBulkSimulationResponse, MerchantProductInput, MerchantSimulationResponse
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

    def fetch_persona_rows(self, org_id: str) -> list[dict[str, Any]]:
        response = (
            self.client.table("merchant_personas")
            .select("customer_id, persona")
            .eq("organisation_id", org_id)
            .execute()
        )
        return [dict(row) for row in response.data or []]

    def simulate_with_persona(
        self,
        *,
        org_id: str,
        customer_id: str,
        persona: dict[str, Any],
        product: MerchantProductInput,
    ) -> MerchantSimulationResponse:
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

    def simulate(self, org_id: str, customer_id: str, product: MerchantProductInput) -> MerchantSimulationResponse:
        persona = self.fetch_persona(org_id, customer_id)
        return self.simulate_with_persona(org_id=org_id, customer_id=customer_id, persona=persona, product=product)

    def select_bulk_personas(
        self,
        *,
        org_id: str,
        customer_ids: list[str] | None,
        sample_size: int,
    ) -> list[dict[str, Any]]:
        rows = self.fetch_persona_rows(org_id)
        if customer_ids:
            wanted = {customer_id.strip() for customer_id in customer_ids if customer_id.strip()}
            rows = [row for row in rows if str(row.get("customer_id") or "") in wanted]
        elif len(rows) > sample_size:
            rows = random.sample(rows, sample_size)

        if not rows:
            raise MerchantSimulationError("No merchant personas found for the requested simulation scope.")
        return rows[:sample_size] if not customer_ids else rows

    def simulate_bulk(
        self,
        *,
        org_id: str,
        product: MerchantProductInput,
        customer_ids: list[str] | None = None,
        sample_size: int = 3,
    ) -> MerchantBulkSimulationResponse:
        persona_rows = self.select_bulk_personas(org_id=org_id, customer_ids=customer_ids, sample_size=sample_size)
        simulations: list[MerchantSimulationResponse] = []
        praise_signals: list[str] = []
        concern_signals: list[str] = []

        for index, row in enumerate(persona_rows):
            customer_id = str(row.get("customer_id") or "")
            persona = row.get("persona") if isinstance(row.get("persona"), dict) else {}
            preferences = persona.get("preferences") if isinstance(persona, dict) else {}
            if isinstance(preferences, dict):
                praise_signals.extend(clean_signal_list(preferences.get("what_they_value")))
                praise_signals.extend(clean_signal_list(preferences.get("liked_attributes")))
                concern_signals.extend(clean_signal_list(preferences.get("common_complaints")))
                concern_signals.extend(clean_signal_list(preferences.get("disliked_attributes")))

            simulations.append(
                self.simulate_with_persona(
                    org_id=org_id,
                    customer_id=customer_id,
                    persona=persona,
                    product=product,
                )
            )
            if index < len(persona_rows) - 1:
                time.sleep(0.3)

        ratings = [max(1.0, min(5.0, result.final_predicted_rating)) for result in simulations]
        total = len(ratings)
        avg_rating = round(sum(ratings) / total, 2) if total else 0.0
        pct_4_plus = round(sum(1 for rating in ratings if rating >= 4) / total, 2) if total else 0.0
        pct_3_or_below = round(sum(1 for rating in ratings if rating <= 3) / total, 2) if total else 0.0
        top_praises = top_signals(praise_signals, ["Fit with customer priorities", "Clear practical value"])
        top_concerns = top_signals(concern_signals, ["Potential quality concerns", "Price sensitivity"])
        return MerchantBulkSimulationResponse(
            simulations=simulations,
            avg_predicted_rating=avg_rating,
            pct_4_plus=pct_4_plus,
            pct_3_or_below=pct_3_or_below,
            top_praises=top_praises,
            top_concerns=top_concerns,
            interpretation=build_interpretation(avg_rating, top_praises, top_concerns),
        )


def clean_signal_list(value: Any) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in items if str(item).strip()]


def top_signals(signals: list[str], fallback: list[str], limit: int = 3) -> list[str]:
    counted = [label for label, _ in Counter(signals).most_common(limit)]
    return counted or fallback[:limit]


def build_interpretation(avg_rating: float, praises: list[str], concerns: list[str]) -> str:
    if avg_rating >= 4:
        posture = "Customers are likely to respond positively"
    elif avg_rating >= 3:
        posture = "Customers may be interested, but the launch needs careful positioning"
    else:
        posture = "Customers may resist this launch unless the offer is sharpened"

    praise = praises[0].lower() if praises else "the core value proposition"
    concern = concerns[0].lower() if concerns else "possible objections"
    return (
        f"{posture} because it connects with {praise}. Watch {concern}; "
        "address it directly in product copy, pricing, and launch messaging."
    )
