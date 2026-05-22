CREATE TABLE IF NOT EXISTS simulation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    parent_asin TEXT NOT NULL,
    holdout_review_id TEXT,
    real_review_text TEXT,
    real_rating FLOAT,
    llm_predicted_rating FLOAT,
    statistical_predicted_rating FLOAT,
    final_predicted_rating FLOAT NOT NULL,
    simulated_review_title TEXT,
    simulated_review_text TEXT NOT NULL,
    confidence FLOAT,
    nigerian_mode BOOLEAN DEFAULT false,
    reasoning_summary TEXT,
    evidence_used JSONB DEFAULT '[]'::jsonb,
    model_name TEXT,
    prompt_version TEXT,
    persona_version TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS simulation_results_user_category_idx
ON simulation_results (user_id, category);
