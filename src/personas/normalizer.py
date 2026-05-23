from __future__ import annotations

from typing import Any

from src.personas.validator import repair_persona_payload


MINIMUM_PERSONA_ERROR = (
    "Custom persona must include at least one usable signal such as likes, dislikes, interests, "
    "concerns, values, preferred categories, tone, average rating, budget, or rating style."
)

STRICTNESS_VALUES = {"strict", "moderate", "generous"}
LENGTH_VALUES = {"short", "medium", "long"}
DETAIL_VALUES = {"low", "medium", "high"}
FORMALITY_VALUES = {"casual", "mixed", "formal"}
SENSITIVITY_WITH_UNKNOWN = {"low", "medium", "high", "unknown"}
QUALITY_VALUES = {"low", "medium", "high"}


def coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item).strip()]
    return [str(value)]


def normalize_enum(value: Any, allowed: set[str], default: str) -> str:
    candidate = str(value or "").strip().lower().replace("_", " ")
    return candidate if candidate in allowed else default


def normalize_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(5.0, number))


def pop_first(raw: dict[str, Any], keys: list[str]) -> tuple[Any, str | None]:
    for key in keys:
        if key in raw and raw[key] not in (None, "", []):
            return raw[key], key
    return None, None


def normalize_custom_persona(raw_persona: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_persona, dict):
        raise ValueError("Custom persona must be a JSON object.")

    known_top_level = {
        "writing_style",
        "preferences",
        "rating_behavior",
        "purchase_behavior",
        "cultural_signals",
        "evidence",
        "extra_persona_signals",
    }
    working = dict(raw_persona)
    base = repair_persona_payload({key: value for key, value in working.items() if key in known_top_level})
    notes: list[str] = []
    mapped_keys: set[str] = set(key for key in working if key in known_top_level)

    preferences = dict(base.get("preferences") or {})
    writing_style = dict(base.get("writing_style") or {})
    rating_behavior = dict(base.get("rating_behavior") or {})
    purchase_behavior = dict(base.get("purchase_behavior") or {})
    extra = dict(base.get("extra_persona_signals") or {})

    mappings = [
        (["likes", "interests"], "liked_attributes", "mapped likes/interests to liked_attributes"),
        (["preferred_products"], "liked_product_types", "mapped preferred_products to liked_product_types"),
        (["dislikes", "avoid"], "disliked_attributes", "mapped dislikes/avoid to disliked_attributes"),
        (["concerns"], "common_complaints", "mapped concerns to common_complaints"),
        (["values", "priorities"], "what_they_value", "mapped values/priorities to what_they_value"),
    ]
    for keys, target, note in mappings:
        combined: list[str] = list(preferences.get(target) or [])
        used = False
        for key in keys:
            if key in working:
                combined.extend(coerce_string_list(working[key]))
                mapped_keys.add(key)
                used = True
        if used:
            preferences[target] = coerce_string_list(combined)
            notes.append(note)

    categories, key = pop_first(working, ["preferred_categories", "categories"])
    if key:
        purchase_behavior["preferred_categories"] = coerce_string_list(categories)
        mapped_keys.add(key)
        notes.append(f"mapped {key} to preferred_categories")

    tone, key = pop_first(working, ["tone", "writing_tone", "voice"])
    if key:
        writing_style["tone"] = str(tone)
        mapped_keys.add(key)
        notes.append(f"mapped {key} to writing_style.tone")

    length, key = pop_first(working, ["review_length", "length"])
    if key:
        writing_style["length"] = normalize_enum(length, LENGTH_VALUES, "medium")
        mapped_keys.add(key)
        notes.append(f"mapped {key} to writing_style.length")

    for source, target, allowed, default in [
        ("detail_level", "detail_level", DETAIL_VALUES, "medium"),
        ("formality", "formality", FORMALITY_VALUES, "mixed"),
    ]:
        if source in working:
            writing_style[target] = normalize_enum(working[source], allowed, default)
            mapped_keys.add(source)
            notes.append(f"mapped {source} to writing_style.{target}")

    average, key = pop_first(working, ["average_rating", "avg_rating"])
    if key:
        rating_behavior["average_rating"] = normalize_float(average)
        mapped_keys.add(key)
        notes.append(f"mapped {key} to rating_behavior.average_rating")

    strictness, key = pop_first(working, ["strictness", "rating_style"])
    if key:
        rating_behavior["strictness"] = normalize_enum(strictness, STRICTNESS_VALUES, "moderate")
        rating_behavior["rating_patterns"] = str(strictness)
        mapped_keys.add(key)
        notes.append(f"mapped {key} to rating_behavior")

    price, key = pop_first(working, ["price_sensitivity", "budget"])
    if key:
        purchase_behavior["price_sensitivity"] = normalize_enum(price, SENSITIVITY_WITH_UNKNOWN, "unknown")
        mapped_keys.add(key)
        notes.append(f"mapped {key} to purchase_behavior.price_sensitivity")

    if "quality_sensitivity" in working:
        purchase_behavior["quality_sensitivity"] = normalize_enum(working["quality_sensitivity"], QUALITY_VALUES, "medium")
        mapped_keys.add("quality_sensitivity")
        notes.append("mapped quality_sensitivity to purchase_behavior.quality_sensitivity")

    unmapped = {key: value for key, value in working.items() if key not in mapped_keys}
    extra["raw_custom_persona"] = raw_persona
    extra["normalization_notes"] = notes
    extra["unmapped_fields"] = unmapped

    normalized = {
        **base,
        "writing_style": writing_style,
        "preferences": preferences,
        "rating_behavior": rating_behavior,
        "purchase_behavior": purchase_behavior,
        "extra_persona_signals": extra,
    }
    validate_custom_persona_minimum(normalized)
    return normalized


def validate_custom_persona_minimum(normalized_persona: dict[str, Any]) -> None:
    preferences = normalized_persona.get("preferences") or {}
    writing_style = normalized_persona.get("writing_style") or {}
    rating_behavior = normalized_persona.get("rating_behavior") or {}
    purchase_behavior = normalized_persona.get("purchase_behavior") or {}
    notes = (normalized_persona.get("extra_persona_signals") or {}).get("normalization_notes") or []

    signals = [
        preferences.get("liked_product_types"),
        preferences.get("liked_attributes"),
        preferences.get("what_they_value"),
        preferences.get("disliked_attributes"),
        preferences.get("common_complaints"),
        purchase_behavior.get("preferred_categories"),
        writing_style.get("tone") if writing_style.get("tone") != "unknown" else None,
        rating_behavior.get("average_rating") if rating_behavior.get("average_rating") else None,
        rating_behavior.get("rating_patterns") if rating_behavior.get("rating_patterns") != "unknown" else None,
        purchase_behavior.get("price_sensitivity") if purchase_behavior.get("price_sensitivity") != "unknown" else None,
        "quality_sensitivity" if any("quality_sensitivity" in str(note) for note in notes) else None,
    ]
    if not any(bool(signal) for signal in signals):
        raise ValueError(MINIMUM_PERSONA_ERROR)
