from __future__ import annotations

import re
from typing import Any

from src.evaluation.utils import CATEGORY_CONTRADICTION_KEYWORDS, word_count

_PRICE_PATTERNS = [
    re.compile(r"\$[\d,]+\.?\d{0,2}"),
    re.compile(r"([\d,]+\.?\d{0,2})\s*dollars", re.IGNORECASE),
]


def _parse_price(text: str) -> float | None:
    for pattern in _PRICE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                raw = match.group(0).replace("$", "").replace(",", "")
                raw = re.sub(r"\s*dollars.*", "", raw, flags=re.IGNORECASE)
                return float(raw)
            except (ValueError, AttributeError):
                return None
    return None


def check_task_a_behaviour(row: dict, product_snapshot: dict) -> dict:
    rating_valid = False
    try:
        r = float(row["predicted_rating"])
        rating_valid = r is not None and 1 <= r <= 5
    except (KeyError, TypeError, ValueError):
        pass

    review_text = row.get("simulated_review_text")
    review_non_empty = isinstance(review_text, str) and word_count(review_text) >= 10

    # Product grounding — soft check only.
    product_grounding_check: bool | None | str = None
    category = product_snapshot.get("category")
    if category is not None and isinstance(review_text, str):
        normalised_cat = category.lower().replace("_", " ").replace("-", " ")
        lower_review = review_text.lower()
        cat_words = normalised_cat.split()
        if any(w in lower_review for w in cat_words):
            product_grounding_check = True
        else:
            contradictions = CATEGORY_CONTRADICTION_KEYWORDS.get(category, [])
            if any(kw in lower_review for kw in contradictions):
                product_grounding_check = "contradiction"

    # Hallucination — price mention vs actual price.
    hallucination_detected = False
    if isinstance(review_text, str):
        try:
            mentioned_price = _parse_price(review_text)
            actual_price = product_snapshot.get("price")
            if mentioned_price is not None and actual_price is not None:
                actual_price = float(actual_price)
                if actual_price > 0:
                    diff = abs(mentioned_price - actual_price)
                    hallucination_detected = diff > 0.5 * actual_price
        except (TypeError, ValueError):
            pass

    behaviour_passed = (
        rating_valid
        and review_non_empty
        and product_grounding_check != "contradiction"
        and not hallucination_detected
    )

    return {
        "rating_valid": rating_valid,
        "review_non_empty": review_non_empty,
        "product_grounding_check": product_grounding_check,
        "hallucination_detected": hallucination_detected,
        "behaviour_passed": behaviour_passed,
    }


def check_task_b_behaviour(row: dict, persona_train_asins: list[str]) -> dict:
    recs = row.get("recommendations")
    output_valid = isinstance(recs, list) and len(recs) > 0

    reviewed_product_recommended: bool | None = None
    if not recs:
        reviewed_product_recommended = None
    else:
        rec_asins = set()
        for r in recs:
            if isinstance(r, dict):
                asin = r.get("parent_asin")
            else:
                asin = r
            if asin:
                rec_asins.add(str(asin))
        train_set = set(str(a) for a in persona_train_asins) if persona_train_asins else set()
        reviewed_product_recommended = bool(rec_asins & train_set) if train_set else None

    behaviour_passed = (
        output_valid
        and reviewed_product_recommended is not True
    )

    return {
        "output_valid": output_valid,
        "reviewed_product_recommended": reviewed_product_recommended,
        "behaviour_passed": behaviour_passed,
    }
