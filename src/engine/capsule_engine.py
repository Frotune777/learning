"""
File: src/engine/capsule_engine.py
Purpose: Capsule Academy 5-Star Framework, Train No. 920/130 & Smart Money Capsule 1.0.
Authored based on Dr. Nayeem Ahmad Shariff's 5-Star Study & SMC Booklet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (Wilder's RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def compute_cci(df: pd.DataFrame, period: int = 30, smoothing: int = 5) -> tuple[pd.Series, pd.Series]:
    """Calculate Commodity Channel Index (CCI) and its smoothed Signal."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))
    cci_signal = cci.ewm(span=smoothing, adjust=False).mean()
    return cci.fillna(0.0), cci_signal.fillna(0.0)


def compute_macd_hist(series: pd.Series) -> pd.Series:
    """Calculate MACD Histogram (12, 26, 9)."""
    fast = series.ewm(span=12, adjust=False).mean()
    slow = series.ewm(span=26, adjust=False).mean()
    macd_line = fast - slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line - signal_line


def add_capsule_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich an OHLCV DataFrame with all technical indicators required by Capsule Academy."""
    d = df.copy()
    c = d["Close"]

    # Key EMAs: 7, 9, 20, 200
    d["EMA7"] = compute_ema(c, 7)
    d["EMA9"] = compute_ema(c, 9)
    d["EMA20"] = compute_ema(c, 20)
    if len(d) >= 200:
        d["EMA200"] = compute_ema(c, 200)
    else:
        d["EMA200"] = np.nan

    # 9/20 EMA Cross Signals
    d["EMA9_gt_EMA20"] = d["EMA9"] > d["EMA20"]
    d["EMA9_20_CrossOver"] = (d["EMA9"] > d["EMA20"]) & (d["EMA9"].shift(1) <= d["EMA20"].shift(1))
    d["EMA9_20_CrossDown"] = (d["EMA9"] < d["EMA20"]) & (d["EMA9"].shift(1) >= d["EMA20"].shift(1))

    # MACD Histogram (12, 26, 9)
    d["MACD_Hist"] = compute_macd_hist(c)

    # CCI 30/5 and 30/7
    d["CCI_30_5"], d["CCI_30_5_Sig"] = compute_cci(d, period=30, smoothing=5)
    d["CCI_30_7"], d["CCI_30_7_Sig"] = compute_cci(d, period=30, smoothing=7)

    # RSI (14)
    d["RSI14"] = compute_rsi(c, 14)

    # Simple Turnover: Volume * Price & 20-period average turnover
    vol = d["Volume"] if "Volume" in d.columns else pd.Series(0, index=d.index)
    d["Simple_Turnover"] = vol * c
    d["Avg_Turnover_20"] = vol.rolling(20).mean() * c
    d["Turnover_Surge_Pct"] = (
        (d["Simple_Turnover"] - d["Simple_Turnover"].shift(1))
        / d["Simple_Turnover"].shift(1).replace(0, np.nan)
        * 100.0
    ).fillna(0.0)

    return d


def resample_timeframes(df_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resample daily OHLCV into Weekly (Fri close) and Monthly (Month-end) bars."""
    agg_rules = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    cols = [col for col in agg_rules if col in df_daily.columns]
    sub_agg = {col: agg_rules[col] for col in cols}

    weekly = df_daily.resample("W-FRI").agg(sub_agg).dropna(subset=["Close"])
    monthly = df_daily.resample("ME").agg(sub_agg).dropna(subset=["Close"])

    return weekly, monthly


def resample_to_3h(df_hourly: pd.DataFrame) -> pd.DataFrame:
    """Resample 1H OHLCV into 3H bars for Seeds Order Block overlap."""
    if df_hourly is None or df_hourly.empty:
        return pd.DataFrame()
    agg_rules = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }
    cols = [col for col in agg_rules if col in df_hourly.columns]
    return df_hourly.resample("3h").agg({c: agg_rules[c] for c in cols}).dropna(subset=["Close"])


@dataclass
class CapsuleAnalysisResult:
    """Comprehensive analysis score and setup flags for one symbol."""

    symbol: str
    close: float
    # 5 Stars Breakdown
    star_monthly_farms: bool = False
    star_weekly_sunflowers: bool = False
    star_daily_seeds: bool = False
    star_turnover_surge: bool = False
    star_fundamentals_ok: bool = True
    total_stars: int = 0

    # Train No. 920/130 Momentum Setup
    train_920130_boarding: bool = False
    train_920130_reasons: list[str] = field(default_factory=list)

    # Timeframe mode & 1H Intraday execution
    tf_mode: str = "1D_FALLBACK"  # "1H" or "1D_FALLBACK"
    hourly_ema9_gt_ema20: bool = False
    hourly_crossover: bool = False
    hourly_above_ema200: bool = False
    hourly_turnover_surge: bool = False
    seeds_3h_overlap: bool = False

    # SMC Capsule Setup
    smc_spring: bool = False
    smc_ifc_candle: bool = False
    smc_ob_overlap: str = "None"  # "Farms" (M+W), "Sunflowers" (W+D), or "None"
    smc_fvg_discount: bool = False

    # Detailed metrics
    rsi_daily: float = 0.0
    rsi_weekly: float = 0.0
    rsi_monthly: float = 0.0
    ema9_above_ema20: bool = False
    above_ema200: bool = False
    turnover_surge_pct: float = 0.0
    recommended_action: str = "WATCH"
    stop_loss: float = 0.0
    target_price: float = 0.0


def analyze_capsule_strategy(
    symbol: str,
    df_daily: pd.DataFrame,
    df_hourly: pd.DataFrame | None = None,
) -> CapsuleAnalysisResult | None:
    """Run full Capsule Academy 5-Star + Train No. 920/130 + SMC evaluation on a single stock."""
    if df_daily.empty or len(df_daily) < 60:
        return None

    # 1. Enrich Daily
    df_d = add_capsule_indicators(df_daily)
    last_d = df_d.iloc[-1]
    prev_d = df_d.iloc[-2] if len(df_d) >= 2 else last_d

    # 2. Resample & Enrich Weekly and Monthly
    df_w, df_m = resample_timeframes(df_daily)
    if len(df_w) < 20 or len(df_m) < 6:
        return None

    df_w = add_capsule_indicators(df_w)
    df_m = add_capsule_indicators(df_m)

    last_w = df_w.iloc[-1]
    prev_w = df_w.iloc[-2]
    last_m = df_m.iloc[-1]
    prev_m = df_m.iloc[-2]

    res = CapsuleAnalysisResult(
        symbol=symbol.upper(),
        close=float(last_d["Close"]),
        rsi_daily=float(last_d["RSI14"]),
        rsi_weekly=float(last_w["RSI14"]),
        rsi_monthly=float(last_m["RSI14"]),
        ema9_above_ema20=bool(last_d["EMA9_gt_EMA20"]),
        above_ema200=bool(not np.isnan(last_d["EMA200"]) and last_d["Close"] > last_d["EMA200"]),
        turnover_surge_pct=float(last_d["Turnover_Surge_Pct"]),
    )

    # -------------------------------------------------------------
    # 1H INTRADAY METRICS EVALUATION (When 1H Parquet Available)
    # -------------------------------------------------------------
    has_1h = df_hourly is not None and not df_hourly.empty and len(df_hourly) >= 10
    if has_1h:
        res.tf_mode = "1H"
        df_h = add_capsule_indicators(df_hourly)
        last_h = df_h.iloc[-1]
        prev_h = df_h.iloc[-2] if len(df_h) >= 2 else last_h

        res.hourly_ema9_gt_ema20 = bool(last_h["EMA9_gt_EMA20"])
        res.hourly_crossover = bool(df_h["EMA9_20_CrossOver"].iloc[-5:].any())
        h_ema200 = last_h["EMA200"]
        res.hourly_above_ema200 = (
            bool(not np.isnan(h_ema200) and last_h["Close"] > h_ema200)
            if (len(df_h) >= 200 and not np.isnan(h_ema200))
            else bool(last_h["Close"] > last_h["EMA20"])
        )

        # 1H Simple Turnover Surge (>= +50% over prior 1H bar)
        h_surge = (
            last_h["Simple_Turnover"] >= 1.50 * prev_h["Simple_Turnover"]
            and last_h["Volume"] >= prev_h["Volume"]
            and last_h["Close"] >= 20.0
        )
        res.hourly_turnover_surge = bool(h_surge)
        res.turnover_surge_pct = float(last_h["Turnover_Surge_Pct"])
        res.star_turnover_surge = bool(h_surge)

        # 3H Resampling for Seeds Overlap
        df_3h = resample_to_3h(df_hourly)
        if len(df_3h) >= 5:
            df_3h = add_capsule_indicators(df_3h)
            res.seeds_3h_overlap = bool(df_3h["Close"].iloc[-1] > df_3h["EMA9"].iloc[-1])
    else:
        res.tf_mode = "1D_FALLBACK"
        # 1D approximation for turnover surge
        if (
            last_d["Simple_Turnover"] >= 1.5 * prev_d["Simple_Turnover"]
            and last_d["Volume"] >= prev_d["Volume"]
            and last_d["Close"] >= 20.0
        ):
            res.star_turnover_surge = True

    # -------------------------------------------------------------
    # STAR 1: MONTHLY (FARMS)
    # -------------------------------------------------------------
    m_hist_pos = last_m["MACD_Hist"] > 0
    m_hist_growing = m_hist_pos and (last_m["MACD_Hist"] >= prev_m["MACD_Hist"])
    m_cci_pos = last_m["CCI_30_5"] > 0
    m_ema9_ok = last_m["Close"] > last_m["EMA9"]
    m_ema200_ok = np.isnan(last_m["EMA200"]) or (last_m["Close"] > last_m["EMA200"])
    m_ema_co = last_m["EMA9_gt_EMA20"]
    m_rsi_ok = last_m["RSI14"] >= 60

    m_conditions_met = sum([m_hist_growing, m_cci_pos, m_ema9_ok, m_ema200_ok, m_ema_co, m_rsi_ok])
    if m_conditions_met >= 4:
        res.star_monthly_farms = True

    # -------------------------------------------------------------
    # STAR 2: WEEKLY (SUNFLOWERS)
    # -------------------------------------------------------------
    w_hist_pos = last_w["MACD_Hist"] > 0
    w_cci_pos = last_w["CCI_30_5"] > 0
    w_ema9_ok = last_w["Close"] > last_w["EMA9"]
    w_ema200_ok = np.isnan(last_w["EMA200"]) or (last_w["Close"] > last_w["EMA200"])
    w_ema_co = last_w["EMA9_gt_EMA20"]
    w_rsi_ok = last_w["RSI14"] >= 55

    w_conditions_met = sum([w_hist_pos, w_cci_pos, w_ema9_ok, w_ema200_ok, w_ema_co, w_rsi_ok])
    if w_conditions_met >= 4 and w_ema200_ok:
        res.star_weekly_sunflowers = True

    # -------------------------------------------------------------
    # STAR 3: DAILY (DAILY SEEDS / SWING)
    # -------------------------------------------------------------
    d_ema200_must = not np.isnan(last_d["EMA200"]) and (last_d["Close"] > last_d["EMA200"])
    d_cci_co = last_d["CCI_30_5"] > 0 or last_d["CCI_30_5"] > last_d["CCI_30_5_Sig"]
    d_hist_pos = last_d["MACD_Hist"] > 0
    d_ema7_ok = last_d["Close"] > last_d["EMA7"]
    d_rsi_ok = last_d["RSI14"] >= 50

    d_score = sum([d_cci_co, d_hist_pos, d_ema7_ok, d_rsi_ok])
    if d_ema200_must and d_score >= 2:
        res.star_daily_seeds = True

    # Total Stars count
    stars = [
        res.star_monthly_farms,
        res.star_weekly_sunflowers,
        res.star_daily_seeds,
        res.star_turnover_surge,
        res.star_fundamentals_ok,
    ]
    res.total_stars = sum(1 for s in stars if s)

    # -------------------------------------------------------------
    # TRAIN NO. 920/130 MOMENTUM TRADING SETUP
    # -------------------------------------------------------------
    train_reasons = []
    if d_ema200_must and last_d["CCI_30_7"] > 0:
        train_reasons.append("CCI 30/7 & Price > EMA 200")

    rsi_day_ok = 40.0 <= last_d["RSI14"] <= 65.0
    rsi_week_ok = 45.0 <= last_w["RSI14"] <= 65.0
    rsi_month_ok = 50.0 <= last_m["RSI14"] <= 70.0
    if rsi_day_ok and rsi_week_ok and rsi_month_ok:
        train_reasons.append("Multi-TF RSI Aligned (Day:45±5, Wk:50±5, Mo:55±5)")

    ema9_all_positive = (last_d["Close"] > last_d["EMA9"]) and (last_w["Close"] > last_w["EMA9"]) and (last_m["Close"] > last_m["EMA9"])
    if ema9_all_positive:
        train_reasons.append("EMA 9 Positive in Day, Week & Month")

    if has_1h:
        if res.hourly_ema9_gt_ema20 and res.hourly_above_ema200:
            train_reasons.append("1H 9/20 EMA Crossover above 200 EMA")
        if (
            (res.hourly_ema9_gt_ema20 or res.hourly_crossover)
            and res.hourly_above_ema200
            and d_ema200_must
            and len(train_reasons) >= 3
        ):
            res.train_920130_boarding = True
            res.train_920130_reasons = train_reasons
    else:
        if last_d["EMA9_gt_EMA20"]:
            train_reasons.append("9/20 EMA Bullish Alignment (1D Approximation)")
        if len(train_reasons) >= 3 and d_ema200_must:
            res.train_920130_boarding = True
            res.train_920130_reasons = train_reasons

    # -------------------------------------------------------------
    # SMART MONEY CAPSULE: WYCKOFF SPRING & IFC CANDLE
    # -------------------------------------------------------------
    lows_20 = df_d["Low"].iloc[-21:-1].min()
    if last_d["Low"] < lows_20 and last_d["Close"] > lows_20:
        body = abs(last_d["Close"] - last_d["Open"])
        lower_wick = min(last_d["Close"], last_d["Open"]) - last_d["Low"]
        if lower_wick >= 1.2 * body:
            res.smc_spring = True

    if prev_d["Close"] < prev_d["Open"] and last_d["Close"] > prev_d["High"] and last_d["Simple_Turnover"] > last_d["Avg_Turnover_20"]:
        res.smc_ifc_candle = True

    # Order Block Overlap Check
    if res.star_monthly_farms and res.star_weekly_sunflowers:
        res.smc_ob_overlap = "Farms (Monthly + Weekly)"
    elif res.star_weekly_sunflowers and res.star_daily_seeds:
        res.smc_ob_overlap = "Sunflowers (Weekly + Daily)"
    elif res.star_daily_seeds and res.seeds_3h_overlap:
        res.smc_ob_overlap = "Seeds (Daily + 3H Overlap)"
    elif res.star_daily_seeds:
        res.smc_ob_overlap = "Seeds (Daily Active)"

    # Recommended Action & Stop Loss
    if res.train_920130_boarding or res.total_stars >= 3:
        res.recommended_action = "BUY / BOARD"
        sl = min(float(last_d["Low"]), float(last_d["EMA20"]) if not np.isnan(last_d["EMA20"]) else float(last_d["Low"]))
        res.stop_loss = round(sl * 0.98, 2)
        res.target_price = round(res.close * 1.15, 2)
    elif res.total_stars >= 2:
        res.recommended_action = "ACCUMULATE"
        res.stop_loss = round(res.close * 0.95, 2)
        res.target_price = round(res.close * 1.10, 2)
    else:
        res.recommended_action = "WATCH"

    return res

    # -------------------------------------------------------------
    # SMART MONEY CAPSULE: WYCKOFF SPRING & IFC CANDLE
    # -------------------------------------------------------------
    # Wyckoff Spring: False breakdown of 20-day swing low, reclaimed with lower wick hammer
    lows_20 = df_d["Low"].iloc[-21:-1].min()
    if last_d["Low"] < lows_20 and last_d["Close"] > lows_20:
        body = abs(last_d["Close"] - last_d["Open"])
        lower_wick = min(last_d["Close"], last_d["Open"]) - last_d["Low"]
        if lower_wick >= 1.2 * body:
            res.smc_spring = True

    # Institutional Funding Candle (IFC): Bearish wick sweeping recent liquidity then strong close
    if prev_d["Close"] < prev_d["Open"] and last_d["Close"] > prev_d["High"] and last_d["Simple_Turnover"] > last_d["Avg_Turnover_20"]:
        res.smc_ifc_candle = True

    # Order Block Overlap Check
    if res.star_monthly_farms and res.star_weekly_sunflowers:
        res.smc_ob_overlap = "Farms (Monthly + Weekly)"
    elif res.star_weekly_sunflowers and res.star_daily_seeds:
        res.smc_ob_overlap = "Sunflowers (Weekly + Daily)"
    elif res.star_daily_seeds:
        res.smc_ob_overlap = "Seeds (Daily Active)"

    # Recommended Action & Stop Loss
    if res.train_920130_boarding or res.total_stars >= 3:
        res.recommended_action = "BUY / BOARD"
        # Stop loss below EMA 200 or recent 10-day low
        sl = min(float(last_d["Low"]), float(last_d["EMA20"]) if not np.isnan(last_d["EMA20"]) else float(last_d["Low"]))
        res.stop_loss = round(sl * 0.98, 2)
        res.target_price = round(res.close * 1.15, 2)
    elif res.total_stars >= 2:
        res.recommended_action = "ACCUMULATE"
        res.stop_loss = round(res.close * 0.95, 2)
        res.target_price = round(res.close * 1.10, 2)
    else:
        res.recommended_action = "WATCH"

    return res
