from __future__ import annotations

from typing import Any


MINIMUM_PRODUCT_ERROR = "Custom product must include at least a title/name/product_name or description/features."


def coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_value(raw: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if raw.get(key) not in (None, "", []):
            return raw[key]
    return None


def normalize_custom_product(raw_product: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_product, dict):
        raise ValueError("Custom product must be a JSON object.")

    title = first_value(raw_product, ["title", "name", "product_name"])
    category = first_value(raw_product, ["main_category", "category"])
    categories = raw_product.get("categories")
    if categories is None and category is not None:
        categories = [category]

    known = {
        "parent_asin",
        "title",
        "name",
        "product_name",
        "main_category",
        "category",
        "categories",
        "price",
        "features",
        "description",
        "average_rating",
        "rating",
        "rating_number",
        "reviews_count",
        "store",
        "brand",
        "details",
    }
    details = raw_product.get("details") if isinstance(raw_product.get("details"), dict) else {}
    details = dict(details)
    if raw_product.get("brand") and not raw_product.get("store"):
        details["brand"] = raw_product["brand"]
    custom_fields = {key: value for key, value in raw_product.items() if key not in known}
    if custom_fields:
        details["custom_fields"] = custom_fields

    normalized = {
        "parent_asin": str(raw_product.get("parent_asin") or "custom_product"),
        "title": str(title) if title is not None else None,
        "main_category": str(category) if category is not None else None,
        "categories": coerce_list(categories),
        "price": coerce_float(raw_product.get("price")),
        "features": coerce_list(raw_product.get("features")),
        "description": coerce_list(raw_product.get("description")),
        "average_rating": coerce_float(first_value(raw_product, ["average_rating", "rating"])),
        "rating_number": coerce_int(first_value(raw_product, ["rating_number", "reviews_count"])),
        "store": raw_product.get("store") or raw_product.get("brand"),
        "details": details,
    }
    validate_custom_product_minimum(normalized)
    return normalized


def validate_custom_product_minimum(normalized_product: dict[str, Any]) -> None:
    if normalized_product.get("title"):
        return
    if normalized_product.get("description") or normalized_product.get("features"):
        return
    raise ValueError(MINIMUM_PRODUCT_ERROR)
