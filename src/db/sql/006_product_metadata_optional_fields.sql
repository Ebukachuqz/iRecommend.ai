ALTER TABLE amazon_product_metadata
    ADD COLUMN IF NOT EXISTS images JSONB DEFAULT '[]'::jsonb;

ALTER TABLE amazon_product_metadata
    ADD COLUMN IF NOT EXISTS bought_together JSONB DEFAULT '[]'::jsonb;
