"""Unit tests for lineage helpers (batch ID, SHA-256, manifest)."""

import json
from datetime import date
from pathlib import Path

from src.platform.lineage import (
    compute_bytes_sha256,
    compute_file_sha256,
    generate_batch_id,
    write_manifest,
)


def test_generate_batch_id_formatting() -> None:
    """Verify batch ID normalization and zero-padded sequence."""
    batch_id = generate_batch_id("NSE Bhavcopy", date(2026, 10, 16), seq=1)
    assert batch_id == "nse_bhavcopy_20261016_001"


def test_sha256_computation(tmp_path: Path) -> None:
    """Verify byte and streaming file SHA-256 checksums match."""
    payload = b"TEST_PAYLOAD_FOR_LINEAGE_CHECKSUM"
    expected_hash = compute_bytes_sha256(payload)

    test_file = tmp_path / "test.bin"
    test_file.write_bytes(payload)

    file_hash = compute_file_sha256(test_file)
    assert file_hash == expected_hash


def test_write_manifest_atomicity(tmp_path: Path) -> None:
    """Verify manifest creation with atomic write and metadata enrichment."""
    manifest_file = tmp_path / "manifest.json"
    data = {"batch_id": "test_batch_001", "row_count": 100}
    written = write_manifest(manifest_file, data)

    assert written.exists()
    loaded = json.loads(written.read_text(encoding="utf-8"))
    assert loaded["batch_id"] == "test_batch_001"
    assert loaded["row_count"] == 100
    assert "created_at" in loaded
