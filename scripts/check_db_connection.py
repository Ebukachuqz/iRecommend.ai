from __future__ import annotations

import os
from pathlib import Path
import sys

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


def main() -> None:
    try:
        import psycopg
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg is not installed. Run: pip install -r requirements.txt") from exc

    db_url = get_database_url()
    with psycopg.connect(db_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            cursor.execute("SELECT current_database()")
            database = cursor.fetchone()[0]
    print("Database connection OK.")
    print(f"Database: {database}")
    print(f"Version: {version}")


if __name__ == "__main__":
    main()
