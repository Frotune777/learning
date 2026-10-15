import numpy as np
import pandas as pd

from screeni.strategies.BaseStrategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Breakout Detection with Proximity Signals"
        self.lookback = config.get("daysToLookback", 30) if config else 30

    def analyze(self, df: pd.DataFrame) -> bool:
        """
        Enhanced Breakout Detection with Actionable Proximity Signals.
        Returns: True if breaking out or near breakout
        Sets self.reason with actionable signal
        """
        if df.empty or len(df) < 10:
            return False

        try:
            # Get recent high (excluding today) - df is chronological
            lookback_high = (
                df["High"].iloc[:-1].max()
            )  # Last N days high (excluding current)
            current_close = df["Close"].iloc[-1]  # Most recent close
            df["High"].iloc[-1]

            # Calculate distance to breakout
            if np.isnan(current_close) or np.isnan(lookback_high) or current_close == 0:
                self.reason = "Insufficient Data"
                return False

            distance_pct = ((lookback_high - current_close) / current_close) * 100
            if np.isnan(distance_pct):
                distance_pct = 0.0

            # Actionable Signals
            if current_close > lookback_high:
                self.reason = "Breaking Out Now! 🚀"
                return True
            elif distance_pct <= 1.0:  # Within 1% of breakout
                self.reason = f"Near Breakout (Watch) - {distance_pct:.1f}% away"
                return True
            elif distance_pct <= 3.0:  # Within 3% - Get Ready
                self.reason = f"Get Ready - {distance_pct:.1f}% to breakout"
                return False  # Not yet, but close
            elif current_close < lookback_high * 0.95:  # More than 5% below
                self.reason = "Consolidating"
                return False
            else:
                self.reason = f"Watching - {distance_pct:.1f}% below high"
                return False

        except Exception:
            return False
