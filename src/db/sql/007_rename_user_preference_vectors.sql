CREATE EXTENSION IF NOT EXISTS vector;

DO $$
BEGIN
    IF to_regclass('public.user_taste_vectors') IS NOT NULL
       AND to_regclass('public.user_preference_vectors') IS NULL THEN
        ALTER TABLE user_taste_vectors RENAME TO user_preference_vectors;
    END IF;

    IF to_regclass('public.user_taste_vectors_embedding_ivfflat_idx') IS NOT NULL
       AND to_regclass('public.user_preference_vectors_embedding_ivfflat_idx') IS NULL THEN
        ALTER INDEX user_taste_vectors_embedding_ivfflat_idx
            RENAME TO user_preference_vectors_embedding_ivfflat_idx;
    END IF;
END $$;

DROP FUNCTION IF EXISTS match_user_taste_vectors(vector(384), text, integer, text);

CREATE OR REPLACE FUNCTION match_user_preference_vectors(
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
        user_preference_vectors.user_id,
        user_preference_vectors.category,
        1 - (user_preference_vectors.embedding <=> query_embedding) AS similarity
    FROM user_preference_vectors
    WHERE user_preference_vectors.embedding IS NOT NULL
      AND user_preference_vectors.category = target_category
      AND (exclude_user_id IS NULL OR user_preference_vectors.user_id <> exclude_user_id)
    ORDER BY user_preference_vectors.embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE INDEX IF NOT EXISTS user_preference_vectors_embedding_ivfflat_idx
ON user_preference_vectors
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);
