from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "src" / "db" / "sql" / "007_task_b_upgrade.sql"


def read_migration() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_task_b_upgrade_migration_adds_taste_vector_provenance() -> None:
    sql = read_migration()

    assert "alter table user_taste_vectors" in sql
    assert "source_parent_asins" in sql
    assert "source_review_count" in sql
    assert "updated_at" in sql


def test_task_b_upgrade_migration_adds_recommendation_run_metadata() -> None:
    sql = read_migration()

    for column in [
        "retrieval_sources",
        "top_asin",
        "holdout_asin",
        "hit_at_10",
        "rank_of_holdout",
        "is_evaluation_run",
        "embedding_model",
    ]:
        assert column in sql


def test_task_b_upgrade_migration_preserves_recommendation_sessions_name() -> None:
    sql = read_migration()

    assert "recommendation_sessions" in sql
    assert "session_state" not in sql
    assert "conversation_history" in sql
    assert "active_constraints" in sql
    assert "shown_products" in sql
    assert "expires_at" in sql


def test_task_b_upgrade_migration_adds_debug_tables() -> None:
    sql = read_migration()

    assert "create table if not exists intent_plans" in sql
    assert "create table if not exists recommendation_candidates" in sql
    assert "add column if not exists category text" in sql
    assert "prompt_version text" in sql
    assert "collaborative_similarity" in sql
    assert "rank_before_rerank" in sql
    assert "rank_after_rerank" in sql


def test_task_b_upgrade_migration_adds_similar_user_rpc() -> None:
    sql = read_migration()

    assert "create or replace function match_user_taste_vectors" in sql
    assert "exclude_user_id" in sql


def test_task_b_upgrade_migration_ensures_product_vector_rpc() -> None:
    sql = read_migration()

    assert "create or replace function match_product_embeddings" in sql
    assert "exclude_parent_asins" in sql
    assert "similarity float" in sql
