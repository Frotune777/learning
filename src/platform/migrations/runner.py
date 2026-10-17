"""Migration runner for DuckDB schema evolution and version tracking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from src.platform.exceptions import MigrationError

MIGRATIONS_DIR = Path(__file__).parent


@dataclass
class Migration:
    version: int
    name: str
    up_sql: str
    down_sql: str = ""


class MigrationRunner:
    """Manages discovery, execution, and audit tracking of database migrations."""

    def __init__(
        self,
        conn: Any = None,
        db_path: Path | str = "data/warehouse.duckdb",
        migrations: list[Migration] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.conn = conn
        self._owned_conn = False
        self._custom_migrations = migrations is not None
        self.migrations: list[Migration] = migrations if migrations is not None else []

    def _ensure_conn(self) -> Any:
        if self.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = duckdb.connect(str(self.db_path))
            self._owned_conn = True
        self._ensure_history_table()
        return self.conn

    def _close_conn(self) -> None:
        if self._owned_conn and self.conn is not None:
            self.conn.close()
            self.conn = None
            self._owned_conn = False

    def _ensure_history_table(self) -> None:
        if self.conn is not None:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_history (
                    version INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def discover_migrations(self, directory: Path | str = MIGRATIONS_DIR) -> list[Migration]:
        """Discover V*.sql migration files on disk sorted by version."""
        p = Path(directory)
        found: list[Migration] = []
        pattern = re.compile(r"^V(\d+)__(.+)\.sql$")
        for f in sorted(p.glob("V*.sql")):
            match = pattern.match(f.name)
            if match:
                ver = int(match.group(1))
                name = match.group(2)
                up_sql = f.read_text(encoding="utf-8")
                # Look for matching undo migration U*.sql
                down_file = p / f"U{ver:03d}__{name}.sql"
                down_sql = down_file.read_text(encoding="utf-8") if down_file.is_file() else ""
                found.append(Migration(version=ver, name=name, up_sql=up_sql, down_sql=down_sql))
        self.migrations = sorted(found, key=lambda m: m.version)
        return self.migrations

    def applied_migrations(self) -> list[int]:
        """Return list of applied migration versions from database."""
        conn = self._ensure_conn()
        try:
            sql = "SELECT version FROM migration_history ORDER BY version ASC"
            rows = conn.execute(sql).fetchall()
            return [r[0] for r in rows]
        finally:
            if not self.migrations and self._owned_conn:
                self._close_conn()

    def up(self, target_version: int | None = None) -> list[int]:
        """Apply pending migrations up to target_version."""
        conn = self._ensure_conn()
        if not self._custom_migrations and not self.migrations:
            self.discover_migrations()

        applied_now: list[int] = []
        already_applied = set(self.applied_migrations())

        for m in sorted(self.migrations, key=lambda x: x.version):
            if target_version is not None and m.version > target_version:
                break
            if m.version not in already_applied:
                try:
                    conn.execute("BEGIN TRANSACTION")
                    if m.up_sql.strip():
                        conn.execute(m.up_sql)
                    conn.execute(
                        "INSERT INTO migration_history (version, name) VALUES (?, ?)",
                        [m.version, m.name],
                    )
                    conn.execute("COMMIT")
                    already_applied.add(m.version)
                    applied_now.append(m.version)
                except Exception as exc:
                    try:
                        conn.execute("ROLLBACK")
                    except Exception:
                        pass
                    msg = f"Migration {m.version} ({m.name}) failed on UP: {exc}"
                    raise MigrationError(msg) from exc
        return applied_now

    def down(self, target_version: int = 0) -> list[int]:
        """Rollback applied migrations down to target_version."""
        conn = self._ensure_conn()
        if not self._custom_migrations and not self.migrations:
            self.discover_migrations()

        rolled_back: list[int] = []
        already_applied = self.applied_migrations()

        mig_map = {m.version: m for m in self.migrations}

        for ver in reversed(already_applied):
            if ver <= target_version:
                break
            m = mig_map.get(ver)
            try:
                conn.execute("BEGIN TRANSACTION")
                if m is not None and m.down_sql.strip():
                    conn.execute(m.down_sql)
                conn.execute("DELETE FROM migration_history WHERE version = ?", [ver])
                conn.execute("COMMIT")
                rolled_back.append(ver)
            except Exception as exc:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                name = m.name if m else f"v{ver}"
                msg = f"Migration {ver} ({name}) failed on DOWN: {exc}"
                raise MigrationError(msg) from exc
        return rolled_back

    def migrate(self) -> list[int]:
        """Convenience method to discover and apply all pending migrations."""
        try:
            return self.up()
        finally:
            self._close_conn()

    def rollback(self, steps: int = 1) -> list[int]:
        """Rollback the last N applied migrations."""
        try:
            applied = self.applied_migrations()
            target = applied[-steps - 1] if len(applied) > steps else 0
            return self.down(target_version=target)
        finally:
            self._close_conn()
