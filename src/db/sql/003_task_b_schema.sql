CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS product_embeddings (
    parent_asin TEXT PRIMARY KEY REFERENCES amazon_product_metadata(parent_asin) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,
    product_text TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_taste_vectors (
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    embedding_model TEXT NOT NULL,
    source_parent_asins JSONB DEFAULT '[]'::jsonb,
    source_review_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, category)
);

CREATE TABLE IF NOT EXISTS recommendation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    category TEXT,
    session_id TEXT,
    request TEXT,
    context JSONB DEFAULT '{}'::jsonb,
    candidate_count INTEGER,
    retrieval_sources JSONB DEFAULT '{}'::jsonb,
    recommendations JSONB NOT NULL,
    top_asin TEXT,
    cold_start BOOLEAN DEFAULT false,
    cold_start_type TEXT,
    nigerian_mode BOOLEAN DEFAULT false,
    is_evaluation_run BOOLEAN DEFAULT false,
    holdout_asin TEXT,
    hit_at_10 BOOLEAN,
    rank_of_holdout INTEGER,
    model_name TEXT,
    prompt_version TEXT,
    embedding_model TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recommendation_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    category TEXT,
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    persona JSONB DEFAULT '{}'::jsonb,
    conversation_history JSONB DEFAULT '[]'::jsonb,
    active_constraints JSONB DEFAULT '{}'::jsonb,
    shown_products JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ DEFAULT (now() + interval '24 hours')
);

CREATE TABLE IF NOT EXISTS intent_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_run_id UUID REFERENCES recommendation_runs(id) ON DELETE CASCADE,
    session_id TEXT,
    user_id TEXT,
    category TEXT,
    raw_request TEXT,
    interpreted_need TEXT,
    explicit_constraints JSONB DEFAULT '{}'::jsonb,
    implicit_constraints JSONB DEFAULT '{}'::jsonb,
    retrieval_query TEXT,
    avoid JSONB DEFAULT '[]'::jsonb,
    category_filter TEXT,
    price_max NUMERIC,
    required_attributes JSONB DEFAULT '[]'::jsonb,
    excluded_attributes JSONB DEFAULT '[]'::jsonb,
    model_name TEXT,
    prompt_version TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recommendation_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_run_id UUID REFERENCES recommendation_runs(id) ON DELETE CASCADE,
    parent_asin TEXT,
    candidate_rank INTEGER,
    rank_before_rerank INTEGER,
    rank_after_rerank INTEGER,
    retrieval_source TEXT,
    retrieval_sources JSONB DEFAULT '[]'::jsonb,
    semantic_similarity NUMERIC,
    collaborative_similarity NUMERIC,
    preference_match NUMERIC,
    product_quality NUMERIC,
    price_fit NUMERIC,
    popularity_reliability NUMERIC,
    final_score NUMERIC,
    score_breakdown JSONB DEFAULT '{}'::jsonb,
    product_snapshot JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);
