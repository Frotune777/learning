import pandas as pd
import talib

from src.scanners.base import BaseStrategy


class CandlePatternsStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Candlestick Patterns"

    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Analyze for common candlestick patterns.
        Returns a dictionary or a specific pattern string if found.
        """
        if df.empty:
            return False

        # Ensure float64
        op = df["Open"].to_numpy(dtype=float)
        hi = df["High"].to_numpy(dtype=float)
        lo = df["Low"].to_numpy(dtype=float)
        cl = df["Close"].to_numpy(dtype=float)

        # Check patterns
        # 1. Doji
        doji = talib.CDLDOJI(op, hi, lo, cl)
        # 2. Engulfing
        engulfing = talib.CDLENGULFING(op, hi, lo, cl)
        # 3. Hammer
        hammer = talib.CDLHAMMER(op, hi, lo, cl)
        # 4. Shooting Star
        shooting_star = talib.CDLSHOOTINGSTAR(op, hi, lo, cl)
        # 5. Morning Star
        morning_star = talib.CDLMORNINGSTAR(op, hi, lo, cl)

        # Check standard lookback (e.g., last candle)
        idx = -1
        patterns = []

        if doji[idx] != 0:
            patterns.append("Doji")
        if engulfing[idx] == 100:
            patterns.append("Bullish Engulfing")
        elif engulfing[idx] == -100:
            patterns.append("Bearish Engulfing")
        if hammer[idx] != 0:
            patterns.append("Hammer")
        if shooting_star[idx] != 0:
            patterns.append("Shooting Star")
        if morning_star[idx] != 0:
            patterns.append("Morning Star")

        if patterns:
            pat_str = ", ".join(patterns)
            self.reason = pat_str
            return pat_str

        return False
