import pandas as pd

from screeni.strategies.BaseStrategy import BaseStrategy


class InsideBarStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Inside Bar Pattern"
        self.days_to_lookback = config.get("daysToLookback", 5) if config else 5

    def analyze(self, df: pd.DataFrame) -> bool:
        if df.empty or len(df) < 2:
            return False

        # Screenipy data is reversed (iloc[0] is latest)
        today = df.iloc[0]
        yesterday = df.iloc[1]

        is_inside = (today["High"] < yesterday["High"]) and (
            today["Low"] > yesterday["Low"]
        )
        if is_inside:
            self.reason = "Inside Bar (H < Prev H, L > Prev L)"
            return True
        return False


class IPOBaseStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "IPO Base Pattern"
        self.days_to_lookback = 200  # IPO is usually new

    def analyze(self, df: pd.DataFrame) -> bool:
        if df.empty:
            return False

        # Screenipy data is reversed (iloc[0] is latest)
        recent = df.iloc[0]
        all_time_high = df["High"].max()

        # Within 20% of ATH
        if recent["Close"] >= (all_time_high * 0.8):
            self.reason = f"Near ATH ({(recent['Close'] / all_time_high) * 100:.1f}%)"
            return True
        return False
