-- WARNING:
-- This script deletes all iRecommend project data. Use only for clean rebuilds.
-- It intentionally leaves extensions such as pgcrypto and vector installed.

CREATE EXTENSION IF NOT EXISTS vector;

DROP FUNCTION IF EXISTS match_product_embeddings(vector(384), integer, text[]);
DROP FUNCTION IF EXISTS match_user_taste_vectors(vector(384), text, integer, text);

DROP TABLE IF EXISTS recommendation_candidates CASCADE;
DROP TABLE IF EXISTS intent_plans CASCADE;
DROP TABLE IF EXISTS recommendation_runs CASCADE;
DROP TABLE IF EXISTS recommendation_sessions CASCADE;
DROP TABLE IF EXISTS simulation_results CASCADE;
DROP TABLE IF EXISTS user_taste_vectors CASCADE;
DROP TABLE IF EXISTS product_embeddings CASCADE;
DROP TABLE IF EXISTS user_personas CASCADE;
DROP TABLE IF EXISTS amazon_reviews CASCADE;
DROP TABLE IF EXISTS amazon_product_metadata CASCADE;
