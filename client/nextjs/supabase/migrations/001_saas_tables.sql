CREATE TABLE IF NOT EXISTS organisations (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           TEXT NOT NULL,
    market_context TEXT DEFAULT 'global',
    owner_id       UUID REFERENCES auth.users(id),
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS csv_uploads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organisation_id     UUID REFERENCES organisations(id) ON DELETE CASCADE,
    upload_type         TEXT NOT NULL,
    file_name           TEXT NOT NULL,
    column_mapping      JSONB NOT NULL,
    status              TEXT DEFAULT 'pending',
    total_rows          INTEGER DEFAULT 0,
    processed_rows      INTEGER DEFAULT 0,
    personas_generated  INTEGER DEFAULT 0,
    processing_summary  JSONB DEFAULT '{}'::jsonb,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    completed_at        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS merchant_reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organisation_id UUID REFERENCES organisations(id) ON DELETE CASCADE,
    customer_id     TEXT NOT NULL,
    product_name    TEXT,
    category        TEXT,
    rating          FLOAT NOT NULL,
    review_text     TEXT,
    review_date     TEXT,
    extra_fields    JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS merchant_products (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organisation_id UUID REFERENCES organisations(id) ON DELETE CASCADE,
    product_id      TEXT,
    product_name    TEXT NOT NULL,
    category        TEXT NOT NULL,
    price           FLOAT,
    description     TEXT,
    features        JSONB DEFAULT '[]',
    extra_fields    JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS merchant_personas (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organisation_id  UUID REFERENCES organisations(id) ON DELETE CASCADE,
    customer_id      TEXT NOT NULL,
    persona          JSONB NOT NULL,
    review_count     INTEGER DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE(organisation_id, customer_id)
);
