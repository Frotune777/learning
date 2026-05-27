"""
File: tests/test_volatility_regime.py
Purpose: Unit tests for the volatility_regime.py module.
Last Modified: 2026-05-27
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.nse_bhavcopy.volatility_regime import (
    add_volatility_regime,
    classify_vol_regime,
    fit_garch_vol,
)


def test_classify_vol_regime() -> None:
    """
    Test classification of GARCH annualised volatility.
    """
    assert classify_vol_regime(40.0) == "High"
    assert classify_vol_regime(25.0) == "Medium"
    assert classify_vol_regime(10.0) == "Low"
    assert classify_vol_regime(float("nan")) == "Unknown"


def test_fit_garch_vol() -> None:
    """
    Test GARCH fitting on random returns.
    """
    # 100 observations of daily returns
    np.random.seed(42)
    returns = pd.Series(np.random.randn(100) * 0.01)
    vol = fit_garch_vol(returns)
    assert not np.isnan(vol)
    assert vol > 0.0

    # Insufficient observations (< 60)
    short_returns = pd.Series(np.random.randn(30) * 0.01)
    assert np.isnan(fit_garch_vol(short_returns))


def test_add_volatility_regime_missing_col() -> None:
    """
    Test add_volatility_regime raises KeyError when symbol column is missing.
    """
    df = pd.DataFrame({"CODE": ["TCS"]})
    with pytest.raises(KeyError):
        add_volatility_regime(df, daily_dir="dummy", symbol_col="SYMBOL")
