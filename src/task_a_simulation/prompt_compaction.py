from __future__ import annotations

from typing import Any

MAX_FIELD_CHARS = 300
MAX_LIST_ITEMS = 5
MAX_TOTAL_PRODUCT_CHARS = 1500
MAX_TOTAL_PERSONA_CHARS = 2000

PERSONA_KEEP_SECTIONS = {
    "rating_behavior",
    "purchase_behavior",
    "preferences",
    "writing_style",
}


def _truncate_str(value: str, max_chars: int = MAX_FIELD_CHARS) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3] + "..."


def _truncate_list(items: list, max_items: int = MAX_LIST_ITEMS, max_chars: int = MAX_FIELD_CHARS) -> list:
    result = []
    for item in items[:max_items]:
        if isinstance(item, str):
            result.append(_truncate_str(item, max_chars))
        else:
            result.append(item)
    return result


def compact_persona(persona: dict[str, Any], aggressive: bool = False) -> dict[str, Any]:
    max_chars = MAX_FIELD_CHARS // 2 if aggressive else MAX_FIELD_CHARS
    max_items = 3 if aggressive else MAX_LIST_ITEMS

    out: dict[str, Any] = {}

    for section in PERSONA_KEEP_SECTIONS:
        val = persona.get(section)
        if val is None:
            continue
        if isinstance(val, dict):
            compacted = {}
            for k, v in val.items():
                if isinstance(v, str):
                    compacted[k] = _truncate_str(v, max_chars)
                elif isinstance(v, list):
                    compacted[k] = _truncate_list(v, max_items, max_chars)
                else:
                    compacted[k] = v
            out[section] = compacted
        else:
            out[section] = val

    ws = persona.get("writing_style")
    if isinstance(ws, dict) and "writing_style" in out:
        ws_out = out["writing_style"]
        for drop_key in ("vocabulary_markers", "common_phrases"):
            if aggressive and drop_key in ws_out:
                ws_out[drop_key] = ws_out[drop_key][:2]

    cs = persona.get("cultural_signals")
    if cs and not aggressive:
        out["cultural_signals"] = _truncate_str(str(cs), max_chars)

    return out


def compact_product(product_dict: dict[str, Any], aggressive: bool = False) -> dict[str, Any]:
    max_chars = MAX_FIELD_CHARS // 2 if aggressive else MAX_FIELD_CHARS
    max_items = 3 if aggressive else MAX_LIST_ITEMS

    out: dict[str, Any] = {}

    for key in ("parent_asin", "title", "main_category", "average_rating", "rating_number", "price", "store"):
        if key in product_dict:
            val = product_dict[key]
            if isinstance(val, str):
                out[key] = _truncate_str(val, max_chars)
            else:
                out[key] = val

    cat = product_dict.get("category")
    if cat:
        out["category"] = _truncate_str(str(cat), max_chars)

    cats = product_dict.get("categories")
    if isinstance(cats, list):
        out["categories"] = _truncate_list(cats, max_items, max_chars)

    features = product_dict.get("features")
    if isinstance(features, list):
        out["features"] = _truncate_list(features, max_items, max_chars)

    desc = product_dict.get("description")
    if isinstance(desc, list):
        out["description"] = _truncate_list(desc, max_items, max_chars)
    elif isinstance(desc, str):
        out["description"] = _truncate_str(desc, max_chars)

    details = product_dict.get("details")
    if isinstance(details, dict):
        kept = {}
        for k, v in list(details.items())[:max_items]:
            if isinstance(v, str):
                kept[k] = _truncate_str(v, max_chars // 2)
            else:
                kept[k] = v
        out["details"] = kept

    import json
    text = json.dumps(out, ensure_ascii=False)
    if len(text) > MAX_TOTAL_PRODUCT_CHARS:
        for drop in ("details", "description", "categories"):
            if drop in out:
                del out[drop]
            text = json.dumps(out, ensure_ascii=False)
            if len(text) <= MAX_TOTAL_PRODUCT_CHARS:
                break

    return out
