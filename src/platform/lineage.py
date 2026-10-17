"""Batch ID generation, cryptographic checksums, and manifest lineage writer."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from src.platform.exceptions import LineageIntegrityError


def generate_batch_id(source: str, trade_date: date | str, seq: int = 1) -> str:
    """Generate canonical batch identifier: {source}_{YYYYMMDD}_{seq:03d}."""
    if isinstance(trade_date, date):
        d_str = trade_date.strftime("%Y%m%d")
    else:
        d_str = str(trade_date).replace("-", "")
    clean_source = source.strip().lower().replace(" ", "_")
    return f"{clean_source}_{d_str}_{seq:03d}"


def compute_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(file_path: Path | str, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hex digest of a file in streaming chunks."""
    p = Path(file_path)
    if not p.is_file():
        raise LineageIntegrityError(f"Target file for SHA-256 computation not found: {p}")
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_manifest(manifest_path: Path | str, payload: dict[str, Any]) -> Path:
    """Atomically write manifest JSON metadata using write-then-rename."""
    target = Path(manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    enriched = dict(payload)
    enriched.setdefault("created_at", datetime.now(UTC).isoformat())

    tmp = target.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(enriched, f, indent=2, sort_keys=True)
        os.replace(tmp, target)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        msg = f"Failed to atomically write manifest to {target}: {exc}"
        raise LineageIntegrityError(msg) from exc
    return target
