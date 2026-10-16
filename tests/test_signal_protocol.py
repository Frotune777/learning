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


def test_consensus_aggressive_regime_branch_order() -> None:
    """Verify net_score >= 5.0 triggers STRONG BUY in aggressive regime filter (Lagging/Weakening)
    and does not get swallowed by net_score >= 3.5.
    """
    # Base strategy columns
    strat_cols = [
        "STR_NIFTY_SHOP_ACTION", "STR_BUY_LOW_ACTION", "STR_TURTLE_ACTION",
        "STR_RDX_ACTION", "STR_100SMA_ACTION", "STR_ETF_SHOP_ACTION",
        "STR_SUPER_BO_ACTION", "STR_DMA_REV_ACTION", "STR_DMA_NOSL_ACTION",
        "STR_VCP_ACTION", "STR_TTM_ACTION", "STR_SUPERTREND_ACTION", "STR_LORENTZIAN_ACTION"
    ]
    # In Weakening regime:
    # local_weights: VCP=0.5, SUPER_BO=0.5, all 11 others=1.0. Total weight = 12.0.
    # Score is (buy_weight_sum / 12.0) * 10.0
    # For net_score = 5.5: buy_weight = 6.6 -> 6 buy signals of weight 1.0 + 1 buy of weight 0.5 (SUPER_BO) = 6.5 / 12 * 10 = 5.416
    # Let's test directly with controlled strategy actions:
    # SYM1: 7 buys of weight 1.0 -> 7/12 * 10 = 5.833 (net_score >= 5.0) -> STRONG BUY
    # SYM2: 5 buys of weight 1.0 -> 5/12 * 10 = 4.167 (net_score >= 3.5 and < 5.0) -> HOLD / ADD ON DIPS
    # SYM3: 4 buys of weight 1.0 -> 4/12 * 10 = 3.333 (net_score < 3.5) -> NEUTRAL / SIDEWAYS
    data = {"SYMBOL": ["SYM1", "SYM2", "SYM3"]}
    for c in strat_cols:
        data[c] = ["Hold", "Hold", "Hold"]

    # SYM1: 8 buys -> score 5.71 (>= 5.0) -> STRONG BUY
    for c in strat_cols[:8]:
        data[c][0] = "Buy"

    # SYM2: 5 buys -> score 4.00 (>= 3.5 and < 5.0) -> HOLD / ADD ON DIPS
    for c in strat_cols[:5]:
        data[c][1] = "Buy"

    # SYM3: 4 light buys -> score 2.29 (< 3.5) -> NEUTRAL / SIDEWAYS
    for c in ["STR_NIFTY_SHOP_ACTION", "STR_BUY_LOW_ACTION", "STR_100SMA_ACTION", "STR_ETF_SHOP_ACTION"]:
        data[c][2] = "Buy"

    df = pd.DataFrame(data)
    enriched = add_consensus_score(df, sector_quadrants={"^CNXINFRA": "Weakening"})

    sym1_action = enriched.loc[enriched["SYMBOL"] == "SYM1", "PORTFOLIO_ACTION"].values[0]
    sym2_action = enriched.loc[enriched["SYMBOL"] == "SYM2", "PORTFOLIO_ACTION"].values[0]
    sym3_action = enriched.loc[enriched["SYMBOL"] == "SYM3", "PORTFOLIO_ACTION"].values[0]

    assert sym1_action == "STRONG BUY"
    assert sym2_action == "HOLD / ADD ON DIPS"
    assert sym3_action == "NEUTRAL / SIDEWAYS"


def test_sector_mapping_nifty_bank() -> None:
    """Verify banking symbols with is_nifty_bank=True map to ^NSEBANK instead of ^CNXPSUBANK."""
    from src.core.consensus_engine import get_symbol_sector_map

    df = pd.DataFrame([
        {"symbol": "HDFCBANK", "is_nifty_bank": True},
        {"symbol": "ICICIBANK", "is_nifty_bank": True},
        {"symbol": "AXISBANK", "is_nifty_bank": True},
        {"symbol": "KOTAKBANK", "is_nifty_bank": True},
        {"symbol": "SBIN", "is_nifty_psu_bank": True, "is_nifty_bank": True},
    ])

    mapping = get_symbol_sector_map(df)
    assert mapping["HDFCBANK"] == "^NSEBANK"
    assert mapping["ICICIBANK"] == "^NSEBANK"
    assert mapping["AXISBANK"] == "^NSEBANK"
    assert mapping["KOTAKBANK"] == "^NSEBANK"
    # SBIN matches is_nifty_psu_bank first in dictionary order -> ^CNXPSUBANK
    assert mapping["SBIN"] == "^CNXPSUBANK"


