from typing import Any

import pandas as pd

from src.scanners.base import BaseStrategy


class VCPStrategy(BaseStrategy):
    """
    Minervini's Volatility Contraction Pattern (VCP) Strategy.
    Identifies stocks with tightening price action near highs.
    """

    def __init__(self, config: dict[str, Any] = None):
        super().__init__(config)
        self.description = "Minervini VCP Pattern"
        self.lookback_days = 250  # ~1 year
        self.swing_window = 5  # Window to find relative highs/lows

    def analyze(self, df: pd.DataFrame) -> bool:
        if df is None or len(df) < self.lookback_days:
            self.reason = f"Insufficient data ({len(df)} < {self.lookback_days})"
            return False

        try:
            # Screenipy data is reversed (iloc[0] is latest)
            # For swing detection, chronological order is easier
            data = df.iloc[::-1].copy()

            # 1. Trend Filter (Mark Minervini's Trend Template basic rules)
            current_price = data["Close"].iloc[-1]
            ema_50 = (
                data["SMA_50"].iloc[-1]
                if "SMA_50" in data.columns and not pd.isna(data["SMA_50"].iloc[-1])
                else data["Close"].rolling(50).mean().iloc[-1]
            )
            ema_200 = (
                data["SMA_200"].iloc[-1]
                if "SMA_200" in data.columns and not pd.isna(data["SMA_200"].iloc[-1])
                else data["Close"].rolling(200).mean().iloc[-1]
            )

            if current_price < ema_50 or current_price < ema_200:
                self.reason = "Price below EMA 50 or EMA 200 (Not in Stage 2 Uptrend)"
                return False

            # 2. Proximity to 52-Week High
            yearly_high = data["High"].tail(250).max()
            if current_price < 0.75 * yearly_high:
                self.reason = f"Price too far from 52w High ({current_price:.2f} < 75% of {yearly_high:.2f})"
                return False

            # 3. Volatility Contraction Detection (Simple swing-based)
            # Find recent peaks (local highs)
            # Using a rolling window to detect peaks
            data["Peak"] = data["High"].rolling(self.swing_window, center=True).max()
            peaks = data[data["High"] == data["Peak"]].tail(4)  # Get last 4 peaks

            if len(peaks) < 3:
                self.reason = "Not enough price peaks found to detect contraction"
                return False

            # Find lows between these peaks to calculate consolidation legs
            legs = []
            for i in range(len(peaks) - 1):
                start_idx = peaks.index[i]
                end_idx = peaks.index[i + 1]
                leg_data = data.loc[start_idx:end_idx]
                peak_val = peaks["High"].iloc[i]
                low_val = leg_data["Low"].min()
                contraction = (peak_val - low_val) / peak_val * 100
                legs.append(contraction)

            # VCP Requirement: Consecutive legs should be smaller (tightening)
            # Example: 20% -> 10% -> 5%
            is_tightening = True
            for i in range(len(legs) - 1):
                if (
                    legs[i + 1] > legs[i] * 1.1
                ):  # Allow for slight non-linear tightening (10% buffer)
                    is_tightening = False
                    break

            if is_tightening and legs[-1] < 10:  # Final leg should be tight (< 10%)
                legs_str = ", ".join([f"{leg_pct:.1f}%" for leg_pct in legs])
                self.reason = f"VCP Tightening Detected: Legs({legs_str})"
                return True

            legs_str = ", ".join([f"{leg_pct:.1f}%" for leg_pct in legs])
            self.reason = f"No VCP (Legs: {legs_str})"
            return False

        except Exception as e:
            self.reason = f"VCP Error: {str(e)}"
            return False

    def get_description(self) -> str:
        return self.description
