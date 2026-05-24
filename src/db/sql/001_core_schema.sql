CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS amazon_product_metadata (
    parent_asin TEXT PRIMARY KEY,
    category TEXT DEFAULT 'All_Beauty',
    title TEXT,
    main_category TEXT,
    categories JSONB DEFAULT '[]'::jsonb,
    features JSONB DEFAULT '[]'::jsonb,
    description JSONB DEFAULT '[]'::jsonb,
    price NUMERIC,
    average_rating NUMERIC,
    rating_number INTEGER,
    store TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    raw_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS amazon_reviews (
    review_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    parent_asin TEXT NOT NULL,
    rating NUMERIC,
    title TEXT,
    text TEXT,
    timestamp TIMESTAMPTZ,
    verified_purchase BOOLEAN,
    helpful_vote INTEGER,
    raw_review JSONB DEFAULT '{}'::jsonb,
    task_split TEXT DEFAULT 'persona_train',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_personas (
    user_id TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'All_Beauty',
    persona JSONB NOT NULL,
    persona_version TEXT DEFAULT 'v1',
    model_name TEXT,
    prompt_version TEXT,
    review_count INTEGER DEFAULT 0,
    average_rating NUMERIC,
    source_review_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, category)
);
