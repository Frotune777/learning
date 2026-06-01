"""
File: tests/test_scoring.py
Purpose: Unit tests for the ScoringEngine multi-factor scorer.
Last Modified: 2026-06-01
"""

import numpy as np
import pandas as pd
import pytest

from src.scoring.scoring_engine import ScoringEngine


def test_scoring_engine_empty() -> None:
    """Verify that scoring an empty DataFrame returns an empty DataFrame."""
    engine = ScoringEngine()
    df = pd.DataFrame()
    res = engine.score(df)
    assert res.empty


def test_scoring_engine_calculation() -> None:
    """Verify that ScoringEngine calculates factor scores and composite scores correctly."""
    engine = ScoringEngine()
    
    # Create a mock DataFrame with necessary columns
    df = pd.DataFrame([
        {
            "SYMBOL": "TCS",
            "CMP": 100.0,
            "SMA_20": 95.0,
            "DMA_50": 90.0,
            "DMA_100": 85.0,
            "DMA_150": 80.0,
            "DMA_200": 75.0,
            "DIFF_200_DMA": 33.3,  # ((100-75)/75)*100
            "RSI_14": 60.0,
            "ADX_14": 30.0,
            "PLUS_DI_14": 25.0,
            "MINUS_DI_14": 15.0,
            "CAR_RATING": "Buy/Average Out",
            "SHARPE_1Y": 2.5,
            "MAX_DRAWDOWN_PCT": -8.0,
            "DELIV_PCT": 50.0,
            "VOL_SPIKE": 3.0,
            "GARCH_VOL_PCT": 15.0,
            "Insider Score": 1.0,
            "Event Risk (Days)": 5.0
        }
    ])
    
    res = engine.score(df)
    
    assert "TREND_FACTOR_SCORE" in res.columns
    assert "MOMENTUM_FACTOR_SCORE" in res.columns
    assert "COMPOSITE_SCORE" in res.columns
    assert "RANK" in res.columns
    
    # Check that rank is correctly assigned
    assert res.loc[0, "RANK"] == 1.0
    assert res.loc[0, "COMPOSITE_SCORE"] > 50.0
