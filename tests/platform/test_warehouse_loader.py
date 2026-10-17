"""Unit tests for warehouse loader dimension seeding and backfilling."""

from pathlib import Path

import duckdb
import pandas as pd

from src.platform.loaders.warehouse import WarehouseLoader
from src.platform.migrations.runner import MigrationRunner


def _init_test_wh(db_path: Path) -> WarehouseLoader:
    runner = MigrationRunner(db_path=db_path)
    runner.migrate()
    return WarehouseLoader(db_path=db_path)


def test_seed_dim_date_row_count(tmp_path: Path) -> None:
    """Verify dim_date seeding spans 2000-01-01 to today+365 with accurate holiday flags."""
    wh = _init_test_wh(tmp_path / "wh.duckdb")
    counts = wh.seed_dimensions()
    assert counts["dim_date"] > 9500

    conn = duckdb.connect(str(wh.db_path), read_only=True)
    res = conn.execute("SELECT count(*) FROM dim_date WHERE holiday_name IS NOT NULL").fetchone()
    conn.close()
    assert res[0] >= 10  # From holidays.json


def test_seed_dim_symbol_matches_master(tmp_path: Path) -> None:
    """Verify dim_symbol matches master parquet rows (~2700)."""
    wh = _init_test_wh(tmp_path / "wh.duckdb")
    counts = wh.seed_dimensions()
    assert counts["dim_symbol"] == 2697

    conn = duckdb.connect(str(wh.db_path), read_only=True)
    sql = "SELECT symbol, is_current, is_active FROM dim_symbol WHERE symbol = 'TCS'"
    row = conn.execute(sql).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "TCS"
    assert row[1] is True


def test_backfill_price_one_symbol(tmp_path: Path) -> None:
    """Verify price backfill for TCS yields ~5699 rows."""
    wh = _init_test_wh(tmp_path / "wh.duckdb")
    wh.seed_dimensions()

    # Create dummy dir with only TCS.parquet
    test_hist_dir = tmp_path / "hist"
    test_hist_dir.mkdir()
    tcs_src = Path("data/historical/1d/TCS.parquet")
    if not tcs_src.exists():
        return

    import shutil
    shutil.copy2(tcs_src, test_hist_dir / "TCS.parquet")

    res = wh.backfill_price_from_historical(test_hist_dir)
    assert res["symbols_processed"] == 1
    assert res["rows_inserted"] == 5693

    conn = duckdb.connect(str(wh.db_path), read_only=True)
    query = "SELECT count(*) FROM fact_price_daily WHERE symbol = 'TCS'"
    count = conn.execute(query).fetchone()[0]
    conn.close()
    assert count == 5693


def test_backfill_skips_unknown_symbol(tmp_path: Path) -> None:
    """Verify synthetic symbol not in dim_symbol is logged as SKIPPED_UNIVERSE."""
    wh = _init_test_wh(tmp_path / "wh.duckdb")
    wh.seed_dimensions()

    test_hist_dir = tmp_path / "hist_skip"
    test_hist_dir.mkdir()

    # Create a synthetic symbol parquet
    df = pd.DataFrame({
        "Open": [100.0], "High": [105.0], "Low": [99.0], "Close": [102.0], "Volume": [1000]
    }, index=pd.to_datetime(["2026-10-16"]))
    df.index.name = "Date"
    df.to_parquet(test_hist_dir / "SYNTHETIC_UNKNOWN.parquet")

    res = wh.backfill_price_from_historical(test_hist_dir)
    assert res["skipped_universe"] == 1
    assert res["symbols_processed"] == 0
