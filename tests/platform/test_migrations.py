"""Unit tests for platform schema migration runner."""

from pathlib import Path

import duckdb

from src.platform.migrations.runner import Migration, MigrationRunner


def test_empty_migrations_runner() -> None:
    """Verify up and down work safely on empty migration list."""
    runner = MigrationRunner(conn=duckdb.connect(":memory:"), migrations=[])
    assert runner.applied_migrations() == []
    assert runner.up() == []
    assert runner.down() == []


def test_migrations_up_and_down_lifecycle() -> None:
    """Verify up/down migration execution order."""
    conn = duckdb.connect(":memory:")
    m1 = Migration(
        version=1, name="init_dim", up_sql="CREATE TABLE t1 (id INT);", down_sql="DROP TABLE t1;"
    )
    m2 = Migration(
        version=2, name="init_fact", up_sql="CREATE TABLE t2 (id INT);", down_sql="DROP TABLE t2;"
    )

    runner = MigrationRunner(conn=conn, migrations=[m2, m1])
    # UP
    applied = runner.up()
    assert applied == [1, 2]
    assert runner.applied_migrations() == [1, 2]

    # Redundant UP is idempotent
    assert runner.up() == []

    # DOWN
    rolled_back = runner.down(target_version=1)
    assert rolled_back == [2]
    assert runner.applied_migrations() == [1]

    # Full DOWN
    rolled_back_full = runner.down(target_version=0)
    assert rolled_back_full == [1]
    assert runner.applied_migrations() == []


def test_migrate_applies_all(tmp_path: Path) -> None:
    """Verify runner discovers and applies all disk V*.sql migrations."""
    db_file = tmp_path / "test_wh.duckdb"
    runner = MigrationRunner(db_path=db_file)
    applied = runner.migrate()
    assert 1 in applied

    # Verify history table is accurate
    conn = duckdb.connect(str(db_file), read_only=True)
    rows = conn.execute("SELECT version, name FROM migration_history").fetchall()
    conn.close()
    assert len(rows) >= 1
    assert rows[0][0] == 1


def test_rollback_reverses_last(tmp_path: Path) -> None:
    """Verify rollback removes the last applied migration version."""
    db_file = tmp_path / "test_wh_rb.duckdb"
    conn = duckdb.connect(str(db_file))
    m1 = Migration(
        version=1, name="v1", up_sql="CREATE TABLE dummy (x INT);", down_sql="DROP TABLE dummy;"
    )
    runner = MigrationRunner(conn=conn, db_path=db_file, migrations=[m1])
    runner.up()
    assert runner.applied_migrations() == [1]

    runner.down(target_version=0)
    assert runner.applied_migrations() == []
    conn.close()


def test_migration_history_accurate(tmp_path: Path) -> None:
    """Verify migration_history table correctly records metadata."""
    db_file = tmp_path / "test_wh_hist.duckdb"
    runner = MigrationRunner(db_path=db_file)
    runner.migrate()
    conn = duckdb.connect(str(db_file), read_only=True)
    rows = conn.execute("SELECT version, name, applied_at FROM migration_history").fetchall()
    conn.close()
    assert len(rows) >= 1
    assert rows[0][1] == "initial_schema"
    assert rows[0][2] is not None
