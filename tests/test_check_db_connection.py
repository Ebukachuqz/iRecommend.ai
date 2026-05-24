from scripts.check_db_connection import connection_hint


def test_connection_hint_detects_docker_postgres_host() -> None:
    hint = connection_hint("postgresql://user:pass@postgres:5432/db")

    assert "Docker-only hostname" in hint


def test_connection_hint_recommends_pooler_for_direct_supabase_host() -> None:
    hint = connection_hint("postgresql://user:pass@db.example.supabase.co:5432/postgres")

    assert "IPv6-only" in hint
    assert "Session Pooler" in hint


def test_connection_hint_recognizes_pooler_host() -> None:
    hint = connection_hint("postgresql://user:pass@aws-0-region.pooler.supabase.com:5432/postgres")

    assert "pooler URI" in hint
