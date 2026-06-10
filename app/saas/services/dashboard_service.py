from __future__ import annotations

from collections import Counter
from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def clean_label(value: Any) -> str:
    return str(value or "").strip()


def count_items(items: list[Any], limit: int = 5) -> list[dict[str, Any]]:
    counter = Counter(label for item in items if (label := clean_label(item)))
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def get_persona(row: dict[str, Any]) -> dict[str, Any]:
    return as_dict(row.get("persona"))


def get_section(persona: dict[str, Any], name: str) -> dict[str, Any]:
    return as_dict(persona.get(name))


def summarize_customer(row: dict[str, Any]) -> dict[str, Any]:
    persona = get_persona(row)
    preferences = get_section(persona, "preferences")
    rating_behavior = get_section(persona, "rating_behavior")
    purchase_behavior = get_section(persona, "purchase_behavior")
    preferred_categories = [clean_label(item) for item in as_list(purchase_behavior.get("preferred_categories")) if clean_label(item)]
    values = [clean_label(item) for item in as_list(preferences.get("what_they_value")) if clean_label(item)]
    return {
        "customer_id": str(row.get("customer_id") or ""),
        "review_count": int(row.get("review_count") or 0),
        "avg_rating": float(rating_behavior.get("average_rating") or 0.0),
        "strictness": clean_label(rating_behavior.get("strictness")) or "moderate",
        "top_values": values[:3],
        "top_category": preferred_categories[0] if preferred_categories else None,
    }


def build_overview(persona_rows: list[dict[str, Any]], latest_upload: dict[str, Any] | None = None) -> dict[str, Any]:
    strictness_values: list[str] = []
    values: list[str] = []
    complaints: list[str] = []
    categories: list[str] = []
    for row in persona_rows:
        persona = get_persona(row)
        preferences = get_section(persona, "preferences")
        rating_behavior = get_section(persona, "rating_behavior")
        purchase_behavior = get_section(persona, "purchase_behavior")
        if strictness := clean_label(rating_behavior.get("strictness")):
            strictness_values.append(strictness)
        values.extend(as_list(preferences.get("what_they_value")))
        complaints.extend(as_list(preferences.get("common_complaints")))
        categories.extend(as_list(purchase_behavior.get("preferred_categories")))

    strictness_counter = Counter(strictness_values)
    top_values_counts = count_items(values)
    top_complaints_counts = count_items(complaints)
    categories_covered_counts = count_items(categories)
    return {
        "total_personas": len(persona_rows),
        "avg_strictness": strictness_counter.most_common(1)[0][0] if strictness_counter else None,
        "top_values": [item["label"] for item in top_values_counts],
        "top_values_counts": top_values_counts,
        "top_complaints": [item["label"] for item in top_complaints_counts],
        "top_complaints_counts": top_complaints_counts,
        "categories_covered": [item["label"] for item in categories_covered_counts],
        "categories_covered_counts": categories_covered_counts,
        "last_upload_at": (latest_upload or {}).get("completed_at") or (latest_upload or {}).get("created_at"),
    }
