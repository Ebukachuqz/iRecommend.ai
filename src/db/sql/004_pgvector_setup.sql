CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS product_embeddings (
    parent_asin TEXT PRIMARY KEY REFERENCES amazon_product_metadata(parent_asin),
    embedding vector(384),
    embedding_model TEXT NOT NULL,
    product_text TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_taste_vectors (
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    embedding vector(384),
    embedding_model TEXT NOT NULL,
    source_parent_asins JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, category)
);
