-- Phase B1 Task B schema upgrade.
-- Non-destructive migration: adds columns/tables needed for the stronger
-- persona-centred recommendation pipeline without renaming existing tables.

CREATE EXTENSION IF NOT EXISTS vector;

-- Product embeddings already exist in 004_pgvector_setup.sql. These statements
-- make older databases match the Task B guide while preserving data.
ALTER TABLE product_embeddings
ADD COLUMN IF NOT EXISTS product_text TEXT;

ALTER TABLE product_embeddings
ADD COLUMN IF NOT EXISTS embedding_model TEXT DEFAULT 'sentence-transformers/all-MiniLM-L6-v2';

ALTER TABLE product_embeddings
ALTER COLUMN embedding_model SET DEFAULT 'sentence-transformers/all-MiniLM-L6-v2';

CREATE INDEX IF NOT EXISTS product_embeddings_embedding_ivfflat_idx
ON product_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Taste vectors remain keyed by user_id + category. The new provenance columns
-- explain how much evidence contributed to the vector.
ALTER TABLE user_taste_vectors
ADD COLUMN IF NOT EXISTS source_parent_asins JSONB DEFAULT '[]'::jsonb;

ALTER TABLE user_taste_vectors
ADD COLUMN IF NOT EXISTS source_review_count INTEGER DEFAULT 0;

ALTER TABLE user_taste_vectors
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

ALTER TABLE user_taste_vectors
ALTER COLUMN embedding_model SET DEFAULT 'sentence-transformers/all-MiniLM-L6-v2';

CREATE INDEX IF NOT EXISTS user_taste_vectors_embedding_ivfflat_idx
ON user_taste_vectors
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);

-- recommendation_runs keeps the existing table name and adds retrieval,
-- evaluation, cold-start, and reproducibility fields.
ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS session_id TEXT;

ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS retrieval_sources JSONB DEFAULT '{}'::jsonb;

ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS top_asin TEXT;

ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS cold_start_type TEXT;

ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS nigerian_mode BOOLEAN DEFAULT false;

ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS is_evaluation_run BOOLEAN DEFAULT false;

ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS holdout_asin TEXT;

ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS hit_at_10 BOOLEAN;

ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS rank_of_holdout INTEGER;

ALTER TABLE recommendation_runs
ADD COLUMN IF NOT EXISTS embedding_model TEXT;

ALTER TABLE recommendation_runs
ALTER COLUMN context SET DEFAULT '{}'::jsonb;

ALTER TABLE recommendation_runs
ALTER COLUMN cold_start SET DEFAULT false;

CREATE INDEX IF NOT EXISTS recommendation_runs_user_category_idx
ON recommendation_runs (user_id, category);

CREATE INDEX IF NOT EXISTS recommendation_runs_eval_idx
ON recommendation_runs (is_evaluation_run, hit_at_10);

-- Keep the existing project table name recommendation_sessions. The state JSONB
-- remains for backward compatibility; top-level columns make multi-turn state
-- inspectable.
ALTER TABLE recommendation_sessions
ADD COLUMN IF NOT EXISTS persona JSONB;

ALTER TABLE recommendation_sessions
ADD COLUMN IF NOT EXISTS conversation_history JSONB DEFAULT '[]'::jsonb;

ALTER TABLE recommendation_sessions
ADD COLUMN IF NOT EXISTS active_constraints JSONB DEFAULT '{
    "price_max": null,
    "excluded_products": [],
    "required_attributes": [],
    "excluded_attributes": [],
    "category_filter": null
}'::jsonb;

ALTER TABLE recommendation_sessions
ADD COLUMN IF NOT EXISTS shown_products JSONB DEFAULT '[]'::jsonb;

ALTER TABLE recommendation_sessions
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ DEFAULT (now() + interval '24 hours');

CREATE INDEX IF NOT EXISTS recommendation_sessions_user_category_idx
ON recommendation_sessions (user_id, category);

CREATE INDEX IF NOT EXISTS recommendation_sessions_expires_at_idx
ON recommendation_sessions (expires_at);

CREATE TABLE IF NOT EXISTS intent_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_run_id UUID REFERENCES recommendation_runs(id) ON DELETE CASCADE,
    session_id TEXT,
    user_id TEXT,
    raw_request TEXT,
    interpreted_need TEXT,
    explicit_constraints JSONB DEFAULT '{}'::jsonb,
    implicit_constraints JSONB DEFAULT '{}'::jsonb,
    retrieval_query TEXT,
    avoid JSONB DEFAULT '[]'::jsonb,
    category_filter TEXT,
    price_max FLOAT,
    required_attributes JSONB DEFAULT '[]'::jsonb,
    excluded_attributes JSONB DEFAULT '[]'::jsonb,
    model_name TEXT,
    prompt_version TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS intent_plans_run_idx
ON intent_plans (recommendation_run_id);

CREATE INDEX IF NOT EXISTS intent_plans_user_idx
ON intent_plans (user_id);

CREATE TABLE IF NOT EXISTS recommendation_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_run_id UUID REFERENCES recommendation_runs(id) ON DELETE CASCADE,
    parent_asin TEXT,
    candidate_rank INTEGER,
    retrieval_source TEXT,
    retrieval_sources JSONB DEFAULT '[]'::jsonb,
    semantic_similarity FLOAT,
    final_score FLOAT,
    score_breakdown JSONB DEFAULT '{}'::jsonb,
    product_snapshot JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recommendation_candidates_run_idx
ON recommendation_candidates (recommendation_run_id);

CREATE INDEX IF NOT EXISTS recommendation_candidates_parent_asin_idx
ON recommendation_candidates (parent_asin);
