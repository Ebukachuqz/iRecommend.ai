CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS amazon_reviews (
    review_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    parent_asin TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'All_Beauty',
    rating FLOAT,
    title TEXT,
    text TEXT,
    timestamp TIMESTAMPTZ,
    verified_purchase BOOLEAN,
    helpful_vote INTEGER,
    raw_review JSONB DEFAULT '{}'::jsonb,
    task_split TEXT DEFAULT 'persona_train',
    used_for_persona BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS amazon_reviews_user_category_idx
ON amazon_reviews (user_id, category);

CREATE INDEX IF NOT EXISTS amazon_reviews_parent_asin_idx
ON amazon_reviews (parent_asin);

CREATE INDEX IF NOT EXISTS amazon_reviews_task_split_idx
ON amazon_reviews (task_split, used_for_persona);

CREATE TABLE IF NOT EXISTS amazon_product_metadata (
    parent_asin TEXT PRIMARY KEY,
    category TEXT NOT NULL DEFAULT 'All_Beauty',
    title TEXT,
    main_category TEXT,
    categories JSONB DEFAULT '[]'::jsonb,
    features JSONB DEFAULT '[]'::jsonb,
    description JSONB DEFAULT '[]'::jsonb,
    price FLOAT,
    average_rating FLOAT,
    rating_number INTEGER,
    store TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    raw_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_personas (
    user_id TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'All_Beauty',
    persona JSONB NOT NULL,
    persona_version TEXT DEFAULT 'v1',
    model_name TEXT,
    prompt_version TEXT,
    source_review_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, category)
);
