CREATE EXTENSION IF NOT EXISTS vector;

CREATE OR REPLACE FUNCTION match_product_embeddings(
    query_embedding vector(384),
    match_count integer DEFAULT 20,
    exclude_parent_asins text[] DEFAULT ARRAY[]::text[]
)
RETURNS TABLE (
    parent_asin text,
    similarity double precision
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

CREATE OR REPLACE FUNCTION match_user_taste_vectors(
    query_embedding vector(384),
    target_category text,
    match_count integer DEFAULT 5,
    exclude_user_id text DEFAULT NULL
)
RETURNS TABLE (
    user_id text,
    category text,
    similarity double precision
)
LANGUAGE SQL
STABLE
AS $$
    SELECT
        user_taste_vectors.user_id,
        user_taste_vectors.category,
        1 - (user_taste_vectors.embedding <=> query_embedding) AS similarity
    FROM user_taste_vectors
    WHERE user_taste_vectors.embedding IS NOT NULL
      AND user_taste_vectors.category = target_category
      AND (exclude_user_id IS NULL OR user_taste_vectors.user_id <> exclude_user_id)
    ORDER BY user_taste_vectors.embedding <=> query_embedding
    LIMIT match_count;
$$;
