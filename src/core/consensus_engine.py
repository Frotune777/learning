import logging
from collections import defaultdict

import pandas as pd

from src.core.signal import Signal

LOGGER = logging.getLogger(__name__)


def aggregate_signals(signals: list[Signal]) -> dict[str, float]:
    """
    Returns {symbol: consensus_score} where:
    -1.0 = unanimous sell, 0.0 = neutral, +1.0 = unanimous buy
    """
    scores: defaultdict[str, list[float]] = defaultdict(list)

    for sig in signals:
        scores[sig.symbol].append(sig.weighted_score)

    return {
        symbol: sum(vals) / len(vals)
        for symbol, vals in scores.items()
        if vals  # skip empty
    }


def get_consensus_recommendation(score: float) -> str:
    if score > 0.3:
        return "STRONG_BUY"
    elif score > 0.1:
        return "BUY"
    elif score < -0.3:
        return "STRONG_SELL"
    elif score < -0.1:
        return "SELL"
    else:
        return "HOLD"


def get_symbol_sector_map(df: pd.DataFrame | None = None) -> dict[str, str]:
    import os

    from src.core.symbol_utils import find_latest_master

    if df is None:
        master_path = find_latest_master("data")
        if not master_path or not os.path.exists(master_path):
            return {}

        try:
            df = pd.read_parquet(master_path)
        except Exception as exc:
            LOGGER.warning("Failed to load symbol sector map from master: %s", exc)
            return {}

    # Map index flag columns to sector symbols
    col_to_sector = {
        "is_nifty_auto": "^CNXAUTO",
        "is_nifty_pharma": "^CNXPHARMA",
        "is_nifty_metal": "^CNXMETAL",
        "is_nifty_it": "^CNXIT",
        "is_nifty_energy": "^CNXENERGY",
        "is_nifty_realty": "^CNXREALTY",
        "is_nifty_psu_bank": "^CNXPSUBANK",
        "is_nifty_media": "^CNXMEDIA",
        "is_nifty_infra": "^CNXINFRA",
        "is_nifty_pse": "^CNXPSE",
        "is_nifty_bank": "^NSEBANK",
    }

    sym_map = {}
    for _, row in df.iterrows():
        sym = str(row.get("Symbol" if "Symbol" in row else "symbol", "")).strip().upper()
        if not sym:
            continue
        matched_sector = "^CNXINFRA"  # default sector
        for col, sec_sym in col_to_sector.items():
            if col in row and row[col] == True:
                matched_sector = sec_sym
                break
        sym_map[sym] = matched_sector

    return sym_map


_get_symbol_sector_map = get_symbol_sector_map


def add_consensus_score(
    df: pd.DataFrame,
    symbol_col: str = "SYMBOL",
    sector_quadrants: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Append consensus, weighted consensus, market state, and action columns to the DataFrame.
    """
    if symbol_col not in df.columns:
        raise KeyError(
            f"Symbol column '{symbol_col}' not found. "
            f"Available: {df.columns.tolist()}"
        )

    # Dynamic Sector Regime Lookup
    sym_sector_map = _get_symbol_sector_map()
    if sector_quadrants is None:
        try:
            from src.nse_bhavcopy.sector_rotation import run_sector_rotation_cli
            df_sec = run_sector_rotation_cli(period=90)
            if not df_sec.empty:
                sector_quadrants = dict(zip(df_sec["Sector"], df_sec["Quadrant"]))
            else:
                sector_quadrants = {}
        except Exception as exc:
            LOGGER.warning("Regime Filter sector rotation lookup failed: %s", exc)
            sector_quadrants = {}

    df = df.copy()
    strategy_cols = [
        "STR_NIFTY_SHOP_ACTION",
        "STR_BUY_LOW_ACTION",
        "STR_TURTLE_ACTION",
        "STR_RDX_ACTION",
        "STR_100SMA_ACTION",
        "STR_ETF_SHOP_ACTION",
        "STR_SUPER_BO_ACTION",
        "STR_DMA_REV_ACTION",
        "STR_DMA_NOSL_ACTION",
        "STR_VCP_ACTION",
        "STR_TTM_ACTION",
        "STR_SUPERTREND_ACTION",
        "STR_LORENTZIAN_ACTION",
    ]
    n_strategies = len(strategy_cols)
    buy_signals = {
        "Buy",
        "Breakout Buy",
        "Explosive Buy",
        "Level 1 Buy",
        "Level 2 Buy",
        "Level 3 Buy",
        "150 DMA Breakout | CMP > 200 DMA",
        "50 DMA Breakout | CMP > 200 DMA",
        "Super BO Buy",
        "Buy on Support / Demand Level",
        "Buy (55D Breakout)",
        "VCP Tightening",
        "Squeeze Active (Bullish)",
        "Long Entry",
        "Lorentzian Buy",
    }
    sell_signals = {"Explosive Sell", "Lorentzian Sell"}

    # Define strategy weights for decision support
    strategy_weights = {
        "STR_NIFTY_SHOP_ACTION": 1.0,
        "STR_BUY_LOW_ACTION": 1.0,
        "STR_TURTLE_ACTION": 2.0,  # High weight (55D breakout)
        "STR_RDX_ACTION": 2.0,  # High weight (Explosive momentum)
        "STR_100SMA_ACTION": 1.0,
        "STR_ETF_SHOP_ACTION": 1.0,
        "STR_SUPER_BO_ACTION": 1.5,
        "STR_DMA_REV_ACTION": 1.5,
        "STR_DMA_NOSL_ACTION": 1.5,
        "STR_VCP_ACTION": 2.0,  # High weight (Minervini VCP)
        "STR_TTM_ACTION": 2.0,  # High weight (TTM Squeeze coiled spring)
        "STR_SUPERTREND_ACTION": 1.5,
        "STR_LORENTZIAN_ACTION": 2.0,  # High weight ML
    }

    scores = []
    callouts = []
    weighted_bull_scores = []
    weighted_bear_scores = []
    market_states = []
    portfolio_actions = []
    confidence_pcts = []
    sector_quads = []
    sl_factors = []

    for _, row in df.iterrows():
        symbol = str(row[symbol_col]).strip().upper()
        sector = sym_sector_map.get(symbol, "^CNXINFRA")
        quadrant = sector_quadrants.get(sector, "Unknown")
        sector_quads.append(quadrant)

        # Dynamic strategy weighting based on quadrant
        local_weights = strategy_weights.copy()
        if quadrant == "Leading":
            local_weights["STR_VCP_ACTION"] = 3.0
            local_weights["STR_SUPER_BO_ACTION"] = 2.5
        elif quadrant in ("Lagging", "Weakening"):
            local_weights["STR_VCP_ACTION"] = 0.5
            local_weights["STR_SUPER_BO_ACTION"] = 0.5

        # Calculate standard consensus score
        score = 0
        buy_weight_sum = 0.0
        sell_weight_sum = 0.0

        for col in strategy_cols:
            val = row.get(col)
            if pd.notna(val):
                if val in buy_signals:
                    score += 1
                    buy_weight_sum += local_weights.get(col, 1.0)
                elif val in sell_signals:
                    score -= 1
                    sell_weight_sum += local_weights.get(col, 1.0)

        scores.append(score)

        # 1. Weighted Scores (scaled from 0 to 10)
        local_total_weight = sum(local_weights.values())
        weighted_bull = (buy_weight_sum / local_total_weight) * 10.0
        weighted_bear = (sell_weight_sum / local_total_weight) * 10.0
        weighted_bull_scores.append(round(weighted_bull, 2))
        weighted_bear_scores.append(round(weighted_bear, 2))

        # 2. Market State / Trend Classification
        cmp = row.get("CMP")
        dma_50 = row.get("DMA_50")
        dma_200 = row.get("DMA_200")

        market_state = "SIDEWAYS"
        if pd.notna(cmp) and cmp > 0:
            if pd.notna(dma_200) and dma_200 > 0:
                if pd.notna(dma_50) and dma_50 > 0:
                    if cmp > dma_200 and cmp > dma_50:
                        market_state = "BULL RUN"
                    elif cmp < dma_200 and cmp > dma_50:
                        market_state = "RECOVERY"
                    elif cmp < dma_200 and cmp < dma_50:
                        market_state = "BEAR TERRITORY"
                else:
                    market_state = "BULL RUN" if cmp > dma_200 else "BEAR TERRITORY"
            elif pd.notna(dma_50) and dma_50 > 0:
                market_state = "BULL RUN" if cmp > dma_50 else "BEAR TERRITORY"

        market_states.append(market_state)

        # 3. Dynamic Portfolio Action & Confidence with Regime Filter
        net_score = weighted_bull - weighted_bear

        # Apply structural 50% penalty if sector is Lagging
        if quadrant == "Lagging":
            net_score *= 0.5

        is_leading_improving = quadrant in ("Leading", "Improving", "Unknown")

        if is_leading_improving:
            # Standard Thresholds (Consensus >= 1.0)
            sl_factors.append(1.0)
            if net_score >= 3.5:
                action = "STRONG BUY"
                conf = min(100.0, 50.0 + (net_score * 8.0))
            elif net_score >= 1.0:
                action = "HOLD / ADD ON DIPS"
                conf = 50.0 + (net_score * 8.0)
            elif net_score <= -3.5:
                action = "EXIT / REDUCE"
                conf = min(100.0, 50.0 + (abs(net_score) * 8.0))
            elif net_score <= -1.0:
                action = "REDUCE / MONITOR"
                conf = 50.0 + (abs(net_score) * 8.0)
            else:
                action = "NEUTRAL / SIDEWAYS"
                conf = 50.0
        else:
            # Aggressive Regime Filter (Consensus >= 3.5 + 50% Stop-Loss tightening)
            sl_factors.append(0.5)
            if net_score >= 5.0:
                action = "STRONG BUY"
                conf = min(100.0, 50.0 + (net_score * 8.0))
            elif net_score >= 3.5:
                action = "HOLD / ADD ON DIPS"
                conf = 50.0 + (net_score * 8.0)
            elif net_score <= -2.0:
                action = "EXIT / REDUCE"
                conf = min(100.0, 50.0 + (abs(net_score) * 8.0))
            else:
                action = "NEUTRAL / SIDEWAYS"
                conf = 50.0

        portfolio_actions.append(action)
        confidence_pcts.append(round(conf, 1))

        # Build detailed callout
        if score >= 4:
            callout = (
                f"⭐ {score}/{n_strategies} strategies agree: "
                f"HIGH CONVICTION BUY on {symbol} (Sector: {quadrant})"
            )
        elif score > 0:
            callout = (
                f"⚖️ {score}/{n_strategies} strategies agree: "
                f"BUY recommendation on {symbol} (Sector: {quadrant})"
            )
        elif score <= -4:
            callout = (
                f"⚠️ {abs(score)}/{n_strategies} strategies agree: "
                f"HIGH CONVICTION SELL on {symbol} (Sector: {quadrant})"
            )
        elif score < 0:
            callout = (
                f"⚠️ {abs(score)}/{n_strategies} strategies agree: "
                f"SELL recommendation on {symbol} (Sector: {quadrant})"
            )
        else:
            callout = f"⚖️ Neutral consensus on {symbol} (Sector: {quadrant})"

        callouts.append(callout)

    df["CONSENSUS_SCORE"] = scores
    df["CONSENSUS_CALLOUT"] = callouts
    df["WEIGHTED_BULL_SCORE"] = weighted_bull_scores
    df["WEIGHTED_BEAR_SCORE"] = weighted_bear_scores
    df["MARKET_STATE"] = market_states
    df["PORTFOLIO_ACTION"] = portfolio_actions
    df["CONFIDENCE_PCT"] = confidence_pcts
    df["SECTOR_QUADRANT"] = sector_quads
    df["REGIME_SL_FACTOR"] = sl_factors

    return df
