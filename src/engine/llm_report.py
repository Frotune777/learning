"""
File: src/engine/llm_report.py
Purpose: Generates a comprehensive, clean, Markdown & structured text report for any stock symbol.
Designed specifically for sharing with LLMs (e.g., Claude, ChatGPT, Gemini) for deep quantitative analysis,
setup review, and trade validation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.core.config import Config
from src.engine.lux_bos_pullback import calculate_valid_bos_pullback
from src.engine.lux_ifvg_sweeps import calculate_sweeps_ifvgs
from src.engine.lux_nwe import calculate_nwe
from src.engine.lux_savgol import calculate_savgol
from src.engine.lux_volume_profile import calculate_volume_profile
from src.engine.lux_vsa import calculate_vsa_bars
from src.engine.lux_weinstein import calculate_weinstein_stage
from src.engine.smc import calculate_smc
from src.engine.smc_decision import generate_smc_call
from src.nse_bhavcopy.ta_indicators import add_ta_indicators, calculate_technical_score

LOGGER = logging.getLogger(__name__)


def _needs_ta_recompute(df: pd.DataFrame) -> bool:
    """Check if required TA indicators are missing or NaN on the trailing row."""
    req_indicators = ("RSI_14", "ADX_14", "ATR_14", "MACD_HIST", "SMA_50", "SMA_200")
    if df.empty or len(df) < 2:
        return False
    for col in req_indicators:
        if col not in df.columns or pd.isna(df[col].iloc[-1]):
            return True
def _build_reconciliation_section(
    cmp: float,
    smc_res: Any,
    w_res: Any,
    nwe_res: Any,
    sg_res: Any,
    vsa_res: Any,
    ta_score_dict: dict[str, Any],
    sma_50: float,
    sma_200: float,
    vp_res: Any,
) -> list[str]:
    """
    Synthesize multi-lens disagreements and confluences into Markdown Section 7.
    """
    sec = ["\n## 7. Quantitative Lens Reconciliation"]

    # 7.1 Macro vs. Micro Structural Alignment
    sec.append("### 7.1 Macro vs. Micro Structural Alignment")
    sec.append(f"- **Macro Weinstein Stage:** `{w_res.stage_name}`")
    swing_trend_str = "BULLISH" if smc_res.current_swing_trend == 1 else ("BEARISH" if smc_res.current_swing_trend == -1 else "NEUTRAL")
    sec.append(f"- **SMC Institutional Trend:** `{swing_trend_str}`")

    # Weinstein vs SMC
    if w_res.current_stage == 4 and smc_res.current_swing_trend == 1:
        sec.append("- **Structural Synthesis:** Counter-trend rally within a broader markdown regime; treat institutional buy setups as tactical pullbacks rather than secular reversals.")
    elif w_res.current_stage == 2 and smc_res.current_swing_trend == -1:
        sec.append("- **Structural Synthesis:** Short-term structural pullback within an advancing macro markup stage; monitor discount zones for trend continuation support.")
    elif w_res.current_stage == 2 and smc_res.current_swing_trend == 1:
        sec.append("- **Structural Synthesis:** Bullish multi-timeframe confluence; intermediate markup stage aligns with upward institutional swing structure.")
    elif w_res.current_stage == 4 and smc_res.current_swing_trend == -1:
        sec.append("- **Structural Synthesis:** Bearish multi-timeframe confluence; intermediate markdown stage aligns with downward institutional swing structure.")
    else:
        sec.append("- **Structural Synthesis:** Transitional macro/micro structure; monitor structural breaks (BOS/CHoCH) for confirmation.")

    # SMA 50 vs SMA 200
    if not np.isnan(sma_50) and not np.isnan(sma_200):
        if cmp > sma_50 and cmp < sma_200:
            sec.append("- **Macro Moving Average Context:** Intermediate cyclical recovery operating below the secular 200-day moving average; long-term macro resistance remains overhead (Note: 10W MA ≡ SMA_50 by construction).")
        elif cmp < sma_50 and cmp > sma_200:
            sec.append("- **Macro Moving Average Context:** Corrective pullback testing intermediate support above the secular 200-day bull anchor (Note: 10W MA ≡ SMA_50 by construction).")
        elif cmp > sma_50 and cmp > sma_200:
            sec.append("- **Macro Moving Average Context:** Full macro moving average alignment (price above both 50D and 200D averages).")
        elif cmp < sma_50 and cmp < sma_200:
            sec.append("- **Macro Moving Average Context:** Full secular bear alignment (price below both 50D and 200D averages).")

    # 7.2 Statistical Extremes & Momentum Tension
    sec.append("\n### 7.2 Statistical Extremes & Momentum Tension")
    score = ta_score_dict.get("score", 50)
    rating = ta_score_dict.get("rating", "NEUTRAL")
    sec.append(f"- **Composite Technical Score:** {score}/100 (`{rating}`)")

    # Composite vs Weinstein
    if score >= 70 and w_res.current_stage == 4:
        sec.append("- **Score vs. Regime Conflict:** Intermediate technical momentum and indicator alignment conflict with macro stage headwinds; high-beta rally occurring below declining moving averages.")
    elif score <= 30 and w_res.current_stage == 2:
        sec.append("- **Score vs. Regime Conflict:** Temporary indicator exhaustion or consolidation within an advancing stage; underlying macro trend remains constructive.")

    # SMC vs NWE
    nwe_overbought = cmp >= nwe_res.latest_upper
    nwe_oversold = cmp <= nwe_res.latest_lower
    if smc_res.current_swing_trend == 1 and nwe_overbought:
        sec.append("- **Statistical Envelope Tension:** Bullish structural expansion has reached an upper statistical volatility extreme; elevated risk of sharp mean-reversion pullback before further upside.")
    elif smc_res.current_swing_trend == -1 and nwe_oversold:
        sec.append("- **Statistical Envelope Tension:** Bearish structural impulse is extended into the lower statistical envelope; high probability of a short-squeeze or snapback bounce.")
    else:
        sec.append("- **Statistical Envelope Context:** Price oscillating within standard non-parametric kernel distribution boundaries.")

    # SMC Trend vs Savitzky-Golay
    if smc_res.current_swing_trend == 1 and sg_res.latest_turn_signal == -1:
        sec.append("- **Digital Filter Turning Inflection:** Upward trend showing local deceleration; negative second derivative suggests short-term momentum exhaustion prior to structural confirmation.")
    elif smc_res.current_swing_trend == -1 and sg_res.latest_turn_signal == 1:
        sec.append("- **Digital Filter Turning Inflection:** Downward trend showing local deceleration; positive second derivative highlights nascent curvature bottoming.")
    else:
        sec.append("- **Digital Filter Inflection Context:** Savitzky-Golay polynomial trajectory indicates momentum trend continuation.")

    # 7.3 Volume Conviction & Auction Context
    sec.append("\n### 7.3 Volume Conviction & Auction Context")
    if vsa_res.latest_no_demand:
        sec.append("- **Volume Spread Assessment:** Upward price progression accompanied by low relative volume and narrow spread, signaling lack of aggressive buying conviction.")
    elif vsa_res.latest_no_supply:
        sec.append("- **Volume Spread Assessment:** Downside progression on dried-up volume and narrow spread, suggesting exhaustion of aggressive selling pressure.")
    else:
        sec.append("- **Volume Spread Assessment:** Volume spread profile shows normal participation without active No-Demand or No-Supply testing signals.")

    cmp_va_pos = "Inside 70% Value Area" if vp_res.val_price <= cmp <= vp_res.vah_price else (
        "Above Value Area (Premium/Overextended)" if cmp > vp_res.vah_price else "Below Value Area (Discount/Undervalued)"
    )
    sec.append(f"- **Auction Value Position:** `{cmp_va_pos}` relative to VPOC anchor at ₹{vp_res.poc_price:,.2f}.")

    return sec


def generate_symbol_llm_dossier(
    symbol: str,
    hist_dir: str = Config.DEFAULT_HIST_DIR,
    timeframe: str = "1d",
) -> str:
    """
    Compile a complete institutional-grade Markdown dossier for a symbol
    spanning Price Action, Multi-Factor Technicals, SMC, LuxAlgo Regimes,
    and Risk-Reward parameters formatted specifically for LLM context injection.
    """
    sym = symbol.strip().upper().replace(".NS", "")
    
    # Try both direct path and timeframe subdirectory
    candidates = [
        Path(hist_dir) / f"{sym}.parquet",
        Path(hist_dir) / timeframe / f"{sym}.parquet",
        Path("data/historical/1d") / f"{sym}.parquet",
        Path("data/historical") / f"{sym}.parquet",
    ]
    p_path = next((p for p in candidates if p.exists()), None)

    if not p_path:
        return f"Error: No historical parquet data found for symbol '{sym}'. Please sync historical data first."

    try:
        df = pd.read_parquet(p_path)
    except Exception as e:
        return f"Error loading data for '{sym}': {e}"

    if df.empty or len(df) < 30:
        return f"Error: Insufficient data rows ({len(df)}) for '{sym}'. Minimum 30 required."

    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    else:
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # Standardize column casing for downstream modules
    cols_map = {c: c.lower() for c in df.columns}
    df_lower = df.rename(columns=cols_map)

    # Standardize capitalized columns for TA indicators
    cap_map = {}
    for c in df.columns:
        cl = c.lower()
        if cl in ("open", "high", "low", "close", "volume"):
            cap_map[c] = cl.capitalize()
    df_cap = df.rename(columns=cap_map)
    if _needs_ta_recompute(df_cap):
        try:
            df_cap = add_ta_indicators(df_cap)
        except Exception as exc:
            LOGGER.warning("Could not calculate TA indicators for %s: %s", sym, exc)

    last_row = df_cap.iloc[-1]
    cmp = float(last_row.get("Close", 0.0))
    open_p = float(last_row.get("Open", 0.0))
    high_p = float(last_row.get("High", 0.0))
    low_p = float(last_row.get("Low", 0.0))
    volume = float(last_row.get("Volume", 0.0))
    date_str = df_cap.index[-1].strftime("%Y-%m-%d")

    # 1D Change %
    prev_close = float(df_cap["Close"].iloc[-2]) if len(df_cap) >= 2 else cmp
    chg_pct = ((cmp - prev_close) / prev_close * 100.0) if prev_close > 0 else 0.0

    # 1. Technical Score & Baseline Indicators
    ta_score_dict = calculate_technical_score(last_row) if "RSI_14" in df_cap.columns else {"score": 50, "rating": "NEUTRAL"}
    rsi = last_row.get("RSI_14", np.nan)
    adx = last_row.get("ADX_14", np.nan)
    atr = last_row.get("ATR_14", np.nan)
    ema_20 = last_row.get("EMA_20", np.nan)
    sma_50 = last_row.get("SMA_50", np.nan)
    sma_200 = last_row.get("SMA_200", np.nan)
    macd = last_row.get("MACD", np.nan)
    macd_sig = last_row.get("MACD_SIGNAL", np.nan)
    macd_hist = last_row.get("MACD_HIST", np.nan)

    # 2. Smart Money Concepts (SMC) & Trading Call
    smc_res = calculate_smc(df_lower, swing_length=20, internal_length=5)
    smc_call = generate_smc_call(sym, smc_res, df_lower)

    # 3. LuxAlgo Portfolio Engines
    # (a) Weinstein 4-Stage
    w_res = calculate_weinstein_stage(df_lower, ma_weeks=10, slope_weeks=2, is_daily=True)
    # (b) Volume Profile
    vp_res = calculate_volume_profile(df_lower, lookback=min(len(df_lower), 120))
    # (c) Nadaraya-Watson Envelope
    nwe_res = calculate_nwe(df_lower, bandwidth=8.0, multiplier=2.5)
    # (d) VSA Tests
    vsa_res = calculate_vsa_bars(df_lower)
    # (e) Savitzky-Golay Inflections
    sg_res = calculate_savgol(df_lower, half_width=10, poly_order=2)
    # (f) Sweeps & iFVGs
    sw_res = calculate_sweeps_ifvgs(df_lower, swing_len=4)
    # (g) Valid BOS Pullback
    bos_res = calculate_valid_bos_pullback(df_lower, left_bars=2, right_bars=2, swing_lookback=40)

    # Compile Markdown Document
    doc = []
    doc.append(f"# Institutional Quantitative Dossier: {sym}")
    doc.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | **Timeframe:** {timeframe.upper()} | **Last Candle Date:** {date_str}\n")
    
    doc.append("## 1. Executive Summary & Market Snapshot")
    doc.append(f"- **Current Market Price (CMP):** ₹{cmp:,.2f} ({chg_pct:+.2f}%)")
    doc.append(f"- **Day's Range:** Low ₹{low_p:,.2f} — High ₹{high_p:,.2f} (Open: ₹{open_p:,.2f})")
    doc.append(f"- **Traded Volume:** {volume:,.0f} shares")
    doc.append(f"- **Technical Composite Score:** {ta_score_dict.get('score', 'N/A')}/100 (`{ta_score_dict.get('rating', 'NEUTRAL')}`)")
    doc.append(f"- **Macro Weinstein Stage:** `{w_res.stage_name}` (10W MA: ₹{w_res.ma_value:,.2f}, Slope: {w_res.ma_slope_pct:+.2f}%, Vol Ratio: {w_res.volume_ratio:.2f}x)")
    doc.append("  * *(Classifier uses a 10W MA, faster than Weinstein's original 30W.)*")
    if w_res.is_breakout:
        doc.append("  * **ALERT:** Active Stage 2 Expansion Breakout confirmed!")
    if w_res.is_breakdown:
        doc.append("  * **WARNING:** Stage 4 Capitulation Breakdown confirmed!")

    doc.append("\n## 2. Actionable SMC Trading Setup")
    if smc_call:
        doc.append(f"- **Signal Direction:** `{smc_call.direction}`")
        doc.append(f"- **Setup Type:** `{smc_call.setup_type}`")
        doc.append(f"- **Trigger Entry Price:** ₹{smc_call.entry_price:,.2f}")
        doc.append(f"- **Invalidation Stop Loss:** ₹{smc_call.stop_loss:,.2f}")
        doc.append(f"- **Profit Target 1 (TP1):** ₹{smc_call.target_1:,.2f}")
        doc.append(f"- **Profit Target 2 (TP2):** ₹{smc_call.target_2:,.2f}")
        doc.append(f"- **Risk-to-Reward Ratio:** `{smc_call.risk_reward:.2f}R`")
        doc.append(f"- **Setup Notes:** {smc_call.notes}")
    else:
        doc.append("- **Status:** `NO ACTIVE TRIGGER` (Market not at institutional discount/premium mitigation extreme or RR < 1.8R)")
    doc.append("\n## 3. Institutional Smart Money Structure (ICT / SMC)")
    swing_bias_str = "BULLISH" if smc_res.current_swing_trend == 1 else ("BEARISH" if smc_res.current_swing_trend == -1 else "NEUTRAL")
    internal_bias_str = "BULLISH" if smc_res.current_internal_trend == 1 else ("BEARISH" if smc_res.current_internal_trend == -1 else "NEUTRAL")
    doc.append(f"- **Higher Timeframe Trend Bias:** `{swing_bias_str}`")
    doc.append(f"- **Internal Market Structure Shift:** `{internal_bias_str}`")
    doc.append(f"- **Equilibrium Level (50% Fair Value):** ₹{smc_res.equilibrium_level:,.2f}")
    doc.append(f"- **Discount Zone (Institutional Buy Zone):** ₹{smc_res.discount_zone[0]:,.2f} – ₹{smc_res.discount_zone[1]:,.2f}")
    doc.append(f"- **Premium Zone (Institutional Sell Zone):** ₹{smc_res.premium_zone[0]:,.2f} – ₹{smc_res.premium_zone[1]:,.2f}")
    doc.append(f"- **Active Fair Value Gaps (FVG):** {len(smc_res.active_fair_value_gaps)} unmitigated imbalances")
    doc.append(f"- **Active Order Blocks:** {len(smc_res.active_order_blocks)} institutional blocks")

    doc.append(f"- **Liquidity Sweeps & Inverted FVGs (iFVG):**")
    latest_swp = sw_res.latest_sweep
    if latest_swp:
        doc.append(f"  * Last Liquidity Sweep: `{latest_swp.direction}` at ₹{latest_swp.price:,.2f}")
    else:
        doc.append("  * No recent liquidity sweeps")
    if sw_res.latest_ifvg:
        iz = sw_res.latest_ifvg
        doc.append(f"  * Active Inverted FVG (Breaker Zone): `{iz.direction}` from ₹{iz.bottom:,.2f} to ₹{iz.top:,.2f} (Mitigated: {iz.mitigated})")

    doc.append("\n## 4. Auction Market & Volume Profile Geometry")
    doc.append(f"- **Volume Point of Control (VPOC):** ₹{vp_res.poc_price:,.2f} (High volume magnet node)")
    doc.append(f"- **Value Area High (VAH):** ₹{vp_res.vah_price:,.2f}")
    doc.append(f"- **Value Area Low (VAL):** ₹{vp_res.val_price:,.2f}")
    cmp_va_pos = "Inside 70% Value Area" if vp_res.val_price <= cmp <= vp_res.vah_price else (
        "Above Value Area (Premium/Overextended)" if cmp > vp_res.vah_price else "Below Value Area (Discount/Undervalued)"
    )
    doc.append(f"- **Price Auction Context:** `{cmp_va_pos}`")
    doc.append(f"- **Volume Spread Analysis (VSA):**")
    vsa_state = "No-Demand Bar (Lack of institutional buying on rally)" if vsa_res.latest_no_demand else (
        "No-Supply Bar (Absorption of selling on pullback)" if vsa_res.latest_no_supply else "Normal Volume Spread"
    )
    doc.append(f"  * Status: `{vsa_state}` (Rel Spread: {vsa_res.relative_spread:.2f}x, Rel Volume: {vsa_res.relative_volume:.2f}x)")

    doc.append("\n## 5. Non-Parametric & Digital Filter Regimes")
    doc.append(f"- **Nadaraya-Watson Envelope (NWE):**")
    doc.append(f"  * Upper MAE Band: ₹{nwe_res.latest_upper:,.2f}")
    doc.append(f"  * Central Kernel Curve: ₹{nwe_res.latest_nwe:,.2f}")
    doc.append(f"  * Lower MAE Band: ₹{nwe_res.latest_lower:,.2f}")
    nwe_sig = "Extreme Overbought (Mean Reversion Short Bias)" if cmp >= nwe_res.latest_upper else (
        "Extreme Oversold (Mean Reversion Long Bias)" if cmp <= nwe_res.latest_lower else "Within Normal Statistical Distribution"
    )
    doc.append(f"  * Kernel Context: `{nwe_sig}`")
    doc.append(f"- **Savitzky-Golay Digital Filter:**")
    doc.append(f"  * Filter Value: ₹{sg_res.latest_sg:,.2f} | 1st Deriv (Slope): {sg_res.latest_slope:+.4f} | 2nd Deriv (Curvature): {sg_res.latest_curvature:+.6f}")
    sg_sig = "Bullish Turning Inflection" if sg_res.latest_turn_signal == 1 else (
        "Bearish Turning Inflection" if sg_res.latest_turn_signal == -1 else "Trend Continuation"
    )
    doc.append(f"  * Inflection Signal: `{sg_sig}`")

    doc.append("\n## 6. Classical Technical & Indicator Suite")
    doc.append("| Indicator | Value | Reference / Benchmark | Reading |")
    doc.append("| :--- | :--- | :--- | :--- |")
    doc.append(f"| RSI (14) | {rsi:.2f} | 30 / 70 Thresholds | {'Oversold' if rsi <= 30 else 'Overbought' if rsi >= 70 else 'Neutral/Bullish' if rsi >= 50 else 'Bearish'} |")
    doc.append(f"| ADX (14) | {adx:.2f} | 25.0 Trend Filter | {'Strong Trend Active' if adx >= 25 else 'Chop / Sideways Market'} |")
    doc.append(f"| ATR (14) | ₹{atr:,.2f} | Daily Volatility | {atr/cmp*100:.2f}% of price |")
    doc.append(f"| EMA (20) | ₹{ema_20:,.2f} | Short-term Momentum | {'Price Above (Bullish)' if cmp > ema_20 else 'Price Below (Bearish)'} |")
    doc.append(f"| SMA (50) | ₹{sma_50:,.2f} | Intermediate Trend | {'Price Above (Bullish)' if cmp > sma_50 else 'Price Below (Bearish)'} |")
    doc.append(f"| SMA (200) | ₹{sma_200:,.2f} | Secular Macro Trend | {'Price Above (Secular Bull)' if cmp > sma_200 else 'Price Below (Secular Bear)'} |")
    doc.append(f"| MACD (12,26,9) | Line: {macd:.2f}, Sig: {macd_sig:.2f} | Histogram: {macd_hist:.2f} | {'Bullish Crossover' if macd > macd_sig else 'Bearish Crossunder'} |")

    # 7. Quantitative Lens Reconciliation
    doc.extend(
        _build_reconciliation_section(
            cmp=cmp,
            smc_res=smc_res,
            w_res=w_res,
            nwe_res=nwe_res,
            sg_res=sg_res,
            vsa_res=vsa_res,
            ta_score_dict=ta_score_dict,
            sma_50=sma_50,
            sma_200=sma_200,
            vp_res=vp_res,
        )
    )

    # 8. Instructions for LLM Prompting / Strategy Formulation
    doc.append("\n## 8. Instructions for LLM Prompting / Strategy Formulation")
    doc.append(
        "> When reviewing this dossier, evaluate: (1) Does the SMC trade setup align with the macro Weinstein Stage and VPOC context? (2) Is volume confirming the move or showing exhaustion/no-demand? (3) Reconcile any Section 7 tactical vs. strategic tensions before formulating a thesis with position sizing and invalidation criteria."
    )

    return "\n".join(doc)
