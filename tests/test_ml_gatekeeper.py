from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.ml.ml_gatekeeper import GatekeeperDecision, MLDataGatekeeper


@pytest.fixture
def gatekeeper():
    return MLDataGatekeeper(contamination=0.01)


@pytest.fixture
def dummy_historical():
    """Generate 100 days of normal trading data."""
    dates = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(100)]
    np.random.seed(42)
    # Start at 100, add small random walks
    closes = 100 + np.random.randn(100).cumsum()
    # Ensure no negative prices
    closes = np.abs(closes) + 50

    df = pd.DataFrame(
        {
            "Close": closes,
            "Open": closes - 0.5,
            "High": closes + 1.0,
            "Low": closes - 1.0,
            "Volume": np.random.randint(1000, 5000, 100),
        },
        index=dates,
    )
    return df


def test_ml_gatekeeper_ok(gatekeeper, dummy_historical):
    """Test that a normal candle returns OK."""
    new_date = [dummy_historical.index[-1] + timedelta(days=1)]
    last_close = dummy_historical["Close"].iloc[-1]

    # 1% move is completely normal
    new_df = pd.DataFrame(
        {
            "Close": [last_close * 1.01],
            "Open": [last_close * 1.0],
            "High": [last_close * 1.02],
            "Low": [last_close * 0.99],
            "Volume": [2500],
        },
        index=new_date,
    )

    decision = gatekeeper.evaluate(dummy_historical, new_df)
    assert decision == GatekeeperDecision.OK


def test_ml_gatekeeper_bad_tick(gatekeeper, dummy_historical):
    """Test that a 10x price jump is flagged as BAD_TICK."""
    new_date = [dummy_historical.index[-1] + timedelta(days=1)]
    last_close = dummy_historical["Close"].iloc[-1]

    # 10x move is definitely a bad tick
    new_df = pd.DataFrame(
        {
            "Close": [last_close * 10.0],
            "Open": [last_close * 9.5],
            "High": [last_close * 10.5],
            "Low": [last_close * 9.0],
            "Volume": [2500],
        },
        index=new_date,
    )

    decision = gatekeeper.evaluate(dummy_historical, new_df)
    assert decision == GatekeeperDecision.BAD_TICK


def test_ml_gatekeeper_corporate_action(gatekeeper, dummy_historical):
    """Test that an exact 0.5 ratio (1:1 split) is flagged as CORP_ACTION."""
    new_date = [dummy_historical.index[-1] + timedelta(days=1)]
    last_close = dummy_historical["Close"].iloc[-1]

    # Exactly 0.5 ratio
    new_df = pd.DataFrame(
        {
            "Close": [last_close * 0.501],
            "Open": [last_close * 0.5],
            "High": [last_close * 0.51],
            "Low": [last_close * 0.49],
            "Volume": [5000],  # Volume usually spikes on split
        },
        index=new_date,
    )

    decision = gatekeeper.evaluate(dummy_historical, new_df)
    assert decision == GatekeeperDecision.CORP_ACTION


def test_ml_gatekeeper_not_enough_data(gatekeeper):
    """Test fallback when not enough data is provided."""
    # Only 10 rows
    dates = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(10)]
    df = pd.DataFrame(
        {
            "Close": [100.0] * 10,
            "Open": [100.0] * 10,
            "High": [100.0] * 10,
            "Low": [100.0] * 10,
            "Volume": [1000] * 10,
        },
        index=dates,
    )

    new_date = [dates[-1] + timedelta(days=1)]

    # 0.5 ratio -> Should fallback to hardcoded rule and return CORP_ACTION
    new_df = pd.DataFrame(
        {
            "Close": [50.0],
            "Open": [50.0],
            "High": [50.0],
            "Low": [50.0],
            "Volume": [1000],
        },
        index=new_date,
    )

    decision = gatekeeper.evaluate(df, new_df)
    assert decision == GatekeeperDecision.CORP_ACTION
