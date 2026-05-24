from pathlib import Path
from contextlib import contextmanager
import shutil
import uuid

import pytest

from scripts import run_migrations


@contextmanager
def temp_sql_dir():
    temp_root = Path(__file__).resolve().parents[1] / ".test_tmp"
    temp_root.mkdir(exist_ok=True)
    directory = temp_root / f"migrations_{uuid.uuid4().hex}"
    directory.mkdir()
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def write_sql_files(sql_dir: Path) -> None:
    sql_dir.mkdir(exist_ok=True)
    (sql_dir / "archive").mkdir()
    for name in [
        "002_task_a_schema.sql",
        "000_reset_database.sql",
        "001_core_schema.sql",
        "003_task_b_schema.sql",
    ]:
        (sql_dir / name).write_text(f"-- {name}", encoding="utf-8")
    (sql_dir / "archive" / "999_old.sql").write_text("-- archived", encoding="utf-8")


def test_discover_migration_files_is_sorted_and_ignores_archive() -> None:
    with temp_sql_dir() as tmp_path:
        write_sql_files(tmp_path)

        files = run_migrations.discover_migration_files(tmp_path)

    assert [path.name for path in files] == [
        "000_reset_database.sql",
        "001_core_schema.sql",
        "002_task_a_schema.sql",
        "003_task_b_schema.sql",
    ]


def test_reset_is_skipped_by_default() -> None:
    with temp_sql_dir() as tmp_path:
        write_sql_files(tmp_path)

        files = run_migrations.run_migrations(sql_dir=tmp_path, dry_run=True)

    assert [path.name for path in files] == [
        "001_core_schema.sql",
        "002_task_a_schema.sql",
        "003_task_b_schema.sql",
    ]


def test_reset_requires_explicit_confirmation() -> None:
    with temp_sql_dir() as tmp_path:
        write_sql_files(tmp_path)

        with pytest.raises(ValueError, match="without --confirm-reset"):
            run_migrations.run_migrations(sql_dir=tmp_path, include_reset=True, dry_run=True)


def test_reset_can_be_selected_when_confirmed() -> None:
    with temp_sql_dir() as tmp_path:
        write_sql_files(tmp_path)

        files = run_migrations.run_migrations(
            sql_dir=tmp_path,
            from_version="000",
            to_version="000",
            include_reset=True,
            confirm_reset=True,
            dry_run=True,
        )

    assert [path.name for path in files] == ["000_reset_database.sql"]


def test_from_to_filtering_works() -> None:
    with temp_sql_dir() as tmp_path:
        write_sql_files(tmp_path)

        files = run_migrations.run_migrations(sql_dir=tmp_path, from_version="002", to_version="003", dry_run=True)

    assert [path.name for path in files] == ["002_task_a_schema.sql", "003_task_b_schema.sql"]


def test_dry_run_does_not_execute_sql() -> None:
    with temp_sql_dir() as tmp_path:
        write_sql_files(tmp_path)

        def fail_connect(_db_url):
            raise AssertionError("dry-run should not connect")

        files = run_migrations.run_migrations(sql_dir=tmp_path, dry_run=True, connect=fail_connect)

    assert files


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql):
        self.connection.executed.append(sql)
        if "fail" in sql:
            raise RuntimeError("boom")


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_execute_sql_files_commits_each_file() -> None:
    with temp_sql_dir() as tmp_path:
        first = tmp_path / "001_first.sql"
        second = tmp_path / "002_second.sql"
        first.write_text("select 1", encoding="utf-8")
        second.write_text("select 2", encoding="utf-8")
        connection = FakeConnection()

        run_migrations.execute_sql_files([first, second], "postgres://example", connect=lambda _url: connection)

    assert connection.executed == ["select 1", "select 2"]
    assert connection.commits == 2
    assert connection.rollbacks == 0
    assert connection.closed is True


def test_execute_sql_files_rolls_back_and_stops_on_failure() -> None:
    with temp_sql_dir() as tmp_path:
        first = tmp_path / "001_first.sql"
        second = tmp_path / "002_second.sql"
        first.write_text("select fail", encoding="utf-8")
        second.write_text("select 2", encoding="utf-8")
        connection = FakeConnection()

        with pytest.raises(RuntimeError, match="boom"):
            run_migrations.execute_sql_files([first, second], "postgres://example", connect=lambda _url: connection)

    assert connection.executed == ["select fail"]
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed is True
