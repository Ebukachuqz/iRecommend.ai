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

## Reranking

The LLM reranker receives only scored candidates and must not invent product facts or recommend products outside the candidate set. If the LLM call or parser fails, a deterministic score-based fallback is used and the fallback event is logged.
