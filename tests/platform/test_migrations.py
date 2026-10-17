"""Unit tests for platform schema migration runner."""

from src.platform.migrations.runner import Migration, MigrationRunner


def test_empty_migrations_runner() -> None:
    """Verify up and down work safely on empty migration list."""
    runner = MigrationRunner()
    assert runner.applied_migrations() == []
    assert runner.up() == []
    assert runner.down() == []


def test_migrations_up_and_down_lifecycle() -> None:
    """Verify up/down migration execution order."""
    m1 = Migration(version=1, name="init_dim", up_sql="", down_sql="")
    m2 = Migration(version=2, name="init_fact", up_sql="", down_sql="")

    runner = MigrationRunner(migrations=[m2, m1])
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
