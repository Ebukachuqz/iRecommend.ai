ALTER TABLE csv_uploads
    ADD COLUMN IF NOT EXISTS processing_summary JSONB DEFAULT '{}'::jsonb;
