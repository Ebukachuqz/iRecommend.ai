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

The runtime path is now explicit in `src/task_b_recommendation/graph.py` using LangGraph. FastAPI, CLI scripts, and other callers still enter through `service.recommend()`, and the service delegates to the graph runner so public behavior and response models remain stable. The graph nodes wrap the existing business functions rather than reimplementing retrieval, scoring, reranking, or storage.

The implementation keeps pgvector behind `VectorStore`, with `SupabasePgVectorStore` as the first backend. Business logic calls the abstraction rather than raw pgvector tables.

Task B can run from a stored user persona or from a caller-provided custom persona. Custom personas are normalized through the same bounded persona normalizer used by Task A, so common fields such as `likes`, `interests`, `avoid`, `concerns`, `budget`, `tone`, and `average_rating` can drive request planning, retrieval, scoring, and reranking. Unknown fields are preserved for inspection rather than silently discarded.

## Retrieval

Candidate retrieval builds a broad pool before scoring and LLM reranking. It now combines five sources:

- `taste_vector`: pgvector nearest-neighbour search from the user's category-specific taste vector.
- `request_query`: semantic search from the intent planner's retrieval query. This is the main cold-start and custom-persona path.
- `collaborative`: similar users are found through `user_taste_vectors`, then their highly rated `persona_train` products are considered.
- `attribute_match`: product text is matched against persona liked attributes, product types, values, and intent-required attributes.
- `quality_fallback`: highly rated/popular products fill the pool when other sources are sparse.

Collaborative filtering is deliberately only one source among several. The recommender goes beyond "users like you liked this" by using persona values, request intent, metadata semantics, transparent scoring, and LLM reranking together.

Taste vectors are built only from `amazon_reviews.task_split='persona_train'` liked reviews with rating >= 4, and products already reviewed by the user are always excluded. If no taste vector exists, request-query retrieval and quality fallback still work, which keeps cold-start and custom persona flows useful.

Taste vectors are category-aware. Reviews are filtered through `amazon_product_metadata` by `parent_asin`, using `category` first and falling back to `main_category`/`categories`, before product embeddings are averaged. This prevents a beauty taste vector from being polluted by books, electronics, or other category histories.

Every retrieval run records source counts such as `{"taste_vector": 40, "request_query": 30, "attribute_match": 12}` in `recommendation_runs.retrieval_sources`. These counts describe unique candidates added by each source after dedupe, not only the final top recommendations. If a product appears from multiple sources, its `retrieval_sources` list preserves all sources, but only the first source that added the unique candidate increments the run-level count.

## Audit Trail

Task B persists the recommendation pipeline in three linked tables. `recommendation_runs` remains the primary record and stores the final ranked recommendations, request context, source counts, and reproducibility metadata. `intent_plans` stores the agent's structured reasoning brief for the same run, including explicit constraints, persona-derived implicit constraints, retrieval query, required attributes, and avoid lists. `recommendation_candidates` stores one row per scored candidate with retrieval sources, similarity signals, score breakdown, `rank_before_rerank`, and `rank_after_rerank` when the candidate appears in the final LLM-ranked list.

Intent and candidate trace writes are best-effort. If trace persistence fails, recommendation generation still returns the final output and keeps the `recommendation_runs` record as the source of truth. Together these tables provide an audit trail for debugging, ablations, evaluation, and the solution paper.

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
