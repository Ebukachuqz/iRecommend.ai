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

## Rating

The statistical predictor starts from the user's historical average, blends in product average rating when available, rewards liked attribute matches, penalizes disliked attributes and complaint matches, applies price/quality sensitivity, and adjusts for strictness.

Calibration blends `0.45` statistical rating, `0.35` LLM rating, and `0.20` user average. It then pulls unusually high ratings toward the user's mean, avoids easy 5-star ratings for strict users, and clamps the final result to `1..5`.

## Nigerian Context

`nigerian_mode=True` adds practical Nigerian shopping-context concerns only when relevant: affordability, value for money, durability, delivery/packaging, authenticity risk, and hot or humid weather fit for beauty/skincare items. It does not force slang, Pidgin, or demographic identity.
