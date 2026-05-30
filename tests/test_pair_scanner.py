"""
File: tests/test_pair_scanner.py
Purpose: Unit tests for the pair_scanner.py module.
Last Modified: 2026-05-27
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.scanners.pair_scanner import (
    run_pair_scanner_cli,
    scan_cointegrated_pairs,
)
from src.core.signal import Signal
from src.scanners.pair_scanner import (
    test_cointegration as run_coint_test,
)


def test_test_cointegration() -> None:
    """
    Test Engle-Granger cointegration helper with mock series.
    """
    # Create two highly cointegrated series
    np.random.seed(42)
    steps = 300
    nifty = np.cumprod(1.0 + np.random.randn(steps) * 0.001) * 20000.0
    # Stock A is closely tied to Nifty
    stock_a = nifty * 0.1 + np.random.randn(steps) * 2.0
    stock_b = nifty * 0.1 + np.random.randn(steps) * 2.0

    s1 = pd.Series(stock_a)
    s2 = pd.Series(stock_b)

    pval, zscore, signal = run_coint_test(s1, s2, lookback=252)
    assert not np.isnan(pval)
    # They should be highly cointegrated (p-val is low)
    assert pval < 0.1

    # Check insufficient data path
    pval_short, z_short, sig_short = run_coint_test(s1.head(10), s2.head(10))
    assert np.isnan(pval_short)
    assert np.isnan(z_short)
    assert sig_short == "Insufficient Data"


def test_scan_cointegrated_pairs_empty() -> None:
    """
    Test scan_cointegrated_pairs returns empty dataframe on empty symbols list.
    """
    signals = scan_cointegrated_pairs([], daily_dir="dummy")
    assert isinstance(signals, list)
    assert len(signals) == 0


def test_run_pair_scanner_cli_invalid_dir() -> None:
    """
    Test run_pair_scanner_cli returns empty dataframe on invalid directory.
    """
    signals = run_pair_scanner_cli(daily_dir="non_existent_dir_123")
    assert signals == []


def test_run_pair_scanner_cli_success(tmp_path: Path) -> None:
    """
    Test run_pair_scanner_cli finds files and performs cointegration scans.
    """
    # Create temp directory structure
    d = tmp_path / "1d"
    d.mkdir()

    # Generate 300 steps of data for two cointegrated stocks
    np.random.seed(42)
    steps = 300
    nifty = np.cumprod(1.0 + np.random.randn(steps) * 0.001) * 20000.0
    stock_a_vals = nifty * 0.1 + np.random.randn(steps) * 2.0
    stock_b_vals = nifty * 0.1 + np.random.randn(steps) * 2.0

    df_a = pd.DataFrame({"Close": stock_a_vals})
    df_b = pd.DataFrame({"Close": stock_b_vals})

    df_a.to_parquet(d / "STOCKA.parquet")
    df_b.to_parquet(d / "STOCKB.parquet")

    # Run the scanner
    results = run_pair_scanner_cli(daily_dir=str(d), max_pval=0.20, symbol_limit=5)
    assert isinstance(results, list)
    if results:
        sig = results[0]
        assert isinstance(sig, Signal)
        assert sig.strategy_name == "pair_scanner"
        assert "pair_id" in sig.meta
        assert "pair_symbol" in sig.meta
