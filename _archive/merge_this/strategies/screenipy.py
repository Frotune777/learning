import pandas as pd

from screeni.strategies.BaseStrategy import BaseStrategy


class ConsolidationStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Consolidation Pattern"
        self.percentage = config.get("consolidationPercentage", 10) if config else 10

    def analyze(self, df: pd.DataFrame) -> bool:
        if df is None or df.empty:
            return False

        # Logic ported from validateConsolidation
        # Needs high/low/close
        # Assuming df contains 'Close' and recently screened period

        # We look at the most recent snapshot or window passed in df
        hc = df["Close"].max()
        lc = df["Close"].min()

        if hc == 0:
            return False

        range_percent = abs((hc - lc) / hc) * 100

        # Store result in metadata or return bool?
        # The legacy screener printed colored text.
        # For now, return pure bool. Reporting layer can handle text.

        return range_percent <= self.percentage and (hc - lc != 0)


class BreakoutStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Breakout Pattern"
        self.days_to_lookback = config.get("daysToLookback", 30) if config else 30

    def analyze(self, df: pd.DataFrame) -> bool:
        if df.empty:
            return False

        # Simple breakout logic: Close > Max(High) of previous N days
        # df is expected to be the full window

        # Excluding today? Legacy code did `data = data[1:]` (skipping recent?) or similar
        # Let's assume df includes today at the end.

        if len(df) < self.days_to_lookback:
            return False

        # Detect Data Order (Chronological vs Reversed)
        # If iloc[0].name (Date) > iloc[-1].name, it's Reversed (Newest First)
        # Note: requires DatetimeIndex

        is_reversed = False
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
            if df.index[0] > df.index[-1]:
                is_reversed = True

        if is_reversed:
            recent = df.iloc[0]
            # unexpected: Screenipy passes reversed head(30).
            # So history is [1:] (Previous days)
            history = df.iloc[1:]
        else:
            recent = df.iloc[-1]
            history = df.iloc[:-1]

        if history.empty:
            return False

        history["High"].max()
        hc = history["Close"].max()
        rc = recent["Close"]

        return rc >= hc


class RSIStrategy(BaseStrategy):
    def __init__(self, config=None, min_rsi=30, max_rsi=70):
        super().__init__(config)
        self.description = "RSI Strategy"
        self.min_rsi = min_rsi
        self.max_rsi = max_rsi

    def analyze(self, df: pd.DataFrame) -> bool:
        if "RSI" not in df.columns or df.empty:
            self.reason = "RSI column missing or empty data"
            return False

        # Screenipy data is reversed (iloc[0] is latest)
        current_rsi = df["RSI"].iloc[0]
        passed = self.min_rsi <= current_rsi <= self.max_rsi
        self.reason = f"RSI: {current_rsi:.2f} ({'PASSED' if passed else 'FAILED'} [{self.min_rsi}-{self.max_rsi}])"
        return passed


class MomentumStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Momentum Strategy"

    def analyze(self, df: pd.DataFrame) -> bool:
        # Example: RSI > 50 and MACD > Signal
        if df.empty or "RSI" not in df.columns or "MACD" not in df.columns:
            self.reason = "Required indicators (RSI/MACD) missing"
            return False

        # Screenipy data is reversed (iloc[0] is latest)
        rsi = df["RSI"].iloc[0]
        macd = df["MACD"].iloc[0]
        signal = df["MACD_Signal"].iloc[0]

        passed = rsi > 50 and macd > signal
        self.reason = f"Momentum: RSI={rsi:.2f}, MACD={macd:.2f}, Signal={signal:.2f} ({'PASSED' if passed else 'FAILED'})"
        return passed
