"""Unit tests for staging layer loader."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.platform.exceptions import SchemaValidationError
from src.platform.loaders.staging import StagingLoader


def _create_landing_batch(
    landing_dir: Path, batch_id: str, csv_content: str, trade_date: str = "2026-10-16"
) -> None:
    batch_dir = landing_dir / "nse_bhavcopy" / trade_date / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "bhavcopy.csv").write_text(csv_content, encoding="utf-8")
    data_lines = [line for line in csv_content.strip().split("\n")[1:] if line.strip()]
    manifest = {
        "batch_id": batch_id,
        "source": "nse_bhavcopy",
        "trade_date": trade_date,
        "file_name": "bhavcopy.csv",
        "file_sha256": "dummy",
        "row_count": len(data_lines),
    }
    (batch_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_stage_produces_canonical_columns(tmp_path: Path) -> None:
    """Verify StagingLoader produces Parquet with exact canonical columns."""
    landing_dir = tmp_path / "landing"
    staging_dir = tmp_path / "staging"
    loader = StagingLoader(landing_root=landing_dir, staging_root=staging_dir)

    batch_id = "nse_bhavcopy_20261016_001"
    csv_data = (
        "TradDt,TckrSymb,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd\n"
        "2026-10-16,TCS,3500.0,3550.0,3490.0,3520.0,1000,3520000.0,50\n"
    )
    _create_landing_batch(landing_dir, batch_id, csv_data)

    rows_written = loader.stage(batch_id)
    assert rows_written == 1

    out_file = staging_dir / "price_daily" / "dt=2026-10-16" / f"{batch_id}.parquet"
    assert out_file.is_file()

    df = pd.read_parquet(out_file)
    assert list(df.columns) == loader.CANONICAL_COLUMNS
    assert df["symbol"].iloc[0] == "TCS"
    assert df["open"].iloc[0] == 3500.0
    assert df["high"].iloc[0] == 3550.0
    assert df["low"].iloc[0] == 3490.0
    assert df["close"].iloc[0] == 3520.0
    assert df["volume"].iloc[0] == 1000
    assert df["vwap"].iloc[0] == 3520.0
    assert df["source_batch_id"].iloc[0] == batch_id


def test_stage_validates_against_schema(tmp_path: Path) -> None:
    """Verify validation passes for clean data and fails on empty symbol."""
    landing_dir = tmp_path / "landing"
    staging_dir = tmp_path / "staging"
    loader = StagingLoader(landing_root=landing_dir, staging_root=staging_dir)

    batch_id = "nse_bhavcopy_20261016_bad_sym"
    csv_data = (
        "TradDt,TckrSymb,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,TtlTrfVal\n"
        "2026-10-16,,3500.0,3550.0,3490.0,3520.0,1000,3520000.0\n"
    )
    _create_landing_batch(landing_dir, batch_id, csv_data)

    with pytest.raises(SchemaValidationError, match="empty symbol"):
        loader.stage(batch_id)


def test_stage_rejects_invalid_high_low(tmp_path: Path) -> None:
    """Verify StagingLoader rejects bars where high < low."""
    landing_dir = tmp_path / "landing"
    staging_dir = tmp_path / "staging"
    loader = StagingLoader(landing_root=landing_dir, staging_root=staging_dir)

    batch_id = "nse_bhavcopy_20261016_inverted_hl"
    csv_data = (
        "TradDt,TckrSymb,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol,TtlTrfVal\n"
        "2026-10-16,RELIANCE,2500.0,2400.0,2600.0,2550.0,500,1275000.0\n"
    )
    _create_landing_batch(landing_dir, batch_id, csv_data)

    with pytest.raises(SchemaValidationError, match="high .* < low"):
        loader.stage(batch_id)
