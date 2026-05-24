CREATE TABLE IF NOT EXISTS simulation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    parent_asin TEXT NOT NULL,
    holdout_review_id TEXT,
    real_review_text TEXT,
    real_rating FLOAT,
    product_snapshot JSONB,
    input_persona JSONB,
    llm_predicted_rating FLOAT,
    statistical_predicted_rating FLOAT,
    final_predicted_rating FLOAT NOT NULL,
    simulated_review_title TEXT,
    simulated_review_text TEXT NOT NULL,
    confidence FLOAT,
    nigerian_mode BOOLEAN DEFAULT false,
    reasoning_summary TEXT,
    evidence_used JSONB DEFAULT '[]'::jsonb,
    rating_breakdown JSONB,
    model_name TEXT,
    prompt_version TEXT,
    persona_version TEXT,
    generated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE simulation_results
ADD COLUMN IF NOT EXISTS holdout_review_id TEXT,
ADD COLUMN IF NOT EXISTS real_review_text TEXT,
ADD COLUMN IF NOT EXISTS real_rating FLOAT,
ADD COLUMN IF NOT EXISTS product_snapshot JSONB,
ADD COLUMN IF NOT EXISTS input_persona JSONB,
ADD COLUMN IF NOT EXISTS llm_predicted_rating FLOAT,
ADD COLUMN IF NOT EXISTS statistical_predicted_rating FLOAT,
ADD COLUMN IF NOT EXISTS simulated_review_title TEXT,
ADD COLUMN IF NOT EXISTS confidence FLOAT,
ADD COLUMN IF NOT EXISTS reasoning_summary TEXT,
ADD COLUMN IF NOT EXISTS evidence_used JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS rating_breakdown JSONB,
ADD COLUMN IF NOT EXISTS model_name TEXT,
ADD COLUMN IF NOT EXISTS prompt_version TEXT,
ADD COLUMN IF NOT EXISTS persona_version TEXT,
ADD COLUMN IF NOT EXISTS generated_at TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS simulation_results_user_category_idx
ON simulation_results (user_id, category);
