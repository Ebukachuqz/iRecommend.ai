# Data Pipeline Notes

The initial pipeline streams Amazon Reviews 2023, filters users by minimum review count, writes reviews and matching product metadata to Supabase, creates chronological holdout splits, and generates personas only from `persona_train` reviews.
