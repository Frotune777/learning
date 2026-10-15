from typing import Any, Dict

import pandas as pd

from screeni.strategies.BaseStrategy import BaseStrategy


class TTMSqueezeStrategy(BaseStrategy):
    """
    TTM Squeeze Strategy.
    Identifies periods of low volatility (Bollinger Bands inside Keltner Channels)
    which often precede explosive moves.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.description = "TTM Squeeze"
        self.period = 20
        self.bb_mult = 2.0
        self.kc_mult = 1.5

    def analyze(self, df: pd.DataFrame) -> bool:
        if df is None or len(df) < self.period + 14:  # +14 for ATR
            self.reason = "Insufficient data for TTM Squeeze"
            return False

        try:
            # Screenipy data is reversed (iloc[0] is latest)
            # Need chronological for rolling calcs
            data = df.iloc[::-1].copy()

            # 1. Bollinger Bands
            data["SMA20"] = data["Close"].rolling(self.period).mean()
            data["StdDev"] = data["Close"].rolling(self.period).std()
            data["BB_Upper"] = data["SMA20"] + (self.bb_mult * data["StdDev"])
            data["BB_Lower"] = data["SMA20"] - (self.bb_mult * data["StdDev"])

            # 2. Keltner Channels
            # KC = SMA(20) +/- 1.5 * ATR(20)
            # Using ATR from Screener if available, else calc
            if "ATR" not in data.columns:
                high_low = data["High"] - data["Low"]
                high_pc = abs(data["High"] - data["Close"].shift(1))
                low_pc = abs(data["Low"] - data["Close"].shift(1))
                tr = pd.concat([high_low, high_pc, low_pc], axis=1).max(axis=1)
                data["ATR"] = tr.rolling(self.period).mean()

            data["KC_Upper"] = data["SMA20"] + (self.kc_mult * data["ATR"])
            data["KC_Lower"] = data["SMA20"] - (self.kc_mult * data["ATR"])

            # 3. Squeeze Check (Current Candle)
            bb_u = data["BB_Upper"].iloc[-1]
            bb_l = data["BB_Lower"].iloc[-1]
            kc_u = data["KC_Upper"].iloc[-1]
            kc_l = data["KC_Lower"].iloc[-1]

            is_squeeze = (bb_u < kc_u) and (bb_l > kc_l)

            # 4. Momentum (Optional but good for direction)
            # TTM Squeeze usually uses a momentum histogram (e.g., price vs linear regression line)
            # Simple momentum: Price vs SMA20
            momentum = data["Close"].iloc[-1] - data["SMA20"].iloc[-1]

            if is_squeeze:
                direction = "Bullish Bias" if momentum > 0 else "Bearish Bias"
                self.reason = f"TTM Squeeze Active ({direction})"
                return True

            self.reason = "No Squeeze (Bands outside Keltner Channels)"
            return False

        except Exception as e:
            self.reason = f"TTM Squeeze Error: {str(e)}"
            return False

    def get_description(self) -> str:
        return self.description
