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
from src.llm.parsers import parse_json_from_llm_text
from src.personas.prompts import PERSONA_PROMPT, PERSONA_SCHEMA_EXAMPLE, PERSONA_SYSTEM_INSTRUCTIONS
from src.personas.validator import persona_to_storage_dict, validate_persona
from src.task_b_recommendation.preference_vector import product_matches_category


def log_persona_generation(message: str) -> None:
    print(f"[persona] {message}")


DEFAULT_MAX_REVIEWS_PER_PERSONA = 10


def has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


class PersonaGenerator:
    def __init__(self, client: Client | None = None) -> None:
        self.settings = get_settings()
        self.client = client or get_supabase_client()

    def fetch_user_reviews(self, user_id: str) -> list[dict[str, Any]]:
        response = (
            self.client.table("amazon_reviews")
            .select("*")
            .eq("user_id", user_id)
            .eq("task_split", PERSONA_TRAIN_SPLIT)
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

    def filter_enriched_reviews_by_category(
        self,
        reviews: list[dict[str, Any]],
        category: str | None,
    ) -> list[dict[str, Any]]:
        if not category:
            return reviews
        return [
            review
            for review in reviews
            if product_matches_category(review.get("product") or {}, category)
        ]

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
            "eligible_review_count": len(reviews),
            "average_rating": round(mean(ratings), 3) if ratings else 0.0,
            "rating_distribution": {str(key): distribution.get(str(key), 0) for key in range(1, 6)},
            "verified_purchase_ratio": round(sum(verified_values) / len(verified_values), 3)
            if verified_values
            else 0.0,
        }

    def select_prompt_reviews(self, reviews: list[dict[str, Any]], max_reviews: int) -> list[dict[str, Any]]:
        with_metadata = [
            review
            for review in reviews
            if has_text(review.get("title"))
            and has_text(review.get("text"))
            and bool(review.get("product"))
        ]
        with_review_text = [
            review
            for review in reviews
            if has_text(review.get("title")) and has_text(review.get("text"))
        ]
        pool = with_metadata or with_review_text or reviews
        return pool[-max_reviews:]

    def format_review_context(self, reviews: list[dict[str, Any]], max_reviews: int = DEFAULT_MAX_REVIEWS_PER_PERSONA) -> tuple[str, list[str]]:
        selected = self.select_prompt_reviews(reviews, max_reviews)
        selected_review_ids = [review["review_id"] for review in selected]
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
        return "\n\n---\n\n".join(blocks), selected_review_ids

    def build_prompt_stats(
        self,
        reviews: list[dict[str, Any]],
        enriched_reviews: list[dict[str, Any]],
        max_reviews: int,
    ) -> tuple[str, dict[str, Any]]:
        review_context, selected_review_ids = self.format_review_context(
            enriched_reviews,
            max_reviews=max_reviews,
        )
        stats = self.compute_user_stats(reviews)
        stats["review_count_available"] = len(reviews)
        stats["review_count_used"] = len(selected_review_ids)
        stats["prompt_review_count"] = len(selected_review_ids)
        stats["source_review_ids"] = selected_review_ids
        return review_context, stats

    def generate_persona_payload(
        self,
        user_id: str,
        category: str | None = None,
        *,
        max_reviews: int = DEFAULT_MAX_REVIEWS_PER_PERSONA,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        category = category or self.settings.default_category
        log_persona_generation(f"Fetching persona_train reviews: user_id={user_id}, category={category}")
        reviews = self.fetch_user_reviews(user_id)
        if not reviews:
            raise ValueError(f"No persona_train reviews found for user_id={user_id!r}, category={category!r}.")

        log_persona_generation(f"Fetched {len(reviews):,} persona_train reviews for user_id={user_id}")
        enriched_reviews = self.enrich_reviews(reviews)
        enriched_reviews = self.filter_enriched_reviews_by_category(enriched_reviews, category)
        if not enriched_reviews:
            raise ValueError(f"No persona_train reviews found for user_id={user_id!r}, category={category!r}.")
        reviews = [{key: value for key, value in review.items() if key != "product"} for review in enriched_reviews]
        review_context, stats = self.build_prompt_stats(reviews, enriched_reviews, max_reviews)
        log_persona_generation(
            "Prepared LLM prompt context: "
            f"user_id={user_id}, source_reviews={stats['review_count']:,}, "
            f"prompt_reviews={stats['prompt_review_count']:,}"
        )
        prompt_input = {
            "instructions": PERSONA_SYSTEM_INSTRUCTIONS,
            "category": category,
            "user_stats": json.dumps(stats, indent=2),
            "review_context": review_context,
            "schema_example": json.dumps(PERSONA_SCHEMA_EXAMPLE, indent=2),
        }
        llm = get_groq_chat(self.settings.groq_model)
        chain = PERSONA_PROMPT | llm
        log_persona_generation(
            f"Calling LLM for persona: user_id={user_id}, model={self.settings.groq_model}"
        )
        raw_message = chain.invoke(prompt_input)
        raw_text = getattr(raw_message, "content", str(raw_message))
        raw_payload, cleaned_json_text = parse_json_from_llm_text(raw_text)
        log_persona_generation(f"LLM persona response parsed: user_id={user_id}")
        log_llm_response(
            "persona_generation",
            {
                "user_id": user_id,
                "category": category,
                "model_name": self.settings.groq_model,
                "prompt_version": self.settings.persona_prompt_version,
                "raw_text": raw_text,
                "cleaned_json_text": cleaned_json_text,
                "parsed_payload": raw_payload,
            },
        )
        return raw_payload, stats

    def generate_and_validate(
        self,
        user_id: str,
        category: str | None = None,
        *,
        max_reviews: int = DEFAULT_MAX_REVIEWS_PER_PERSONA,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raw_payload, stats = self.generate_persona_payload(user_id, category, max_reviews=max_reviews)
        log_persona_generation(f"Validating persona payload: user_id={user_id}")
        persona = validate_persona(raw_payload, repair=True)
        log_persona_generation(f"Persona validation complete: user_id={user_id}")
        return persona_to_storage_dict(persona), stats

    def store_persona(
        self,
        user_id: str,
        category: str,
        persona: dict[str, Any],
        stats: dict[str, Any],
    ) -> None:
        payload = {
            "user_id": user_id,
            "category": category,
            "persona": persona,
            "persona_version": self.settings.persona_version,
            "model_name": self.settings.groq_model,
            "prompt_version": self.settings.persona_prompt_version,
            "review_count": stats["review_count"],
            "average_rating": stats["average_rating"],
            "source_review_ids": stats["source_review_ids"],
        }
        log_persona_generation(
            "Upserting persona: "
            f"user_id={user_id}, category={category}, source_reviews={len(stats['source_review_ids']):,}"
        )
        self.client.table("user_personas").upsert(payload, on_conflict="user_id,category").execute()
        log_persona_generation(f"Persona upsert complete: user_id={user_id}, category={category}")

    def regenerate_persona(
        self,
        user_id: str,
        category: str | None = None,
        *,
        max_reviews: int = DEFAULT_MAX_REVIEWS_PER_PERSONA,
        store: bool = True,
    ) -> dict[str, Any]:
        category = category or self.settings.default_category
        log_persona_generation(f"Regenerating persona: user_id={user_id}, category={category}, store={store}")
        persona, stats = self.generate_and_validate(user_id, category, max_reviews=max_reviews)
        if store:
            self.store_persona(user_id, category, persona, stats)
        else:
            log_persona_generation(f"Store disabled; persona not upserted: user_id={user_id}")
        log_persona_generation(
            f"Persona regeneration complete: user_id={user_id}, source_reviews={len(stats['source_review_ids']):,}"
        )
        return {
            "user_id": user_id,
            "category": category,
            "persona": persona,
            "source_review_ids": stats["source_review_ids"],
            "review_count_available": stats.get("review_count_available", len(stats["source_review_ids"])),
            "review_count_used": stats.get("review_count_used", len(stats["source_review_ids"])),
        }
