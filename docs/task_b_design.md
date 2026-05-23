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

## Retrieval

Candidate retrieval first tries the user's stored taste vector from `user_taste_vectors`. Taste vectors are built only from `amazon_reviews.task_split='persona_train'` liked reviews with rating >= 4, and products already reviewed by the user are always excluded. If no taste vector exists, retrieval falls back to high-quality/popular product metadata.

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

## Reranking

The LLM reranker receives only scored candidates and must not invent product facts or recommend products outside the candidate set. If the LLM call or parser fails, a deterministic score-based fallback is used and the fallback event is logged.
