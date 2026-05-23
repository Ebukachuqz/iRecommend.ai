# Task A Design Notes

Task A simulates how a specific user would rate and review a product. It combines:

- persona-aware statistical rating prediction
- LLM review and rating generation
- distribution-aware rating calibration
- storage in `simulation_results`

## Workflow

```text
fetch_persona_and_product
-> statistical_rating_prediction
-> llm_review_and_rating_generation
-> rating_calibration
-> output_validation
-> store_simulation_result
```

`amazon_reviews` is never filtered by category. Holdout evaluation uses `task_split='task_a_holdout'`; persona generation and Task A both treat `task_split` as the review split source of truth.

Task A also supports the hackathon contract directly: a caller can provide a custom persona JSON object and a custom product JSON object without a Supabase user/product row. The backend normalizes common persona fields such as `likes`, `dislikes`, `budget`, `tone`, and `average_rating`, and common product fields such as `name`, `category`, `rating`, and `reviews_count`. Unknown persona fields are preserved under `extra_persona_signals.unmapped_fields`; unknown product fields are preserved under `details.custom_fields`.

This custom path is intentionally bounded. It accepts flexible-but-reasonable JSON, fills safe defaults, and rejects inputs that contain no usable user or product signal. It does not claim to understand every arbitrary schema.

## Rating

The statistical predictor starts from the user's historical average, blends in product average rating when available, rewards liked attribute matches, penalizes disliked attributes and complaint matches, applies price/quality sensitivity, and adjusts for strictness.

Calibration blends `0.45` statistical rating, `0.35` LLM rating, and `0.20` user average. It then pulls unusually high ratings toward the user's mean, avoids easy 5-star ratings for strict users, and clamps the final result to `1..5`.

## Nigerian Context

`nigerian_mode=True` adds practical Nigerian shopping-context concerns only when relevant: affordability, value for money, durability, delivery/packaging, authenticity risk, and hot or humid weather fit for beauty/skincare items. It does not force slang, Pidgin, or demographic identity.
