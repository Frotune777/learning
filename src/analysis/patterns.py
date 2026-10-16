"""
File: src/classes/SMCPatterns.py
Purpose: Smart Money Concepts (SMC) Patterns - Optimized for performance

Dependencies:
External:
- pandas>=2.0.0: [data handling]
- numpy>=1.20.0: [vectorized calculations]
Internal:
- None

Key Components:
Classes:
- SMCPatterns: Detects BOS, CHOCH, Order Blocks, and FVG using vectorized logic
- WilliamsFractals: Detects pivot highs and lows using Williams formula
Functions:
- analyze_smc: Aggregates all SMC patterns for a stock
- analyze_fractals: Aggregates all fractal signals for a stock

Last Modified: 2026-02-19
Modified By: LLM

Open Tasks:
- [ ] [LOW] Add liquidity void detection
- [ ] [MEDIUM] Implement complex market structure mapping (internal vs swing)
"""


import pandas as pd


class SMCPatterns:
    """
    Smart Money Concepts pattern detection - Vectorized for high-scale scanning
    """

    @staticmethod
    def detect_bos(data: pd.DataFrame, lookback: int = 20) -> pd.Series:
        """Detect Break of Structure (BOS) - Vectorized"""
        bos_signals = pd.Series(index=data.index, dtype=object)

        # Calculate rolling highs and lows
        rolling_high = data["High"].rolling(window=lookback).max().shift(1)
        rolling_low = data["Low"].rolling(window=lookback).min().shift(1)

        # Bullish BOS: Close breaks above previous high
        bullish_bos = data["Close"] > rolling_high
        # Bearish BOS: Close breaks below previous low
        bearish_bos = data["Close"] < rolling_low

        bos_signals[bullish_bos] = "Bullish BOS"
        bos_signals[bearish_bos] = "Bearish BOS"

        return bos_signals

    @staticmethod
    def detect_choch(data: pd.DataFrame, lookback: int = 10) -> pd.Series:
        """Detect Change of Character (CHOCH) - Vectorized"""
        signals = pd.Series(index=data.index, dtype=object)

        # Calculate trend indicators
        prev_high_max = data["High"].rolling(lookback).max().shift(1)
        prev_low_min = data["Low"].rolling(lookback).min().shift(1)

        # Was in uptrend? (Simplified definition for CHOCH)
        was_uptrend = data["High"].shift(1) == prev_high_max
        was_downtrend = data["Low"].shift(1) == prev_low_min

        # CHOCH: Trend breaks (opposite movement after trend)
        bearish_choch = was_uptrend & (data["Low"] < prev_low_min)
        bullish_choch = was_downtrend & (data["High"] > prev_high_max)

        signals[bearish_choch] = "Bearish CHOCH"
        signals[bullish_choch] = "Bullish CHOCH"

        return signals

    @staticmethod
    def detect_order_blocks(
        data: pd.DataFrame, threshold: float = 0.02
    ) -> pd.DataFrame:
        """
        Detect Order Blocks - Vectorized candidate identification with same-bar confirmation.
        Semantics follow LuxAlgo SMC: confirmation is evaluated on the current bar close vs prior close,
        eliminating any lookahead (shift(-1)).
        """
        prev_close = data["Close"].shift(1)
        move_pct = abs(data["Close"] - prev_close) / prev_close

        # Identification masks (evaluated at bar i relative to prior bar i-1)
        bull_mask = (
            (move_pct >= threshold)
            & (data["Close"] > prev_close)
            & (data["Close"] > data["Open"])
        )
        bear_mask = (
            (move_pct >= threshold)
            & (data["Close"] < prev_close)
            & (data["Close"] < data["Open"])
        )

        obs = []
        for idx in data.index[bull_mask]:
            row = data.loc[idx]
            obs.append(
                {
                    "Date": idx,
                    "Type": "Bullish OB",
                    "High": row["High"],
                    "Low": row["Low"],
                    "Zone_Top": row["High"],
                    "Zone_Bottom": row["Open"],
                }
            )

        for idx in data.index[bear_mask]:
            row = data.loc[idx]
            obs.append(
                {
                    "Date": idx,
                    "Type": "Bearish OB",
                    "High": row["High"],
                    "Low": row["Low"],
                    "Zone_Top": row["Open"],
                    "Zone_Bottom": row["Low"],
                }
            )

        return pd.DataFrame(obs)

    @staticmethod
    def detect_fvg(data: pd.DataFrame) -> pd.DataFrame:
        """
        Detect Fair Value Gaps (FVG) - Vectorized 3-bar past window (i-2, i-1, i).
        Evaluated strictly at current bar i without future lookahead (shift(-1)).
        """
        p2_high = data["High"].shift(2)
        p2_low = data["Low"].shift(2)

        bull_fvg_mask = (data["Low"] > p2_high) & p2_high.notna()
        bear_fvg_mask = (data["High"] < p2_low) & p2_low.notna()

        fvgs = []
        for idx in data.index[bull_fvg_mask]:
            fvgs.append(
                {
                    "Date": idx,
                    "Type": "Bullish FVG",
                    "Gap_Top": data.loc[idx, "Low"],
                    "Gap_Bottom": p2_high[idx],
                    "Gap_Size": data.loc[idx, "Low"] - p2_high[idx],
                }
            )

        for idx in data.index[bear_fvg_mask]:
            fvgs.append(
                {
                    "Date": idx,
                    "Type": "Bearish FVG",
                    "Gap_Top": p2_low[idx],
                    "Gap_Bottom": data.loc[idx, "High"],
                    "Gap_Size": p2_low[idx] - data.loc[idx, "High"],
                }
            )

        return pd.DataFrame(fvgs)

    @staticmethod
    def detect_liquidity_grab(data: pd.DataFrame, lookback: int = 20) -> pd.Series:
        """Detect Liquidity Grab / Stop Hunt - Vectorized"""
        signals = pd.Series(index=data.index, dtype=object)

        r_high = data["High"].rolling(window=lookback).max().shift(1)
        r_low = data["Low"].rolling(window=lookback).min().shift(1)

        # Bullish Grab: Low < prev_low AND Close > prev_low
        bull_grab = (data["Low"] < r_low) & (data["Close"] > r_low)
        # Bearish Grab: High > prev_high AND Close < prev_high
        bear_grab = (data["High"] > r_high) & (data["Close"] < r_high)

        signals[bull_grab] = "Bullish Grab"
        signals[bear_grab] = "Bearish Grab"

        return signals

    @staticmethod
    def detect_cisd(data: pd.DataFrame) -> pd.Series:
        """Detect Change in State of Delivery (CISD) - Vectorized"""
        signals = pd.Series(index=data.index, dtype=object)

        p_close, p_open, p_high, p_low = (
            data["Close"].shift(1),
            data["Open"].shift(1),
            data["High"].shift(1),
            data["Low"].shift(1),
        )

        bull_cisd = (p_close < p_open) & (data["Close"] > p_high)
        bear_cisd = (p_close > p_open) & (data["Close"] < p_low)

        signals[bull_cisd] = "Bullish CISD"
        signals[bear_cisd] = "Bearish CISD"

        return signals

    @staticmethod
    def analyze_smc(data: pd.DataFrame) -> dict:
        """Complete SMC analysis"""
        result = {
            "BOS": SMCPatterns.detect_bos(data),
            "CHOCH": SMCPatterns.detect_choch(data),
            "Order_Blocks": SMCPatterns.detect_order_blocks(data),
            "FVG": SMCPatterns.detect_fvg(data),
            "Liquidity": SMCPatterns.detect_liquidity_grab(data),
            "CISD": SMCPatterns.detect_cisd(data),
        }

        # Get latest signals
        latest_bos = result["BOS"].dropna().tail(1)
        latest_choch = result["CHOCH"].dropna().tail(1)
        latest_liq = result["Liquidity"].dropna().tail(1)
        latest_cisd = result["CISD"].dropna().tail(1)

        result["Latest_BOS"] = latest_bos.iloc[0] if not latest_bos.empty else None
        result["Latest_CHOCH"] = (
            latest_choch.iloc[0] if not latest_choch.empty else None
        )
        result["Latest_Grab"] = latest_liq.iloc[0] if not latest_liq.empty else None
        result["Latest_CISD"] = latest_cisd.iloc[0] if not latest_cisd.empty else None

        result["Active_Order_Blocks"] = len(result["Order_Blocks"])
        result["Active_FVG"] = len(result["FVG"])

        return result


class WilliamsFractals:
    """
    Williams Fractals pattern detection - Vectorized
    """

    @staticmethod
    def detect_fractals(data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """
        Detect Williams Fractals - Vectorized without lookahead.
        The 5-bar fractal definition (peak/trough at bar i-2 compared to bars i-4, i-3, i-1, and i)
        is confirmed and recorded at confirmation bar i, eliminating future bar references.
        """
        high = data["High"]
        low = data["Low"]

        # 5-bar confirmation at bar i: candidate peak is at bar i-2
        peak = high.shift(2)
        trough = low.shift(2)

        bull_mask = (
            (peak > high.shift(4))
            & (peak > high.shift(3))
            & (peak > high.shift(1))
            & (peak > high)
        )
        bear_mask = (
            (trough < low.shift(4))
            & (trough < low.shift(3))
            & (trough < low.shift(1))
            & (trough < low)
        )

        f_highs = pd.Series(index=data.index, dtype=float)
        f_lows = pd.Series(index=data.index, dtype=float)

        f_highs[bull_mask] = peak[bull_mask]
        f_lows[bear_mask] = trough[bear_mask]

        return f_highs, f_lows

    @staticmethod
    def analyze_fractals(data: pd.DataFrame) -> dict:
        """Complete fractal analysis"""
        highs, lows = WilliamsFractals.detect_fractals(data)
        r_highs = highs.dropna().tail(3)
        r_lows = lows.dropna().tail(3)

        return {
            "Fractal_Highs": highs,
            "Fractal_Lows": lows,
            "Recent_Fractal_Highs": r_highs.tolist(),
            "Recent_Fractal_Lows": r_lows.tolist(),
            "Last_Fractal_High": r_highs.iloc[-1] if not r_highs.empty else None,
            "Last_Fractal_Low": r_lows.iloc[-1] if not r_lows.empty else None,
        }
