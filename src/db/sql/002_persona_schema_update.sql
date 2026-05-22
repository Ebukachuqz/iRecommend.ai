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
ADD COLUMN IF NOT EXISTS source_review_ids JSONB DEFAULT '[]'::jsonb;

ALTER TABLE user_personas
DROP CONSTRAINT IF EXISTS user_personas_pkey;

ALTER TABLE user_personas
ADD CONSTRAINT user_personas_pkey PRIMARY KEY (user_id, category);
