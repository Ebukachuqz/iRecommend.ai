from __future__ import annotations

import re
from typing import Any


def stringify(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, list):
        return "; ".join(stringify(item) for item in value if stringify(item))
    if isinstance(value, dict):
        return "; ".join(f"{key}: {stringify(item)}" for key, item in value.items() if stringify(item))
    return str(value).strip()


def coerce_list(value: Any) -> list[Any]:
    if value in (None, "", [], {}):
        return []
    return value if isinstance(value, list) else [value]


def get_price_tier(price: Any) -> str | None:
    if price in (None, ""):
        return None
    try:
        numeric_price = float(price)
    except (TypeError, ValueError):
        return None
    if numeric_price < 10:
        return "budget"
    if numeric_price < 30:
        return "mid-range"
    if numeric_price < 75:
        return "premium"
    return "luxury"


def get_category_path(product: dict[str, Any]) -> str:
    categories = product.get("categories") or []
    if categories:
        if isinstance(categories, list) and categories and isinstance(categories[0], list):
            path_values = categories[0]
        else:
            path_values = categories if isinstance(categories, list) else [categories]
        path = " > ".join(str(item).strip() for item in path_values if str(item).strip())
        if path:
            return path
    return str(product.get("main_category") or product.get("category") or "").strip()


def description_excerpt(description: Any, max_parts: int = 3) -> str:
    values = coerce_list(description)
    if not values:
        return ""
    if len(values) == 1:
        sentences = re.split(r"(?<=[.!?])\s+", str(values[0]).strip())
        return " ".join(sentence for sentence in sentences[:max_parts] if sentence)
    return " ".join(str(item).strip() for item in values[:max_parts] if str(item).strip())


def detail_text(details: Any, limit: int = 5) -> str:
    if not isinstance(details, dict):
        return ""
    parts: list[str] = []
    for key, value in list(details.items())[:limit]:
        rendered = stringify(value)
        if key and rendered:
            parts.append(f"{str(key).strip()}: {rendered}")
    return "; ".join(parts)


def is_embeddable(product: dict[str, Any]) -> bool:
    title = str(product.get("title") or "").strip()
    return bool(title and get_category_path(product))


def build_product_text(product: dict[str, Any]) -> str:
    parts: list[str] = []

    title = str(product.get("title") or "").strip()
    if title:
        parts.append(f"Title: {title}")

    category_path = get_category_path(product)
    project_category = str(product.get("category") or "").strip()
    main_category = str(product.get("main_category") or "").strip()
    if project_category:
        parts.append(f"Project category: {project_category}")
    if main_category and main_category != project_category:
        parts.append(f"Main category: {main_category}")
    if category_path:
        parts.append(f"Category path: {category_path}")

    features = [stringify(item) for item in coerce_list(product.get("features"))[:5]]
    features = [item for item in features if item]
    if features:
        parts.append("Features: " + "; ".join(features))

    description = description_excerpt(product.get("description"))
    if description:
        parts.append(f"Description: {description}")

    brand = str(product.get("store") or product.get("brand") or "").strip()
    if brand:
        parts.append(f"Brand: {brand}")

    price_tier = get_price_tier(product.get("price"))
    if price_tier:
        parts.append(f"Price tier: {price_tier}")

    details = detail_text(product.get("details"))
    if details:
        parts.append(f"Details: {details}")

    return "\n".join(parts)
