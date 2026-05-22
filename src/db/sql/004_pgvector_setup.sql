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

CREATE OR REPLACE FUNCTION match_product_embeddings(
    query_embedding vector(384),
    match_count INT DEFAULT 20,
    exclude_parent_asins TEXT[] DEFAULT ARRAY[]::TEXT[]
)
RETURNS TABLE (
    parent_asin TEXT,
    similarity FLOAT
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        product_embeddings.parent_asin,
        1 - (product_embeddings.embedding <=> query_embedding) AS similarity
    FROM product_embeddings
    WHERE product_embeddings.embedding IS NOT NULL
      AND NOT (product_embeddings.parent_asin = ANY(exclude_parent_asins))
    ORDER BY product_embeddings.embedding <=> query_embedding
    LIMIT match_count;
$$;
