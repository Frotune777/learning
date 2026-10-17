"""YAML schema loader and definitions for staging contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.platform.exceptions import SchemaValidationError

SCHEMA_DIR = Path("schemas/staging")


@dataclass
class SchemaDefinition:
    """Staging table schema contract."""

    name: str
    target_table: str
    columns: dict[str, str] = field(default_factory=dict)
    primary_key: list[str] = field(default_factory=list)
    description: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        return self.raw.get(item)

    def __contains__(self, item: str) -> bool:
        return item in self.raw


def load_schema(path: str | Path) -> SchemaDefinition:
    """Load and parse staging schema YAML from a given file path."""
    p = Path(path)
    if not p.is_file():
        raise SchemaValidationError(f"Schema file not found: {p}")
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:
        raise SchemaValidationError(f"Failed to parse YAML schema at {p}: {exc}") from exc

    if not isinstance(data, dict) or "columns" not in data:
        raise SchemaValidationError(f"Schema at {p} must define a 'columns' mapping.")

    cols = data.get("columns", {})
    return SchemaDefinition(
        name=data.get("name", p.stem),
        target_table=data.get("target_table", ""),
        columns=cols if isinstance(cols, dict) else {c["name"]: c.get("type", "str") for c in cols},
        primary_key=data.get("primary_key", []),
        description=data.get("description", ""),
        raw=data,
    )


def load(name: str) -> SchemaDefinition:
    """Load a staging schema by logical name."""
    clean_name = name.removesuffix(".yaml").removesuffix(".yml")
    return load_schema(SCHEMA_DIR / f"{clean_name}.yaml")
