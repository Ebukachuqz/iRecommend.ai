"""
Shared utilities, constants, and database contracts for ``src/evaluation/``.

No other evaluation file should duplicate these definitions.

DATABASE CONTRACTS
==================

amazon_reviews
--------------
  review_id        TEXT
  user_id          TEXT
  parent_asin      TEXT
  rating           FLOAT
  title            TEXT
  text             TEXT
  timestamp        BIGINT
  task_split       TEXT  -- values: 'persona_train', 'task_a_holdout', 'task_b_holdout'

  IMPORTANT:
    - amazon_reviews does NOT have a category column.
      Category must always be resolved by joining to amazon_product_metadata.
    - amazon_reviews does NOT have a legacy persona-source boolean column.
      Review split is controlled by task_split only.
    - Persona source evidence is in user_personas.source_review_ids.

amazon_product_metadata
-----------------------
  parent_asin      TEXT   (PK)
  title            TEXT
  category         TEXT   -- our ingestion label: 'Electronics',
                             'Health_and_Household', or 'Beauty_and_Personal_Care'
  main_category    TEXT   -- Amazon's own label (not our ingestion label)
  categories       JSONB  -- list of related Amazon category strings
  price            FLOAT
  features         JSONB
  description      JSONB
  average_rating   FLOAT
  rating_number    INTEGER
  store            TEXT
  details          JSONB
  images           JSONB  -- optional display image data
  bought_together  JSONB  -- optional related-product retrieval signal

simulation_results
------------------
  id                           UUID
  user_id                      TEXT
  category                     TEXT
  parent_asin                  TEXT
  holdout_review_id            TEXT  -- links to amazon_reviews.review_id
  real_review_text             TEXT
  real_rating                  FLOAT
  llm_predicted_rating         FLOAT
  statistical_predicted_rating FLOAT
  final_predicted_rating       FLOAT
  simulated_review_title       TEXT
  simulated_review_text        TEXT
  confidence                   FLOAT
  model_name                   TEXT
  prompt_version               TEXT
  persona_version              TEXT
  created_at                   TIMESTAMPTZ

user_personas
-------------
  user_id           TEXT
  category          TEXT
  persona           JSONB
  review_count      INTEGER
  persona_version   TEXT
  model_name        TEXT
  prompt_version    TEXT
  source_review_ids JSONB  -- list of review_ids used to build this persona
  PRIMARY KEY: (user_id, category)

recommendation_runs
-------------------
  id                UUID
  user_id           TEXT
  category          TEXT
  candidate_count   INTEGER
  retrieval_sources JSONB
  recommendations   JSONB  -- list of {parent_asin, rank, reason, score_breakdown, ...}
  top_asin          TEXT
  is_evaluation_run BOOLEAN
  holdout_asin      TEXT
  hit_at_10         BOOLEAN
  rank_of_holdout   INTEGER
  model_name        TEXT
  prompt_version    TEXT
  embedding_model   TEXT
  created_at        TIMESTAMPTZ

intent_plans
------------
  id                     UUID
  recommendation_run_id  UUID
  session_id             TEXT
  user_id                TEXT
  category               TEXT
  raw_request            TEXT
  interpreted_need       TEXT
  explicit_constraints   JSONB
  implicit_constraints   JSONB
  retrieval_query        TEXT
  avoid                  JSONB
  category_filter        TEXT
  price_max              FLOAT
  required_attributes    JSONB
  excluded_attributes    JSONB
  model_name             TEXT
  prompt_version         TEXT
  created_at             TIMESTAMPTZ

recommendation_candidates (may not exist in all deployments)
------------------------------------------------------------
  id                       UUID
  recommendation_run_id    UUID
  parent_asin              TEXT
  retrieval_source         TEXT
  semantic_similarity      FLOAT
  collaborative_similarity FLOAT
  preference_match         FLOAT
  product_quality          FLOAT
  price_fit                FLOAT
  popularity_reliability   FLOAT
  final_score              FLOAT
  score_breakdown          JSONB
  rank_before_rerank       INTEGER
  rank_after_rerank        INTEGER
  created_at               TIMESTAMPTZ

  NOTE: This table may not exist in all deployments.
        Every query against it must be wrapped in try/except.
        On exception: treat the result as unavailable (None),
        log a warning once, and continue. Never crash because
        this table is absent.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES: list[str] = [
    "Electronics",
    "Health_and_Household",
    "Beauty_and_Personal_Care",
]

DEFAULT_K: int = 10

CATEGORY_CONTRADICTION_KEYWORDS: dict[str, list[str]] = {
    "Electronics": [
        "moisturiser", "moisturizer", "lotion", "serum", "shampoo",
        "conditioner", "skincare", "fragrance", "perfume", "cream",
        "facewash", "face wash", "toner", "exfoliant", "sunscreen",
    ],
    "Health_and_Household": [
        "circuit", "processor", "ram", "gpu", "hdmi", "motherboard",
        "graphics card", "cpu", "ssd", "hard drive",
    ],
    "Beauty_and_Personal_Care": [
        "circuit", "processor", "motherboard", "gpu", "hdmi",
        "usb", "wattage", "voltage", "amp", "ohm",
    ],
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_REVIEW_LENGTH_MAP: dict[str, int] = {"short": 50, "medium": 120, "long": 250}

_FILTER_OPERATORS: set[str] = {"eq", "neq", "gte", "lte", "in_", "not_in"}


def _apply_filter(query: Any, column: str, operator: str, value: Any) -> Any:
    """Apply a single filter to a Supabase query builder."""
    if operator not in _FILTER_OPERATORS:
        raise ValueError(f"Unsupported filter operator: {operator!r}")
    if operator == "not_in":
        return query.not_.in_(column, value)
    method = getattr(query, operator)
    return method(column, value)


# ---------------------------------------------------------------------------
# Supabase pagination
# ---------------------------------------------------------------------------


def fetch_all_paginated(
    supabase_client: Any,
    table: str,
    select: str = "*",
    filters: list[tuple] | None = None,
    page_size: int = 500,
) -> list[dict]:
    """Fetch all rows from *table* using offset-based pagination.

    Parameters
    ----------
    supabase_client:
        An initialised Supabase ``Client``.
    table:
        Supabase table name.
    select:
        Column selection string (default ``"*"``).
    filters:
        Optional list of ``(column, operator, value)`` tuples.
        Supported operators: ``eq``, ``neq``, ``gte``, ``lte``,
        ``in_``, ``not_in``.
    page_size:
        Number of rows per request (default 500).

    Returns
    -------
    list[dict]
        Flat list of all matching rows.
    """
    rows: list[dict] = []
    offset = 0

    while True:
        query = supabase_client.table(table).select(select)
        if filters:
            for column, operator, value in filters:
                query = _apply_filter(query, column, operator, value)
        query = query.range(offset, offset + page_size - 1)
        response = query.execute()
        data: list[dict] = response.data or []
        rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size

    return rows


# ---------------------------------------------------------------------------
# Category resolution
# ---------------------------------------------------------------------------

_IN_CHUNK_SIZE: int = 500


def resolve_category_for_reviews(
    reviews: list[dict],
    supabase_client: Any,
) -> list[dict]:
    """Add a ``category`` key to each review by joining to product metadata.

    Fetches ``amazon_product_metadata`` rows for all unique ``parent_asin``
    values found in *reviews* and attaches the resolved ``category``
    (our ingestion label) to each review dict **in-place**.

    If no matching metadata row exists for a ``parent_asin``, the review's
    ``category`` is set to ``None`` and a warning is logged **once per
    missing ASIN** (not once per review).

    Returns
    -------
    list[dict]
        The same *reviews* list, mutated with ``category`` added.
    """
    if not reviews:
        return reviews

    # Collect unique parent_asins.
    unique_asins: list[str] = list(
        {r["parent_asin"] for r in reviews if r.get("parent_asin")}
    )

    # Batch-fetch metadata, chunking the IN clause for safety.
    metadata_map: dict[str, str | None] = {}
    for start in range(0, len(unique_asins), _IN_CHUNK_SIZE):
        chunk = unique_asins[start : start + _IN_CHUNK_SIZE]
        rows = fetch_all_paginated(
            supabase_client,
            "amazon_product_metadata",
            select="parent_asin,category",
            filters=[("parent_asin", "in_", chunk)],
        )
        for row in rows:
            metadata_map[row["parent_asin"]] = row.get("category")

    # Attach category; warn once per missing ASIN.
    warned_asins: set[str] = set()
    for review in reviews:
        asin = review.get("parent_asin")
        if asin and asin in metadata_map:
            review["category"] = metadata_map[asin]
        else:
            review["category"] = None
            if asin and asin not in warned_asins:
                logger.warning(
                    "No metadata found for parent_asin %s — category set to None",
                    asin,
                )
                warned_asins.add(asin)

    return reviews


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------


def _serialise_for_csv(value: Any) -> Any:
    """Convert list or dict values to JSON strings for CSV columns."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=str)
    return value


def write_evaluation_outputs(
    rows: list[dict],
    summary: dict,
    csv_path: str,
    json_path: str,
    summary_path: str,
) -> None:
    """Write evaluation results to CSV, JSON-rows, and JSON-summary files.

    1. Creates parent directories if they do not exist.
    2. Serialises ``list`` and ``dict`` fields to JSON strings for CSV output
       only.  JSON output preserves the original Python types.
    3. Writes CSV using ``pandas.DataFrame.to_csv(index=False)``.
    4. Writes JSON rows using ``json.dumps(rows, indent=2, default=str)``.
    5. Writes JSON summary using ``json.dumps(summary, indent=2, default=str)``.
    """
    for path_str in (csv_path, json_path, summary_path):
        Path(path_str).parent.mkdir(parents=True, exist_ok=True)

    # CSV — serialise complex fields.
    csv_rows = [{k: _serialise_for_csv(v) for k, v in row.items()} for row in rows]
    df = pd.DataFrame(csv_rows)
    df.to_csv(csv_path, index=False)

    # JSON rows — preserve original types.
    Path(json_path).write_text(
        json.dumps(rows, indent=2, default=str), encoding="utf-8",
    )

    # JSON summary.
    Path(summary_path).write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Persona helpers
# ---------------------------------------------------------------------------


def get_user_typical_review_length(persona: dict) -> int:
    """Return the expected review word count from the persona's writing style.

    Mapping:
        ``"short"`` → 50, ``"medium"`` → 120, ``"long"`` → 250.

    Returns ``120`` if the field is missing or contains an unrecognised value.
    """
    try:
        length = persona["writing_style"]["length"]
    except (KeyError, TypeError):
        return 120
    return _REVIEW_LENGTH_MAP.get(length, 120)


def get_user_average_rating(persona: dict) -> float:
    """Return the user's average rating from the persona.

    Returns ``3.0`` if the field is missing or not a valid number.
    """
    try:
        return float(persona["rating_behavior"]["average_rating"])
    except (KeyError, TypeError, ValueError):
        return 3.0


# ---------------------------------------------------------------------------
# Word count
# ---------------------------------------------------------------------------


def word_count(text: str) -> int:
    """Return the number of whitespace-delimited words in *text*.

    Returns ``0`` for ``None``, empty strings, or non-string values.
    """
    if not text or not isinstance(text, str):
        return 0
    return len(text.split())
