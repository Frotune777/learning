"""
File: tests/test_risk_metrics.py
Purpose: Unit tests for the risk_metrics.py module.
Last Modified: 2026-05-27
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.nse_bhavcopy.risk_metrics import (
    add_risk_metrics,
    calculate_beta,
    calculate_calmar_ratio,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
)


def test_calculate_max_drawdown() -> None:
    """
    Test peak-to-trough max drawdown calculation.
    """
    # Simple series: peak=120, trough=80, dd = (80 - 120)/120 = -33.33%
    prices = pd.Series([100.0, 120.0, 90.0, 110.0, 80.0, 130.0])
    dd = calculate_max_drawdown(prices)
    assert pytest.approx(dd, abs=1e-2) == -33.333

    # Insufficient data
    prices_short = pd.Series([100.0])
    assert np.isnan(calculate_max_drawdown(prices_short))


def test_calculate_sharpe_ratio() -> None:
    """
    Test Sharpe ratio calculation.
    """
    # Generate constant upward trending log returns
    # daily returns = 0.001
    prices = pd.Series([100.0 * (1.001**i) for i in range(100)])
    sharpe = calculate_sharpe_ratio(prices, risk_free_daily=0.0)
    assert not np.isnan(sharpe)
    assert sharpe > 0.0

    # Insufficient data
    prices_short = pd.Series([100.0, 101.0])
    assert np.isnan(calculate_sharpe_ratio(prices_short))


def test_calculate_calmar_ratio() -> None:
    """
    Test Calmar ratio calculation.
    """
    prices = pd.Series([100.0 * (1.001**i) for i in range(100)])
    calmar = calculate_calmar_ratio(prices)
    # Since there is no drawdown, Calmar should be NaN
    assert np.isnan(calmar)

    # Let's add a drawdown
    prices_with_dd = pd.Series([100.0, 105.0, 95.0, 102.0, 90.0, 110.0])
    calmar_dd = calculate_calmar_ratio(prices_with_dd, lookback=6)
    # Should calculate a valid value
    assert not np.isnan(calmar_dd)


def test_calculate_beta() -> None:
    """
    Test OLS beta calculation vs benchmark.
    """
    np.random.seed(42)
    bench_returns = np.random.randn(150) * 0.01
    stock_returns = bench_returns * 1.2 + np.random.randn(150) * 0.005

    nifty = pd.Series(np.cumprod(1.0 + bench_returns) * 100.0)
    stock = pd.Series(np.cumprod(1.0 + stock_returns) * 100.0)

    beta = calculate_beta(stock, nifty)
    assert not np.isnan(beta)
    assert beta > 0.0

    # Insufficient data
    assert np.isnan(calculate_beta(stock.head(10), nifty.head(10)))


def test_add_risk_metrics_missing_col() -> None:
    """
    Test add_risk_metrics raises KeyError on missing symbol column.
    """
    df = pd.DataFrame({"CODE": ["TCS", "INFY"]})
    with pytest.raises(KeyError):
        add_risk_metrics(df, daily_dir="dummy", symbol_col="SYMBOL")
