from __future__ import annotations

import math
from statistics import mean
from typing import Any


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_metric(value: float | None, digits: int = 4) -> float | None:
    return round(float(value), digits) if value is not None else None


def clamp_rating(value: float) -> float:
    return max(1.0, min(5.0, float(value)))


def rounded_rating(value: float) -> int:
    return int(math.floor(clamp_rating(value) + 0.5))


def mae(pairs: list[tuple[float, float]]) -> float | None:
    if not pairs:
        return None
    return mean(abs(predicted - actual) for predicted, actual in pairs)


def rmse(pairs: list[tuple[float, float]]) -> float | None:
    if not pairs:
        return None
    return math.sqrt(mean((predicted - actual) ** 2 for predicted, actual in pairs))


def exact_rating_accuracy(pairs: list[tuple[float, float]]) -> float | None:
    if not pairs:
        return None
    return mean(rounded_rating(predicted) == rounded_rating(actual) for predicted, actual in pairs)


def within_1_star_accuracy(pairs: list[tuple[float, float]]) -> float | None:
    if not pairs:
        return None
    return mean(abs(predicted - actual) <= 1.0 for predicted, actual in pairs)


def rank_of_item(items: list[str], target: str, k: int) -> int | None:
    for index, item in enumerate(items[:k], start=1):
        if item == target:
            return index
    return None


def hit_at_k(rank: int | None) -> bool:
    return rank is not None


def ndcg_at_k(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / math.log2(rank + 1)


def reciprocal_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / rank


def summarize_rating_rows(rows: list[dict[str, Any]], prefix: str = "") -> dict[str, Any]:
    predicted_key = f"{prefix}predicted_rating" if prefix else "predicted_rating"
    true_key = "true_rating"
    pairs = [
        (float(row[predicted_key]), float(row[true_key]))
        for row in rows
        if row.get(predicted_key) is not None and row.get(true_key) is not None
    ]
    return {
        f"{prefix}mae": round_metric(mae(pairs)),
        f"{prefix}rmse": round_metric(rmse(pairs)),
        f"{prefix}exact_rating_accuracy": round_metric(exact_rating_accuracy(pairs)),
        f"{prefix}within_1_star_accuracy": round_metric(within_1_star_accuracy(pairs)),
    }


def summarize_ranking_rows(rows: list[dict[str, Any]], prefix: str = "") -> dict[str, Any]:
    hit_key = f"{prefix}hit_at_k" if prefix else "hit_at_k"
    rank_key = f"{prefix}rank_of_holdout" if prefix else "rank_of_holdout"
    ndcg_key = f"{prefix}ndcg_at_k" if prefix else "ndcg_at_k"
    rr_key = f"{prefix}reciprocal_rank" if prefix else "reciprocal_rank"
    if not rows:
        return {
            f"{prefix}hit_rate_at_k": None,
            f"{prefix}ndcg_at_k": None,
            f"{prefix}mrr_at_k": None,
            f"{prefix}mean_rank_of_holdout": None,
            f"{prefix}count_hits": 0,
        }
    hits = [bool(row.get(hit_key)) for row in rows]
    found_ranks = [int(row[rank_key]) for row in rows if row.get(rank_key) is not None]
    return {
        f"{prefix}hit_rate_at_k": round_metric(mean(hits)),
        f"{prefix}ndcg_at_k": round_metric(mean(float(row.get(ndcg_key) or 0.0) for row in rows)),
        f"{prefix}mrr_at_k": round_metric(mean(float(row.get(rr_key) or 0.0) for row in rows)),
        f"{prefix}mean_rank_of_holdout": round_metric(mean(found_ranks)) if found_ranks else None,
        f"{prefix}count_hits": sum(1 for item in hits if item),
    }
