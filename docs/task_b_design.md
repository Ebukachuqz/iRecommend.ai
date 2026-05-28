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

Candidate retrieval builds a broad pool before scoring and LLM reranking. It now combines six normal runtime sources:

- `preference_vector`: pgvector nearest-neighbour search from the user's category-specific preference vector.
- `request_query`: semantic search from the intent planner's retrieval query. This is the main cold-start and custom-persona path.
- `collaborative`: similar users are found through `user_preference_vectors`, then their highly rated `persona_train` products are considered.
- `bought_together`: products listed in `amazon_product_metadata.bought_together` for the user's liked `persona_train` products are considered as related-product candidates.
- `attribute_match`: product text is matched against persona liked attributes, product types, values, and intent-required attributes.
- `quality_fallback`: highly rated/popular products fill the pool when other sources are sparse.

Evaluation runs can add one extra source, `evaluation_holdout`. This is not a normal recommendation source. When `evaluation_mode` is active and a hidden positive `task_b_holdout` ASIN is provided, the graph fetches that product from `amazon_product_metadata`, verifies it belongs to the requested broad `category`, verifies it is not part of the persona-train exclusion set, and adds it to the candidate pool only if it was not already retrieved. It receives no artificial semantic similarity or score boost; scoring and LLM reranking decide whether it appears in the final top-K. This makes Hit@K, NDCG@K, and MRR@K valid by ensuring the held-out target was eligible to be ranked and visible in `recommendation_candidates`.

Collaborative filtering is deliberately only one source among several. The recommender goes beyond "users like you liked this" by using persona values, request intent, metadata semantics, transparent scoring, and LLM reranking together.

Preference vectors are built only from `amazon_reviews.task_split='persona_train'` liked reviews with rating >= 4, and excluded products are removed before retrieval. Normal recommendation runs exclude already reviewed products in the requested project category plus products already shown in the current session. Evaluation-mode runs exclude `persona_train` products while keeping `task_b_holdout` products eligible so Hit@K, NDCG@K, and MRR@K can be computed. If a provided holdout ASIN was not retrieved naturally, `evaluation_holdout` adds it as an ordinary candidate with source provenance but no score advantage. If no preference vector exists, request-query retrieval and quality fallback still work, which keeps cold-start and custom persona flows useful.

Preference vectors are category-aware. Reviews are filtered through `amazon_product_metadata` by `parent_asin`, using the project-controlled `category` column before product embeddings are averaged. `main_category` and `categories` are kept as semantic product signals, not broad operational filters. This prevents a beauty preference vector from being polluted by books, electronics, or other category histories.

Session state now contributes an additional exclusion set. Products already shown in the active session are combined with reviewed products and passed into every retrieval source as excluded parent ASINs. Retrieval is extended rather than rewritten: preference-vector search, request-query search, collaborative retrieval, bought-together retrieval, attribute matching, and quality fallback all keep their existing source labels and provenance.

Every retrieval run records source counts such as `{"preference_vector": 40, "request_query": 30, "attribute_match": 12}` in `recommendation_runs.retrieval_sources`. These counts describe unique candidates added by each source after dedupe, not only the final top recommendations. If a product appears from multiple sources, its `retrieval_sources` list preserves all sources, but only the first source that added the unique candidate increments the run-level count.

## Cold-Start And Sessions

New-user cold-start builds a low-confidence starter persona from request/context signals such as affordability, quality, reliability, and category mentions. It does not require a preference vector; retrieval falls back to request-query semantic search, attribute matching, and quality fallback.

Cross-domain transfer is conservative. The graph only marks a run as cross-domain when both source and target categories are known and meaningfully different domains, such as beauty to electronics or books. Close categories such as `All_Beauty`, `Beauty_and_Personal_Care`, `Beauty`, and `Skincare` stay in the same domain. When cross-domain is active, retrieval uses transferable values like price sensitivity, quality sensitivity, strictness, value, reliability, simplicity, durability, and generic complaint patterns rather than source-category product terms.

Multi-turn sessions refine constraints before retrieval. Follow-up requests such as "something cheaper", "fragrance-free", "not haircare", "avoid that product", or "more premium options" update `active_constraints`, preserve conversation history, and grow `shown_products`. Full onboarding questions, evaluation metrics, and cross-domain benchmarking remain deferred.

## Audit Trail

Task B persists the recommendation pipeline in three linked tables. `recommendation_runs` remains the primary record and stores the final ranked recommendations, request context, source counts, and reproducibility metadata. `intent_plans` stores the agent's structured reasoning brief for the same run, including explicit constraints, persona-derived implicit constraints, retrieval query, required attributes, and avoid lists. `recommendation_candidates` stores one row per scored candidate with retrieval sources, similarity signals, score breakdown, `rank_before_rerank`, and `rank_after_rerank` when the candidate appears in the final LLM-ranked list.

Intent and candidate trace writes are best-effort. If trace persistence fails, recommendation generation still returns the final output and keeps the `recommendation_runs` record as the source of truth. Together these tables provide an audit trail for debugging, ablations, evaluation, and the solution paper.

## Product Embeddings

Product embeddings are built from rich metadata rather than title-only text. `product_embeddings.product_text` includes the title, broad project `category`, Amazon `main_category`, Amazon `categories` hierarchy, top product features, the first description entries/sentences, brand/store, a semantic price tier, and useful details. `category` remains the broad filtering/evaluation bucket, while `main_category` and `categories` enrich semantic matching, refined scoring, and explanations. The stored `product_text` is intentionally kept for debugging and reproducibility: it shows exactly what text was embedded for a product.

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
