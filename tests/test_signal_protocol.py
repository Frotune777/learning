from datetime import datetime

import pandas as pd

from src.core.consensus_engine import add_consensus_score, aggregate_signals
from src.core.signal import Signal


def test_signal_validation() -> None:
    # Should raise on bad action
    try:
        Signal("RELIANCE", "test", 2, 0.5, datetime.now(), {})
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_consensus_aggregation() -> None:
    signals = [
        Signal("RELIANCE", "rsi", 1, 0.8, datetime.now(), {"rsi": 75}),
        Signal("RELIANCE", "macd", 1, 0.6, datetime.now(), {}),
        Signal("RELIANCE", "darvas", 0, 0.5, datetime.now(), {}),
    ]
    result = aggregate_signals(signals)
    assert "RELIANCE" in result
    assert -1.0 <= result["RELIANCE"] <= 1.0


def test_add_consensus_score() -> None:
    data = {
        "SYMBOL": ["TCS", "INFY", "RELIANCE"],
        "STR_NIFTY_SHOP_ACTION": ["Level 3 Buy", "Hold", "Explosive Sell"],
        "STR_BUY_LOW_ACTION": ["Buy on Support / Demand Level", "Hold", "Hold"],
        "STR_TURTLE_ACTION": ["Buy (55D Breakout)", "Hold", "Hold"],
        "STR_RDX_ACTION": ["Explosive Buy", "Hold", "Explosive Sell"],
        "STR_100SMA_ACTION": ["Breakout Buy", "Hold", "Hold"],
        "STR_ETF_SHOP_ACTION": ["Buy", "Hold", "Hold"],
        "STR_SUPER_BO_ACTION": ["Super BO Buy", "Hold", "Hold"],
        "STR_DMA_REV_ACTION": ["150 DMA Breakout | CMP > 200 DMA", "Hold", "Hold"],
        "STR_DMA_NOSL_ACTION": ["50 DMA Breakout | CMP > 200 DMA", "Hold", "Hold"],
        # New strategy columns (all neutral for TCS/INFY/RELIANCE in this test)
        "STR_VCP_ACTION": ["No VCP", "No VCP", "No VCP"],
        "STR_TTM_ACTION": ["No Squeeze", "No Squeeze", "No Squeeze"],
        "STR_SUPERTREND_ACTION": ["Hold", "Hold", "Hold"],
        "STR_LORENTZIAN_ACTION": ["No Signal", "No Signal", "No Signal"],
    }
    df = pd.DataFrame(data)
    df_enriched = add_consensus_score(df)

    assert "CONSENSUS_SCORE" in df_enriched.columns
    assert "CONSENSUS_CALLOUT" in df_enriched.columns

    # TCS has all 9 original strategies saying Buy → score should be 9
    # (4 new columns are neutral/No-action, so they don't change the count)
    tcs_score = df_enriched.loc[
        df_enriched["SYMBOL"] == "TCS", "CONSENSUS_SCORE"
    ].values[0]
    assert tcs_score == 9

    # INFY has all Hold → score should be 0
    infy_score = df_enriched.loc[
        df_enriched["SYMBOL"] == "INFY", "CONSENSUS_SCORE"
    ].values[0]
    assert infy_score == 0

    # RELIANCE has 2 Explosive Sell → score should be -2
    rel_score = df_enriched.loc[
        df_enriched["SYMBOL"] == "RELIANCE", "CONSENSUS_SCORE"
    ].values[0]
    assert rel_score == -2

    # Verify callouts — denominator is now dynamic (13 strategies total)
    tcs_callout = df_enriched.loc[
        df_enriched["SYMBOL"] == "TCS", "CONSENSUS_CALLOUT"
    ].values[0]
    assert "HIGH CONVICTION BUY" in tcs_callout
    assert "9/13" in tcs_callout  # 9 buy signals out of 13 total strategies
