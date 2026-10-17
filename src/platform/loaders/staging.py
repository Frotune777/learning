"""Staging layer loader for canonical typed Parquet transformation."""

from __future__ import annotations

from pathlib import Path


class StagingLoader:
    """Transforms raw landed files into validated canonical staging Parquets."""

    def __init__(self, staging_root: Path | str = "data/staging") -> None:
        self.staging_root = Path(staging_root)

    def stage_batch(self, batch_id: str, schema_name: str) -> Path:
        """Parse, validate against schema, and write staging Parquet."""
        raise NotImplementedError

    def validate_staging_parquet(self, parquet_path: Path | str) -> bool:
        """Validate staging Parquet columns, nullability, and types."""
        raise NotImplementedError
