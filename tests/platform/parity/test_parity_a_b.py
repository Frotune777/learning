"""Parity Gate A -> B verification test."""

import json
from pathlib import Path

import pandas as pd
import pytest


def test_parity_landing_to_staging() -> None:
    """Verify 1:1 parity between latest landing batch manifest and staging Parquet."""
    landing_root = Path("data/landing")
    manifests = list(landing_root.glob("nse_bhavcopy/*/*/manifest.json"))
    if not manifests:
        pytest.skip("No real landing data available in data/landing/ (CI without network).")

    # Pick the most recently modified manifest
    latest_manifest_path = max(manifests, key=lambda p: p.stat().st_mtime)
    with open(latest_manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    trade_date = manifest["trade_date"]
    staging_dir = Path("data/staging/price_daily") / f"dt={trade_date}"
    if not staging_dir.is_dir():
        msg = f"Staging directory {staging_dir} does not exist for batch {manifest['batch_id']}."
        pytest.fail(msg)

    stg_df = pd.read_parquet(staging_dir)

    expected_count = manifest["row_count"]
    assert len(stg_df) == expected_count, f"Count mismatch: {len(stg_df)} vs {expected_count}"
    assert stg_df["symbol"].isna().sum() == 0, "Null symbols found in staging Parquet"
    assert stg_df["trade_date"].isna().sum() == 0, "Null trade_date found in staging Parquet"
    assert (stg_df["high"] >= stg_df["low"]).all(), "Found bars where high < low"
    assert (stg_df["close"] > 0).all(), "Found bars where close <= 0"
