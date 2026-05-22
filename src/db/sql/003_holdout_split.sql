ALTER TABLE amazon_reviews
ADD COLUMN IF NOT EXISTS task_split TEXT DEFAULT 'persona_train',
ADD COLUMN IF NOT EXISTS used_for_persona BOOLEAN DEFAULT true;

ALTER TABLE amazon_reviews
DROP CONSTRAINT IF EXISTS amazon_reviews_task_split_check;

ALTER TABLE amazon_reviews
ADD CONSTRAINT amazon_reviews_task_split_check
CHECK (task_split IN ('persona_train', 'task_a_holdout', 'task_b_holdout'));

WITH ranked_reviews AS (
    SELECT
        review_id,
        user_id,
        rating,
        ROW_NUMBER() OVER (
            PARTITION BY user_id
            ORDER BY timestamp DESC NULLS LAST
        ) AS rn
    FROM amazon_reviews
)
UPDATE amazon_reviews r
SET
    task_split = CASE
        WHEN rr.rn = 1 THEN 'task_a_holdout'
        WHEN rr.rn = 2 AND rr.rating >= 4 THEN 'task_b_holdout'
        ELSE 'persona_train'
    END,
    used_for_persona = CASE
        WHEN rr.rn IN (1, 2) THEN false
        ELSE true
    END
FROM ranked_reviews rr
WHERE r.review_id = rr.review_id;

CREATE INDEX IF NOT EXISTS amazon_reviews_user_split_idx
ON amazon_reviews (user_id, task_split, used_for_persona);
