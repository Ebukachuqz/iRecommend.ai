from __future__ import annotations

import json
from collections import Counter
from statistics import mean
from typing import Any

from supabase import Client

from src.config import get_settings
from src.constants import PERSONA_TRAIN_SPLIT
from src.db.supabase_client import get_supabase_client
from src.llm.groq_client import get_groq_chat
from src.llm.logging import log_llm_response
from src.llm.parsers import get_json_parser
from src.personas.prompts import PERSONA_PROMPT, PERSONA_SCHEMA_EXAMPLE, PERSONA_SYSTEM_INSTRUCTIONS
from src.personas.validator import persona_to_storage_dict, validate_persona


class PersonaGenerator:
    def __init__(self, client: Client | None = None) -> None:
        self.settings = get_settings()
        self.client = client or get_supabase_client()

    def fetch_user_reviews(self, user_id: str, category: str | None = None) -> list[dict[str, Any]]:
        category = category or self.settings.default_category
        response = (
            self.client.table("amazon_reviews")
            .select("*")
            .eq("user_id", user_id)
            .eq("category", category)
            .eq("task_split", PERSONA_TRAIN_SPLIT)
            .eq("used_for_persona", True)
            .order("timestamp", desc=False)
            .execute()
        )
        return list(response.data or [])

    def fetch_product_metadata(self, parent_asins: list[str]) -> dict[str, dict[str, Any]]:
        if not parent_asins:
            return {}
        response = (
            self.client.table("amazon_product_metadata")
            .select("*")
            .in_("parent_asin", list(dict.fromkeys(parent_asins)))
            .execute()
        )
        return {item["parent_asin"]: item for item in response.data or []}

    def enrich_reviews(self, reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
        metadata_by_asin = self.fetch_product_metadata([review["parent_asin"] for review in reviews])
        enriched = []
        for review in reviews:
            item = dict(review)
            item["product"] = metadata_by_asin.get(review["parent_asin"], {})
            enriched.append(item)
        return enriched

    def compute_user_stats(self, reviews: list[dict[str, Any]]) -> dict[str, Any]:
        ratings = [float(review["rating"]) for review in reviews if review.get("rating") is not None]
        distribution = Counter(str(int(round(rating))) for rating in ratings)
        verified_values = [
            bool(review["verified_purchase"])
            for review in reviews
            if review.get("verified_purchase") is not None
        ]
        return {
            "review_count": len(reviews),
            "average_rating": round(mean(ratings), 3) if ratings else 0.0,
            "rating_distribution": {str(key): distribution.get(str(key), 0) for key in range(1, 6)},
            "verified_purchase_ratio": round(sum(verified_values) / len(verified_values), 3)
            if verified_values
            else 0.0,
            "source_review_ids": [review["review_id"] for review in reviews],
        }

    def format_review_context(self, reviews: list[dict[str, Any]], max_reviews: int = 20) -> str:
        selected = reviews[-max_reviews:]
        blocks = []
        for review in selected:
            product = review.get("product") or {}
            blocks.append(
                "\n".join(
                    [
                        f"Review ID: {review.get('review_id')}",
                        f"Rating: {review.get('rating')}",
                        f"Title: {review.get('title') or ''}",
                        f"Text: {review.get('text') or ''}",
                        f"Verified purchase: {review.get('verified_purchase')}",
                        f"Product title: {product.get('title') or ''}",
                        f"Main category: {product.get('main_category') or product.get('category') or ''}",
                        f"Features: {product.get('features') or []}",
                        f"Description: {product.get('description') or []}",
                    ]
                )
            )
        return "\n\n---\n\n".join(blocks)

    def generate_persona_payload(
        self,
        user_id: str,
        category: str | None = None,
        *,
        max_reviews: int = 20,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        category = category or self.settings.default_category
        reviews = self.fetch_user_reviews(user_id, category)
        if not reviews:
            raise ValueError(f"No persona_train reviews found for user_id={user_id!r}, category={category!r}.")

        enriched_reviews = self.enrich_reviews(reviews)
        stats = self.compute_user_stats(reviews)
        prompt_input = {
            "instructions": PERSONA_SYSTEM_INSTRUCTIONS,
            "category": category,
            "user_stats": json.dumps(stats, indent=2),
            "review_context": self.format_review_context(enriched_reviews, max_reviews=max_reviews),
            "schema_example": json.dumps(PERSONA_SCHEMA_EXAMPLE, indent=2),
        }
        parser = get_json_parser()
        llm = get_groq_chat(self.settings.groq_model)
        chain = PERSONA_PROMPT | llm
        raw_message = chain.invoke(prompt_input)
        raw_text = getattr(raw_message, "content", str(raw_message))
        raw_payload = parser.parse(raw_text)
        log_llm_response(
            "persona_generation",
            {
                "user_id": user_id,
                "category": category,
                "model_name": self.settings.groq_model,
                "prompt_version": self.settings.persona_prompt_version,
                "raw_text": raw_text,
                "parsed_payload": raw_payload,
            },
        )
        return raw_payload, stats

    def generate_and_validate(
        self,
        user_id: str,
        category: str | None = None,
        *,
        max_reviews: int = 20,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raw_payload, stats = self.generate_persona_payload(user_id, category, max_reviews=max_reviews)
        persona = validate_persona(raw_payload, repair=True)
        return persona_to_storage_dict(persona), stats

    def store_persona(
        self,
        user_id: str,
        category: str,
        persona: dict[str, Any],
        source_review_ids: list[str],
    ) -> None:
        payload = {
            "user_id": user_id,
            "category": category,
            "persona": persona,
            "persona_version": self.settings.persona_version,
            "model_name": self.settings.groq_model,
            "prompt_version": self.settings.persona_prompt_version,
            "source_review_ids": source_review_ids,
        }
        self.client.table("user_personas").upsert(payload, on_conflict="user_id,category").execute()

    def regenerate_persona(
        self,
        user_id: str,
        category: str | None = None,
        *,
        max_reviews: int = 20,
        store: bool = True,
    ) -> dict[str, Any]:
        category = category or self.settings.default_category
        persona, stats = self.generate_and_validate(user_id, category, max_reviews=max_reviews)
        if store:
            self.store_persona(user_id, category, persona, stats["source_review_ids"])
        return {
            "user_id": user_id,
            "category": category,
            "persona": persona,
            "source_review_ids": stats["source_review_ids"],
        }
