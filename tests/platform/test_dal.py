"""Unit tests for concrete Data Access Layer (DAL)."""

from datetime import date
from pathlib import Path

from src.platform.dal import DAL
from src.platform.loaders.warehouse import WarehouseLoader
from src.platform.migrations.runner import MigrationRunner


def _setup_test_db(tmp_path: Path) -> DAL:
    db_file = tmp_path / "test_dal.duckdb"
    runner = MigrationRunner(db_path=db_file)
    runner.migrate()
    wh = WarehouseLoader(db_path=db_file)
    wh.seed_dimensions()

    # Backfill single stock TCS
    hist_dir = tmp_path / "hist"
    hist_dir.mkdir()
    import shutil
    shutil.copy2("data/historical/1d/TCS.parquet", hist_dir / "TCS.parquet")
    wh.backfill_price_from_historical(hist_dir)
    wh.backfill_ta_from_historical(hist_dir)
    return DAL(db_path=db_file)


def test_get_enriched_symbol_returns_dict_with_expected_keys(tmp_path: Path) -> None:
    """Verify get_enriched_symbol returns combined symbol + price + TA metrics."""
    dal = _setup_test_db(tmp_path)
    res = dal.get_enriched_symbol("TCS")
    assert isinstance(res, dict)
    assert res.get("symbol") == "TCS"
    assert "close" in res
    assert "open" in res
    assert "rsi_14" in res
    assert "ema_20" in res


def test_get_price_history_returns_dataframe_with_ohlcv(tmp_path: Path) -> None:
    """Verify get_price_history returns expected time-series DataFrame."""
    dal = _setup_test_db(tmp_path)
    df = dal.get_price_history("TCS", date(2026, 1, 1), date(2026, 10, 16))
    assert not df.empty
    assert "close" in df.columns
    assert "volume" in df.columns
    assert "trade_date" in df.columns
    assert (df["close"] > 0).all()
