"""Unit tests for landing layer loader."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.platform.lineage import compute_file_sha256
from src.platform.loaders.landing import LandingLoader


def test_ingest_writes_manifest_and_payload(tmp_path: Path) -> None:
    """Verify LandingLoader writes raw payload and valid manifest."""
    loader = LandingLoader(landing_root=tmp_path)
    trade_date = date(2026, 10, 16)

    dummy_csv = tmp_path / "dummy.csv"
    dummy_csv.write_text(
        "TradDt,TckrSymb,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,TtlTrfVal\n"
        "2026-10-16,TCS,3500,3550,3490,3520,1000,3520000\n",
        encoding="utf-8",
    )

    with patch("src.platform.loaders.landing.BhavcopyDownloader") as mock_downloader_cls:
        instance = MagicMock()
        instance.download_day.return_value = dummy_csv
        mock_downloader_cls.return_value = instance

        batch_id = loader.ingest("nse_bhavcopy", trade_date)

    batch_dir = tmp_path / "nse_bhavcopy" / "2026-10-16" / batch_id
    assert batch_dir.is_dir()

    payload_file = batch_dir / "bhavcopy.csv"
    assert payload_file.is_file()

    manifest_file = batch_dir / "manifest.json"
    assert manifest_file.is_file()

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["batch_id"] == batch_id
    assert manifest["source"] == "nse_bhavcopy"
    assert manifest["row_count"] == 1


def test_manifest_contains_checksum(tmp_path: Path) -> None:
    """Verify manifest checksum matches actual payload SHA-256."""
    loader = LandingLoader(landing_root=tmp_path)
    trade_date = date(2026, 10, 16)

    dummy_csv = tmp_path / "dummy_checksum.csv"
    dummy_csv.write_text(
        "TradDt,TckrSymb,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,TtlTrfVal\n"
        "2026-10-16,INFY,1800,1820,1790,1810,500,905000\n",
        encoding="utf-8",
    )

    with patch("src.platform.loaders.landing.BhavcopyDownloader") as mock_downloader_cls:
        instance = MagicMock()
        instance.download_day.return_value = dummy_csv
        mock_downloader_cls.return_value = instance

        batch_id = loader.ingest("nse_bhavcopy", trade_date)

    batch_dir = tmp_path / "nse_bhavcopy" / "2026-10-16" / batch_id
    payload_file = batch_dir / "bhavcopy.csv"
    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))

    computed_hash = compute_file_sha256(payload_file)
    assert manifest["file_sha256"] == computed_hash
    assert loader.validate_manifest(batch_id) is True


def test_batch_id_is_unique_per_call(tmp_path: Path) -> None:
    """Verify successive ingest calls generate distinct, incremented batch IDs."""
    loader = LandingLoader(landing_root=tmp_path)
    trade_date = date(2026, 10, 16)

    dummy_csv = tmp_path / "dummy_seq.csv"
    dummy_csv.write_text("TradDt,TckrSymb,OpnPric\n2026-10-16,TCS,3500\n", encoding="utf-8")

    with patch("src.platform.loaders.landing.BhavcopyDownloader") as mock_downloader_cls:
        instance = MagicMock()
        instance.download_day.return_value = dummy_csv
        mock_downloader_cls.return_value = instance

        b1 = loader.ingest("nse_bhavcopy", trade_date)
        b2 = loader.ingest("nse_bhavcopy", trade_date)

    assert b1 != b2
    assert b1.endswith("_001")
    assert b2.endswith("_002")
