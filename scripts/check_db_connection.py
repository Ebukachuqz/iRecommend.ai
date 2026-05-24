from __future__ import annotations

import os
from pathlib import Path
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_database_url() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL is missing. Add it to .env before checking the database connection.")
    return db_url


def connection_hint(db_url: str) -> str:
    host = urlparse(db_url).hostname or ""
    if host == "postgres":
        return (
            "SUPABASE_DB_URL appears to use host 'postgres', which is usually a Docker-only hostname. "
            "Use the Supabase direct Postgres URI or Session Pooler URI from Supabase Dashboard -> Connect."
        )
    if "pooler.supabase.com" in host:
        return (
            "The URL looks like a Supabase pooler URI. Check that the password is correct, the project is active, "
            "and your network allows outbound PostgreSQL connections."
        )
    if host.endswith(".supabase.co"):
        return (
            "This looks like a direct Supabase database host. Supabase direct database hosts may be IPv6-only. "
            "If your network is IPv4-only, use the Session Pooler connection string from Supabase Dashboard -> Connect."
        )
    return (
        "Check that SUPABASE_DB_URL is the Postgres connection string from Supabase Dashboard -> Connect, "
        "not the Supabase API URL."
    )


def main() -> None:
    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg is not installed. Run: pip install -r requirements.txt") from exc

    db_url = get_database_url()
    try:
        with psycopg.connect(db_url, connect_timeout=15) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                cursor.execute("SELECT current_database()")
                database = cursor.fetchone()[0]
    except psycopg.OperationalError as exc:
        print("Database connection failed.")
        print(connection_hint(db_url))
        print(f"Driver error: {exc}")
        raise SystemExit(1) from exc
    print("Database connection OK.")
    print(f"Database: {database}")
    print(f"Version: {version}")


if __name__ == "__main__":
    main()
