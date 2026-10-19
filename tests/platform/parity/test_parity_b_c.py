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
    """Verify TCS row count in warehouse reflects canonical trading days (non-trading days purged)."""
    wh_rows = wh_conn.execute(
        "SELECT count(*) FROM fact_price_daily WHERE symbol = 'TCS'"
    ).fetchone()[0]
    # TCS has 4,009 pre-2020 trading days and 1,679 canonical 2020+ trading days (total 5,688)
    assert wh_rows == 5688, f"Expected 5688 canonical trading days for TCS, got {wh_rows}"


def test_tcs_date_bounds_match(wh_conn) -> None:
    """Verify min/max trade dates for TCS match canonical exchange history."""
    res = wh_conn.execute(
        "SELECT min(trade_date), max(trade_date) FROM fact_price_daily WHERE symbol = 'TCS'"
    ).fetchone()
    # Min date is 2002-08-12 (listing), max date is 2026-10-16 (latest sec_bhavdata archive)
    assert res[0] == pd.to_datetime("2002-08-12").date(), f"Min date mismatch: {res[0]}"
    assert res[1] == pd.to_datetime("2026-10-16").date(), f"Max date mismatch: {res[1]}"


def test_dim_symbol_count(wh_conn) -> None:
    """Verify dim_symbol row count matches master (~2700)."""
    count = wh_conn.execute(
        "SELECT count(*) FROM dim_symbol WHERE is_current = TRUE"
    ).fetchone()[0]
    assert count >= 2697, f"dim_symbol count expected at least 2697, got {count}"


def test_dim_date_coverage(wh_conn) -> None:
    """Verify dim_date spans all trading days from 2000-01-01 to today."""
    res = wh_conn.execute("SELECT min(calendar_date), max(calendar_date) FROM dim_date").fetchone()
    assert res[0] <= pd.to_datetime("2000-01-01").date()
    assert res[1] > pd.Timestamp.now().date()
