import pandas as pd

from src.scanners.base import BaseStrategy


class IchimokuStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Ichimoku Cloud Strategy"

    def analyze(self, df: pd.DataFrame) -> bool:
        if df.empty or "TS" not in df.columns or "KS" not in df.columns:
            return False

        # Bullish: Tenkan-Sen > Kijun-Sen (Crossover)
        # And Price > Span A/B (Cloud)
        ts = df["TS"].iloc[-1]
        ks = df["KS"].iloc[-1]
        price = df["Close"].iloc[-1]
        span_a = df["SpanA"].iloc[-1] if "SpanA" in df.columns else 0
        span_b = df["SpanB"].iloc[-1] if "SpanB" in df.columns else 0

        if ts > ks and price > max(span_a, span_b):
            self.reason = f"TS ({ts:.2f}) > KS ({ks:.2f}) & Price > Cloud"
            return True

        return False


class NR4Strategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Narrow Range 4 (Volatility Contraction)"

    def analyze(self, df: pd.DataFrame) -> bool:
        if len(df) < 4:
            return False

        # Range = High - Low
        ranges = (df["High"] - df["Low"]).tail(4).values
        today_range = ranges[-1]
        prev_ranges = ranges[:-1]

        if today_range < min(prev_ranges):
            self.reason = f"NR4: Today range ({today_range:.2f}) is smallest in 4 days"
            return True

        return False


class HighLow52WeekStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "52-Week High/Low Breakout"

    def analyze(self, df: pd.DataFrame) -> bool:
        if len(df) < 252:
            return False  # ~1 year of data

        yearly_data = df.tail(252)
        hi52 = yearly_data["High"].max()
        lo52 = yearly_data["Low"].min()
        price = df["Close"].iloc[-1]

        # Within 2% of 52W High
        if price >= hi52 * 0.98:
            self.reason = f"Price ({price:.2f}) near 52W High ({hi52:.2f})"
            return True

        # Within 2% of 52W Low (Bearish)
        if price <= lo52 * 1.02:
            self.reason = f"Price ({price:.2f}) near 52W Low ({lo52:.2f})"
            return True

        return False


class NextDayBullishStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Next Day Bullish Prediction (Heuristic)"

    def analyze(self, df: pd.DataFrame) -> bool:
        if len(df) < 20:
            return False

        rsi = df["RSI"].iloc[-1] if "RSI" in df.columns else 50
        sma20 = df["Close"].rolling(20).mean().iloc[-1]
        price = df["Close"].iloc[-1]

        # Condition: RSI strongly bullish, Price above MA, and Vol positive
        if rsi > 65 and price > sma20:
            self.reason = f"Momentum Strong: RSI ({rsi:.2f}) > 65 & Price > MA20"
            return True

        return False


class SuperTrendStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "SuperTrend Bullish Strategy"

    def analyze(self, df: pd.DataFrame) -> bool:
        from src.analysis.indicators.Trend import TrendIndicators

        st_df = TrendIndicators.supertrend(df)

        if st_df["Direction"].iloc[-1] == 1:
            self.reason = "SuperTrend is Bullish"
            return True

        return False


class ATRCrossStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "ATR Trailing Stop Cross"

    def analyze(self, df: pd.DataFrame) -> bool:
        if "ATR" not in df.columns:
            return False

        atr = df["ATR"].iloc[-1]
        price = df["Close"].iloc[-1]
        prev_price = df["Close"].iloc[-2]

        # Bullish cross of ATR-based trailing stop (simplified)
        # Using 3x ATR as a heuristic
        stop = df["Close"].rolling(window=14).max() - (3 * atr)
        if price > stop.iloc[-1] and prev_price <= stop.iloc[-2]:
            self.reason = (
                f"Price ({price:.2f}) crossed above ATR Stop ({stop.iloc[-1]:.2f})"
            )
            return True

        return False


class HighMomentumStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "High Momentum Stock (RSI & Volume & Price)"

    def analyze(self, df: pd.DataFrame) -> bool:
        if len(df) < 5:
            return False

        rsi = df["RSI"].iloc[-1] if "RSI" in df.columns else 50
        vol_ratio = df["Volume"].iloc[-1] / df["Volume"].rolling(20).mean().iloc[-1]
        price_gain = (df["Close"].iloc[-1] / df["Close"].iloc[-5] - 1) * 100

        if rsi > 70 and vol_ratio > 1.5 and price_gain > 5:
            self.reason = f"High Momentum: RSI={rsi:.1f}, Vol={vol_ratio:.1f}x, 5D Gain={price_gain:.1f}%"
            return True

        return False
