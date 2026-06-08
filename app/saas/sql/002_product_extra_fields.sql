ALTER TABLE merchant_products
    ADD COLUMN IF NOT EXISTS extra_fields JSONB DEFAULT '{}'::jsonb;
