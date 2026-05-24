CREATE TABLE IF NOT EXISTS recommendation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    category TEXT,
    request TEXT,
    context JSONB,
    candidate_count INTEGER,
    recommendations JSONB NOT NULL,
    cold_start BOOLEAN DEFAULT false,
    session_id TEXT,
    model_name TEXT,
    prompt_version TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recommendation_runs_user_category_idx
ON recommendation_runs (user_id, category);

CREATE TABLE IF NOT EXISTS recommendation_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    category TEXT,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recommendation_sessions_user_category_idx
ON recommendation_sessions (user_id, category);
