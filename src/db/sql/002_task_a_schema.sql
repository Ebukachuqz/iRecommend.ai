CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS simulation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    category TEXT,
    parent_asin TEXT,
    holdout_review_id TEXT,
    real_review_text TEXT,
    real_rating NUMERIC,
    product_snapshot JSONB,
    input_persona JSONB,
    llm_predicted_rating NUMERIC,
    statistical_predicted_rating NUMERIC,
    final_predicted_rating NUMERIC,
    simulated_review_title TEXT,
    simulated_review_text TEXT,
    confidence NUMERIC,
    nigerian_mode BOOLEAN DEFAULT false,
    reasoning_summary TEXT,
    evidence_used JSONB DEFAULT '[]'::jsonb,
    rating_breakdown JSONB,
    model_name TEXT,
    prompt_version TEXT,
    persona_version TEXT,
    generated_at TIMESTAMPTZ DEFAULT now()
);
