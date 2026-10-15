import numpy as np
import pandas as pd

from screeni.strategies.BaseStrategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Mean Reversion Strategy"
        self.ma_length = config.get("maLength", 50) if config else 50
        self.deviation = 0.03  # 3% deviation

    def analyze(self, df: pd.DataFrame) -> bool:
        if df.empty or "Close" not in df.columns:
            return False

        # Logic: Price deviated significantly from MA and likely to return?
        # Or Price touches lower band (Bollinger)?
        # Simple Mean Reversion: Price < SMA * (1 - deviation) -> Oversold

        # Need SMA.
        # If 'SMA' column exists use it, else calc.
        cols = df.columns
        sma_col = f"SMA_{self.ma_length}"

        if sma_col not in cols:
            # We don't have access to AnalyticsService here easily unless passed.
            # But df should have indicators calculated.
            # Fallback calculate
            sma = df["Close"].rolling(window=self.ma_length).mean()
        else:
            sma = df[sma_col]

        current_price = df["Close"].iloc[-1]
        current_sma = sma.iloc[-1]

        if np.isnan(current_sma):
            return False

        # Buy signal: Price is significantly below SMA
        # Buy signal: Price is significantly below SMA
        if current_price < (current_sma * (1 - self.deviation)):
            self.reason = f"Price ({current_price:.2f}) < SMA ({current_sma:.2f}) by 3%"
            return True
        return False


class TrendlineStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Trendline Support Strategy"
        self.lookback = 30  # Days to check for trend

    def analyze(self, df: pd.DataFrame) -> bool:
        if df.empty or len(df) < self.lookback:
            return False

        # Simple Logic:
        # Detect if price is near a linear regression line of Lows?
        # Or simple: Price > SMA50 > SMA200 (Strong Trend)

        # Let's map this to Strong Trend alignment for now
        # Requires SMA50 and SMA200

        # Note: AnalyticsService adds SMA_50 and SMA_200
        if "SMA_50" in df.columns and "SMA_200" in df.columns:
            sma50 = df["SMA_50"].iloc[-1]
            sma200 = df["SMA_200"].iloc[-1]
            close = df["Close"].iloc[-1]

            # Uptrend
            # Uptrend
            if close > sma50 and sma50 > sma200:
                self.reason = "Strong Uptrend (Close > 50 > 200)"
                return True
        return False

        return False
