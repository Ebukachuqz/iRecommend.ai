from __future__ import annotations

from typing import Any


def stringify(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, list):
        return "; ".join(stringify(item) for item in value if stringify(item))
    if isinstance(value, dict):
        return "; ".join(f"{key}: {stringify(item)}" for key, item in value.items() if stringify(item))
    return str(value)


def build_product_text(product: dict[str, Any]) -> str:
    sections = [
        ("Title", product.get("title")),
        ("Main Category", product.get("main_category")),
        ("Category Path", product.get("categories") or product.get("category")),
        ("Features", product.get("features")),
        ("Description", product.get("description")),
        ("Average Rating", product.get("average_rating")),
        ("Rating Count", product.get("rating_number")),
        ("Price", product.get("price")),
        ("Store", product.get("store")),
        ("Details", product.get("details")),
    ]
    lines = [f"{label}: {stringify(value)}" for label, value in sections if stringify(value)]
    return "\n".join(lines)
