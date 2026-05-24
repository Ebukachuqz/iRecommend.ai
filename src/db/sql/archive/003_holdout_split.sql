ALTER TABLE amazon_reviews
ADD COLUMN IF NOT EXISTS task_split TEXT DEFAULT 'persona_train';

CREATE INDEX IF NOT EXISTS amazon_reviews_user_split_idx
ON amazon_reviews (user_id, task_split);

CREATE INDEX IF NOT EXISTS amazon_reviews_parent_asin_idx
ON amazon_reviews (parent_asin);
