CREATE INDEX IF NOT EXISTS amazon_reviews_user_split_idx
ON amazon_reviews (user_id, task_split);

CREATE INDEX IF NOT EXISTS amazon_reviews_parent_asin_idx
ON amazon_reviews (parent_asin);

CREATE INDEX IF NOT EXISTS amazon_reviews_user_parent_asin_idx
ON amazon_reviews (user_id, parent_asin);

CREATE INDEX IF NOT EXISTS amazon_product_metadata_category_idx
ON amazon_product_metadata (category);

CREATE INDEX IF NOT EXISTS user_personas_user_category_idx
ON user_personas (user_id, category);

CREATE INDEX IF NOT EXISTS simulation_results_user_category_idx
ON simulation_results (user_id, category);

CREATE INDEX IF NOT EXISTS recommendation_runs_user_category_idx
ON recommendation_runs (user_id, category);

CREATE INDEX IF NOT EXISTS recommendation_runs_eval_idx
ON recommendation_runs (is_evaluation_run, hit_at_10);

CREATE INDEX IF NOT EXISTS recommendation_sessions_user_idx
ON recommendation_sessions (user_id);

CREATE INDEX IF NOT EXISTS intent_plans_run_idx
ON intent_plans (recommendation_run_id);

CREATE INDEX IF NOT EXISTS recommendation_candidates_run_idx
ON recommendation_candidates (recommendation_run_id);

CREATE INDEX IF NOT EXISTS recommendation_candidates_parent_asin_idx
ON recommendation_candidates (parent_asin);

-- pgvector ivfflat indexes are best created after product embeddings and preference
-- vectors are populated. If these indexes are created before a large bulk load,
-- recreate or REINDEX them after the rebuild for better recall/performance.
CREATE INDEX IF NOT EXISTS product_embeddings_embedding_ivfflat_idx
ON product_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS user_preference_vectors_embedding_ivfflat_idx
ON user_preference_vectors
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);
