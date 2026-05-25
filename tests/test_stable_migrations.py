from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "src" / "db" / "sql"
ARCHIVE_DIR = SQL_DIR / "archive"
EXPECTED_ACTIVE_FILES = [
    "000_reset_database.sql",
    "001_core_schema.sql",
    "002_task_a_schema.sql",
    "003_task_b_schema.sql",
    "004_pgvector_functions.sql",
    "005_indexes.sql",
    "006_product_metadata_optional_fields.sql",
    "007_rename_user_preference_vectors.sql",
]
ARCHIVED_FILES = [
    "001_initial_schema.sql",
    "002_persona_schema_update.sql",
    "003_holdout_split.sql",
    "004_pgvector_setup.sql",
    "005_simulation_results.sql",
    "006_recommendation_tables.sql",
    "007_task_b_upgrade.sql",
]


def read_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8").lower()


def test_active_migration_folder_has_expected_stable_files_only() -> None:
    active = sorted(path.name for path in SQL_DIR.glob("*.sql"))

    assert active == EXPECTED_ACTIVE_FILES


def test_development_migrations_are_archived() -> None:
    archived = {path.name for path in ARCHIVE_DIR.glob("*.sql")}

    for name in ARCHIVED_FILES:
        assert name in archived


def test_reset_migration_is_destructive_but_project_scoped() -> None:
    sql = read_sql("000_reset_database.sql")

    assert "this script deletes all irecommend project data" in sql
    assert "create extension if not exists vector" in sql
    assert "drop function if exists match_product_embeddings(vector(384), integer, text[])" in sql
    assert "drop function if exists match_user_preference_vectors(vector(384), text, integer, text)" in sql
    assert "drop function if exists match_user_taste_vectors(vector(384), text, integer, text)" in sql
    for table in [
        "recommendation_candidates",
        "intent_plans",
        "recommendation_runs",
        "recommendation_sessions",
        "simulation_results",
        "user_preference_vectors",
        "user_taste_vectors",
        "product_embeddings",
        "user_personas",
        "amazon_reviews",
        "amazon_product_metadata",
    ]:
        assert f"drop table if exists {table}" in sql
    assert "drop extension" not in sql


def test_core_schema_contains_final_core_tables() -> None:
    sql = read_sql("001_core_schema.sql")

    assert "create extension if not exists pgcrypto" in sql
    assert "create table if not exists amazon_product_metadata" in sql
    assert "images jsonb default '[]'::jsonb" in sql
    assert "bought_together jsonb default '[]'::jsonb" in sql
    assert "create table if not exists amazon_reviews" in sql
    assert "task_split text default 'persona_train'" in sql
    assert "create table if not exists user_personas" in sql
    assert "primary key (user_id, category)" in sql
    assert "amazon_reviews" in sql and "category text" not in sql.split("create table if not exists amazon_reviews", 1)[1].split(");", 1)[0]


def test_task_a_schema_contains_simulation_results() -> None:
    sql = read_sql("002_task_a_schema.sql")

    assert "create table if not exists simulation_results" in sql
    assert "final_predicted_rating numeric" in sql
    assert "nigerian_mode boolean default false" in sql


def test_task_b_schema_contains_final_task_b_tables_and_extensions() -> None:
    sql = read_sql("003_task_b_schema.sql")

    assert sql.index("create extension if not exists vector") < sql.index("embedding vector(384)")
    for table in [
        "product_embeddings",
        "user_preference_vectors",
        "recommendation_runs",
        "recommendation_sessions",
        "intent_plans",
        "recommendation_candidates",
    ]:
        assert f"create table if not exists {table}" in sql
    assert "source_review_count integer default 0" in sql
    assert "retrieval_sources jsonb default '[]'::jsonb" in sql
    assert "collaborative_similarity numeric" in sql
    assert "preference_match numeric" in sql
    assert "product_quality numeric" in sql
    assert "price_fit numeric" in sql
    assert "popularity_reliability numeric" in sql


def test_pgvector_functions_match_python_rpc_names() -> None:
    sql = read_sql("004_pgvector_functions.sql")

    assert "create extension if not exists vector" in sql
    assert "create or replace function match_product_embeddings" in sql
    assert "query_embedding vector(384)" in sql
    assert "match_count integer default 20" in sql
    assert "exclude_parent_asins text[] default array[]::text[]" in sql
    assert "returns table" in sql and "parent_asin text" in sql and "similarity double precision" in sql
    assert "create or replace function match_user_preference_vectors" in sql
    assert "target_category text" in sql
    assert "exclude_user_id text default null" in sql


def test_indexes_migration_contains_key_indexes() -> None:
    sql = read_sql("005_indexes.sql")

    for phrase in [
        "amazon_reviews_user_split_idx",
        "amazon_reviews_parent_asin_idx",
        "amazon_reviews_user_parent_asin_idx",
        "amazon_product_metadata_category_idx",
        "user_personas_user_category_idx",
        "recommendation_runs_user_category_idx",
        "recommendation_runs_eval_idx",
        "recommendation_sessions_user_idx",
        "intent_plans_run_idx",
        "recommendation_candidates_run_idx",
        "recommendation_candidates_parent_asin_idx",
        "product_embeddings_embedding_ivfflat_idx",
        "user_preference_vectors_embedding_ivfflat_idx",
    ]:
        assert phrase in sql
    assert "ivfflat indexes are best created after" in sql


def test_product_metadata_optional_fields_migration_is_safe() -> None:
    sql = read_sql("006_product_metadata_optional_fields.sql")

    assert "alter table amazon_product_metadata" in sql
    assert "add column if not exists images jsonb default '[]'::jsonb" in sql
    assert "add column if not exists bought_together jsonb default '[]'::jsonb" in sql


def test_user_preference_vector_rename_migration_is_safe() -> None:
    sql = read_sql("007_rename_user_preference_vectors.sql")

    assert "to_regclass('public.user_taste_vectors')" in sql
    assert "alter table user_taste_vectors rename to user_preference_vectors" in sql
    assert "drop function if exists match_user_taste_vectors(vector(384), text, integer, text)" in sql
    assert "create or replace function match_user_preference_vectors" in sql
    assert "from user_preference_vectors" in sql
