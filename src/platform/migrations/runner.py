"""Migration runner for DuckDB schema evolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.platform.exceptions import MigrationError


@dataclass
class Migration:
    version: int
    name: str
    up_sql: str
    down_sql: str


class MigrationRunner:
    """Manages sequential execution and rollback of schema migrations."""

    def __init__(self, conn: Any = None, migrations: list[Migration] | None = None) -> None:
        self.conn = conn
        self.migrations: list[Migration] = sorted(migrations or [], key=lambda m: m.version)
        self._applied: set[int] = set()

    def applied_migrations(self) -> list[int]:
        """Return list of applied migration versions in ascending order."""
        return sorted(self._applied)

    def up(self, target_version: int | None = None) -> list[int]:
        """Apply pending migrations up to target_version (or all if None)."""
        applied_now: list[int] = []
        for m in self.migrations:
            if target_version is not None and m.version > target_version:
                break
            if m.version not in self._applied:
                try:
                    if self.conn is not None and m.up_sql.strip():
                        self.conn.execute(m.up_sql)
                    self._applied.add(m.version)
                    applied_now.append(m.version)
                except Exception as exc:
                    msg = f"Migration {m.version} ({m.name}) failed on UP: {exc}"
                    raise MigrationError(msg) from exc
        return applied_now

    def down(self, target_version: int = 0) -> list[int]:
        """Rollback applied migrations down to target_version."""
        rolled_back: list[int] = []
        for m in reversed(self.migrations):
            if m.version <= target_version:
                break
            if m.version in self._applied:
                try:
                    if self.conn is not None and m.down_sql.strip():
                        self.conn.execute(m.down_sql)
                    self._applied.remove(m.version)
                    rolled_back.append(m.version)
                except Exception as exc:
                    msg = f"Migration {m.version} ({m.name}) failed on DOWN: {exc}"
                    raise MigrationError(msg) from exc
        return rolled_back
