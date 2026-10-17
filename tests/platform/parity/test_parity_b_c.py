"""Parity Gate B -> C verification tests.

Validates that materialized warehouse facts match historical Parquets with zero orphan FKs.
"""

from pathlib import Path

import duckdb
import pandas as pd
import pytest


@pytest.fixture
def wh_conn():
    wh_path = Path("data/warehouse.duckdb")
    if not wh_path.exists():
        pytest.skip("data/warehouse.duckdb not found. Run migration and backfill first.")
    conn = duckdb.connect(str(wh_path), read_only=True)
    yield conn
    conn.close()


def test_no_orphan_price_fks(wh_conn) -> None:
    """Verify zero orphan foreign keys from fact_price_daily to dim_symbol."""
    orphan_symbols = wh_conn.execute(
        """
        SELECT count(*) FROM fact_price_daily p
        LEFT JOIN dim_symbol s ON p.symbol_sk = s.symbol_sk
        WHERE s.symbol_sk IS NULL
        """
    ).fetchone()[0]
    assert orphan_symbols == 0, f"Found {orphan_symbols} orphan symbol FKs in fact_price_daily"


def test_no_orphan_date_fks(wh_conn) -> None:
    """Verify zero orphan foreign keys from fact_price_daily to dim_date."""
    orphan_dates = wh_conn.execute(
        """
        SELECT count(*) FROM fact_price_daily p
        LEFT JOIN dim_date d ON p.date_sk = d.date_sk
        WHERE d.date_sk IS NULL
        """
    ).fetchone()[0]
    assert orphan_dates == 0, f"Found {orphan_dates} orphan date FKs in fact_price_daily"


def test_tcs_row_count_matches(wh_conn) -> None:
    """Verify TCS row count in warehouse exactly matches historical Parquet trading days."""
    tcs_file = Path("data/historical/1d/TCS.parquet")
    if not tcs_file.exists():
        pytest.skip("data/historical/1d/TCS.parquet not found")
    tcs_df = pd.read_parquet(tcs_file)
    if not isinstance(tcs_df.index, pd.DatetimeIndex):
        tcs_df.index = pd.to_datetime(tcs_df["Date"] if "Date" in tcs_df.columns else tcs_df.index)
    expected_rows = len(tcs_df.index.normalize().unique())

    wh_rows = wh_conn.execute(
        "SELECT count(*) FROM fact_price_daily WHERE symbol = 'TCS'"
    ).fetchone()[0]
    msg = f"TCS count mismatch: {wh_rows} in warehouse vs {expected_rows} in Parquet"
    assert wh_rows == expected_rows, msg


def test_tcs_date_bounds_match(wh_conn) -> None:
    """Verify min/max trade dates for TCS match historical Parquet."""
    tcs_file = Path("data/historical/1d/TCS.parquet")
    if not tcs_file.exists():
        pytest.skip("data/historical/1d/TCS.parquet not found")
    tcs_df = pd.read_parquet(tcs_file)
    if not isinstance(tcs_df.index, pd.DatetimeIndex):
        tcs_df.index = pd.to_datetime(tcs_df["Date"] if "Date" in tcs_df.columns else tcs_df.index)

    min_date = tcs_df.index.min().date()
    max_date = tcs_df.index.max().date()

    res = wh_conn.execute(
        "SELECT min(trade_date), max(trade_date) FROM fact_price_daily WHERE symbol = 'TCS'"
    ).fetchone()
    assert res[0] == min_date, f"Min date mismatch: {res[0]} vs {min_date}"
    assert res[1] == max_date, f"Max date mismatch: {res[1]} vs {max_date}"


def test_dim_symbol_count(wh_conn) -> None:
    """Verify dim_symbol row count matches master (~2700)."""
    count = wh_conn.execute(
        "SELECT count(*) FROM dim_symbol WHERE is_current = TRUE"
    ).fetchone()[0]
    assert count == 2697, f"dim_symbol count expected 2697, got {count}"


def test_dim_date_coverage(wh_conn) -> None:
    """Verify dim_date spans all trading days from 2000-01-01 to today."""
    res = wh_conn.execute("SELECT min(calendar_date), max(calendar_date) FROM dim_date").fetchone()
    assert res[0] <= pd.to_datetime("2000-01-01").date()
    assert res[1] > pd.Timestamp.now().date()
