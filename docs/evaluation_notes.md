# Evaluation Notes

Evaluation uses the stored per-user holdout split:

- `persona_train` builds personas and user taste vectors.
- `task_a_holdout` evaluates Task A review/rating simulation.
- `task_b_holdout` evaluates Task B recommendation with positive reviews as hidden liked products.

Category filtering is always done by joining reviews through `amazon_product_metadata.parent_asin`; `amazon_reviews` intentionally has no category column.

Task A evaluation runs the existing simulation service against each selected `task_a_holdout` example and compares predicted ratings with the real rating. It also reports a user-average baseline computed only from that user's `persona_train` reviews.

Task B evaluation runs the existing recommendation service with the category passed explicitly. It excludes `persona_train` products but allows the hidden positive `task_b_holdout` ASIN during evaluation so Hit@K, NDCG@K, and MRR@K are measurable. The required baseline is a simple same-category popularity/quality ranking that excludes `persona_train` products.

Evaluation outputs are file-based under `outputs/evaluation/`: result CSV, result JSON, summary JSON, and an all-category manifest when `scripts/evaluate_all.py` is used.
