import pandas as pd

from screeni.strategies.BaseStrategy import BaseStrategy


class MACDStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "MACD Crossover Strategy"

    def analyze(self, df: pd.DataFrame) -> bool:
        if df.empty or "MACD" not in df.columns:
            return False

        # Bullish Crossover: MACD > Signal
        macd = df["MACD"].iloc[-1]
        signal = df["MACD_Signal"].iloc[-1]

        # Check if crossover happened recently (e.g. today or yesterday)
        # For simple screening, just check if currently bullish
        # Bullish Crossover: MACD > Signal
        macd = df["MACD"].iloc[-1]
        signal = df["MACD_Signal"].iloc[-1]

        if macd > signal:
            self.reason = f"MACD ({macd:.2f}) > Signal ({signal:.2f})"
            return True

        self.reason = f"MACD ({macd:.2f}) < Signal"
        return False


class CCIStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "CCI Strategy"
        self.min_cci = -100
        self.max_cci = 100

    def analyze(self, df: pd.DataFrame) -> bool:
        if df.empty or "CCI" not in df.columns:
            return False

        # CCI > 100 usually indicates strong uptrend start
        # CCI < -100 indicates strong downtrend

        cci = df["CCI"].iloc[-1]

        # Example logic: Momentum Buy if CCI > 100
        # Example logic: Momentum Buy if CCI > 100
        if cci > 100:
            self.reason = f"CCI ({cci:.2f}) > 100"
            return True

        self.reason = f"CCI ({cci:.2f}) < 100"
        return False


class StochasticStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        self.description = "Stochastic Oscillator Strategy"

    def analyze(self, df: pd.DataFrame) -> bool:
        if df.empty or "Stoch_K" not in df.columns:
            return False

        # Bullish: K > D and both < 20 (Oversold reversal)
        # OR simply K > D (Momentum)

        k = df["Stoch_K"].iloc[-1]
        d = df["Stoch_D"].iloc[-1]

        if k > d and k < 80:
            self.reason = f"Stoch K ({k:.2f}) > D ({d:.2f}) & K < 80"
            return True

        self.reason = "Stoch weak or OB"
        return False
