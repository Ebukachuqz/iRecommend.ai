ALTER TABLE user_personas
ADD COLUMN IF NOT EXISTS category TEXT;

UPDATE user_personas
SET category = 'All_Beauty'
WHERE category IS NULL;

ALTER TABLE user_personas
ALTER COLUMN category SET NOT NULL;

ALTER TABLE user_personas
ADD COLUMN IF NOT EXISTS persona_version TEXT DEFAULT 'v1',
ADD COLUMN IF NOT EXISTS model_name TEXT,
ADD COLUMN IF NOT EXISTS prompt_version TEXT,
ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS average_rating FLOAT,
ADD COLUMN IF NOT EXISTS source_review_ids JSONB DEFAULT '[]'::jsonb;

DO $$
DECLARE
    primary_key_name TEXT;
BEGIN
    SELECT conname
    INTO primary_key_name
    FROM pg_constraint
    WHERE conrelid = 'user_personas'::regclass
      AND contype = 'p';

    IF primary_key_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE user_personas DROP CONSTRAINT %I', primary_key_name);
    END IF;
END $$;

ALTER TABLE user_personas
ADD CONSTRAINT user_personas_pkey PRIMARY KEY (user_id, category);
