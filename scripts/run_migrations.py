from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Callable, Iterable

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_SQL_DIR = PROJECT_ROOT / "src" / "db" / "sql"
RESET_VERSION = "000"


def migration_version(path: Path) -> str:
    return path.name.split("_", 1)[0]


def discover_migration_files(sql_dir: Path) -> list[Path]:
    return sorted(path for path in sql_dir.glob("*.sql") if path.is_file())


def select_migration_files(
    files: Iterable[Path],
    from_version: str | None = None,
    to_version: str | None = None,
    include_reset: bool = False,
    confirm_reset: bool = False,
) -> list[Path]:
    selected: list[Path] = []
    if include_reset and not confirm_reset:
        raise ValueError("Refusing to include 000_reset_database.sql without --confirm-reset.")

    for path in files:
        version = migration_version(path)
        if version == RESET_VERSION and not include_reset:
            continue
        if from_version and version < from_version:
            continue
        if to_version and version > to_version:
            continue
        selected.append(path)
    return selected


def get_database_url() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL is missing. Add it to .env before running migrations.")
    return db_url


def execute_sql_files(files: list[Path], db_url: str, connect: Callable | None = None) -> None:
    if connect is None:
        try:
            import psycopg
        except ModuleNotFoundError as exc:
            raise RuntimeError("psycopg is not installed. Run: pip install -r requirements.txt") from exc
        connect = psycopg.connect

    connection = connect(db_url)
    try:
        for path in files:
            print(f"Running {path}")
            sql = path.read_text(encoding="utf-8")
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    finally:
        connection.close()


def run_migrations(
    sql_dir: Path = DEFAULT_SQL_DIR,
    from_version: str | None = None,
    to_version: str | None = None,
    include_reset: bool = False,
    confirm_reset: bool = False,
    dry_run: bool = False,
    connect: Callable | None = None,
) -> list[Path]:
    files = select_migration_files(
        discover_migration_files(sql_dir),
        from_version=from_version,
        to_version=to_version,
        include_reset=include_reset,
        confirm_reset=confirm_reset,
    )
    if not files:
        print("No migrations selected.")
        return []
    for path in files:
        print(f"{'Would run' if dry_run else 'Selected'} {path}")
    if dry_run:
        return files
    execute_sql_files(files, get_database_url(), connect=connect)
    return files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run iRecommend SQL migrations against Supabase Postgres.")
    parser.add_argument("--sql-dir", type=Path, default=DEFAULT_SQL_DIR)
    parser.add_argument("--from", dest="from_version")
    parser.add_argument("--to", dest="to_version")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-reset", action="store_true")
    parser.add_argument("--confirm-reset", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        run_migrations(
            sql_dir=args.sql_dir,
            from_version=args.from_version,
            to_version=args.to_version,
            include_reset=args.include_reset,
            confirm_reset=args.confirm_reset,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
