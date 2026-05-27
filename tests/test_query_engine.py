"""
File: tests/test_query_engine.py
Purpose: Unit tests for DuckDBQueryEngine.
Last Modified: 2026-05-27
"""

from pathlib import Path

import pandas as pd

from src.nse_bhavcopy.query_engine import DuckDBQueryEngine


def test_duckdb_query_engine(tmp_path: Path) -> None:
    """
    Verify EOD SQL query capabilities and dynamic symbol extraction from filename.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture. | Valid path.

    Returns:
        None

    Raises:
        None

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> # Executed by pytest
    """
    # Create mock parquet files
    symbol1 = "MOCKA"
    dates1 = pd.date_range("2026-05-01", "2026-05-03")
    df1 = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [95.0, 96.0, 97.0],
            "Close": [100.0, 101.0, 102.0],
            "Volume": [1000, 1100, 1200],
        },
        index=dates1,
    )
    df1.index.name = "Date"

    symbol2 = "MOCKB"
    dates2 = pd.date_range("2026-05-02", "2026-05-04")
    df2 = pd.DataFrame(
        {
            "Open": [200.0, 201.0, 202.0],
            "High": [205.0, 206.0, 207.0],
            "Low": [195.0, 196.0, 197.0],
            "Close": [200.0, 201.0, 202.0],
            "Volume": [2000, 2100, 2200],
        },
        index=dates2,
    )
    df2.index.name = "Date"

    # Save to tmp_path
    df1.to_parquet(tmp_path / f"{symbol1}.parquet")
    df2.to_parquet(tmp_path / f"{symbol2}.parquet")

    # Initialize engine
    engine = DuckDBQueryEngine(data_dir=str(tmp_path))

    # Test query
    res = engine.query("SELECT DISTINCT symbol FROM prices ORDER BY symbol")
    symbols = res["symbol"].tolist()
    assert "MOCKA" in symbols
    assert "MOCKB" in symbols

    # Test get_prices for a single symbol
    prices_a = engine.get_prices(symbol="MOCKA")
    assert len(prices_a) == 3
    assert prices_a["symbol"].iloc[0] == "MOCKA"
    assert prices_a["Close"].iloc[-1] == 102.0

    # Test get_prices with date filter
    prices_filter = engine.get_prices(
        symbol="MOCKA", start_date="2026-05-02", end_date="2026-05-02"
    )
    assert len(prices_filter) == 1
    assert prices_filter["Close"].iloc[0] == 101.0

    # Test get_latest_prices
    latest = engine.get_latest_prices()
    assert len(latest) == 2
    # Sort for deterministic assertion
    latest = latest.sort_values("symbol")
    assert latest["symbol"].iloc[0] == "MOCKA"
    # Latest Date for MOCKA is 2026-05-03
    assert str(latest["Date"].iloc[0]).split(" ")[0] == "2026-05-03"
    assert latest["symbol"].iloc[1] == "MOCKB"
    # Latest Date for MOCKB is 2026-05-04
    assert str(latest["Date"].iloc[1]).split(" ")[0] == "2026-05-04"

    engine.close()
