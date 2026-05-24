# Task B Design Notes

Task B recommends products from a user's persona, optional request, product metadata, and pgvector retrieval.

## Workflow

```text
persona + request
-> intent planning
-> candidate retrieval
-> transparent scoring
-> LLM reranking
-> recommendation_runs storage
```

The implementation keeps pgvector behind `VectorStore`, with `SupabasePgVectorStore` as the first backend. Business logic calls the abstraction rather than raw pgvector tables.

Task B can run from a stored user persona or from a caller-provided custom persona. Custom personas are normalized through the same bounded persona normalizer used by Task A, so common fields such as `likes`, `interests`, `avoid`, `concerns`, `budget`, `tone`, and `average_rating` can drive request planning, retrieval, scoring, and reranking. Unknown fields are preserved for inspection rather than silently discarded.

## Retrieval

Candidate retrieval first tries the user's stored taste vector from `user_taste_vectors`. Taste vectors are built only from `amazon_reviews.task_split='persona_train'` liked reviews with rating >= 4, and products already reviewed by the user are always excluded. If no taste vector exists, retrieval falls back to high-quality/popular product metadata.

Taste vectors are category-aware. Reviews are filtered through `amazon_product_metadata` by `parent_asin`, using `category` first and falling back to `main_category`/`categories`, before product embeddings are averaged. This prevents a beauty taste vector from being polluted by books, electronics, or other category histories.

## Product Embeddings

Product embeddings are built from rich metadata rather than title-only text. `product_embeddings.product_text` includes the title, full category path, top product features, the first description entries/sentences, brand/store, a semantic price tier, and useful details. The stored `product_text` is intentionally kept for debugging and reproducibility: it shows exactly what text was embedded for a product.

The embedding text uses price tiers (`budget`, `mid-range`, `premium`, `luxury`) instead of exact prices such as `$18.99`. Exact prices change over time and add little semantic value; price tiers preserve the stable consumer meaning. When the product text strategy changes, run `scripts/embed_products.py --force-reembed` for the affected category or product set so existing vectors match the new text representation.

## Scoring

Scoring is transparent:

```text
0.30 semantic_similarity
+ 0.25 preference_match
+ 0.20 product_quality
+ 0.15 price_fit
+ 0.10 popularity_reliability
```

Each candidate returns matched persona signals, warnings, and component scores before LLM reranking.

The scoring layer also includes a small transparent rule layer for request quality. It normalizes intent attributes such as `suitable_for_dry_skin` into readable phrases like `dry skin`, rewards direct request/product evidence such as dry-skin moisturizers or oil-control cleansers, and applies soft penalties to off-type results such as haircare, nail tools, travel kits, or narrow eye-area products for broad skincare requests. This is intentionally lightweight and inspectable so later solution-paper analysis can explain ranking trade-offs without treating the recommender as a black box.

The custom-persona path is intentionally not a universal schema mapper. It supports common persona-like field variants, requires at least one usable preference, writing, rating, value, budget, or category signal, and returns a clear validation error for empty or meaningless JSON.

## Reranking

The LLM reranker receives only scored candidates and must not invent product facts or recommend products outside the candidate set. If the LLM call or parser fails, a deterministic score-based fallback is used and the fallback event is logged.
