import pandas as pd
import talib


class MomentumIndicators:
    @staticmethod
    def rsi(df: pd.DataFrame, period=14) -> pd.DataFrame:
        """Calculate RSI"""
        df["RSI"] = talib.RSI(df["Close"].to_numpy(dtype=float), timeperiod=period)
        return df

    @staticmethod
    def stochastic(df: pd.DataFrame, fastk=14, slowk=3, slowd=3) -> pd.DataFrame:
        """Calculate Stochastic Oscillator"""
        slowk_series, slowd_series = talib.STOCH(
            df["High"].to_numpy(dtype=float),
            df["Low"].to_numpy(dtype=float),
            df["Close"].to_numpy(dtype=float),
            fastk_period=fastk,
            slowk_period=slowk,
            slowk_matype=0,
            slowd_period=slowd,
            slowd_matype=0,
        )
        df["Stoch_K"] = slowk_series
        df["Stoch_D"] = slowd_series
        return df

    @staticmethod
    def cci(df: pd.DataFrame, period=20) -> pd.DataFrame:
        """Calculate CCI"""
        df["CCI"] = talib.CCI(
            df["High"].to_numpy(dtype=float),
            df["Low"].to_numpy(dtype=float),
            df["Close"].to_numpy(dtype=float),
            timeperiod=period,
        )
        return df

    @staticmethod
    def mfi(df: pd.DataFrame, period=14) -> pd.DataFrame:
        """Calculate Money Flow Index (MFI)"""
        df["MFI"] = talib.MFI(
            df["High"].to_numpy(dtype=float),
            df["Low"].to_numpy(dtype=float),
            df["Close"].to_numpy(dtype=float),
            df["Volume"].to_numpy(dtype=float),
            timeperiod=period,
        )
        return df

    @staticmethod
    def detect_rsi_divergence(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
        """
        Detect RSI divergence vs Price.
        Bullish: Price lower low, RSI higher low
        Bearish: Price higher high, RSI lower high
        """
        try:
            if "RSI" not in df.columns or "Close" not in df.columns:
                df["RSI_Divergence"] = "None"
                return df

            df["Close"].to_numpy(dtype=float)
            df["RSI"].to_numpy(dtype=float)

            df["RSI_Divergence"] = "None"

            if len(df) < lookback:
                return df

            # Check last lookback candles
            recent_data = df.tail(lookback)
            price_recent = recent_data["Close"].to_numpy(dtype=float)
            rsi_recent = recent_data["RSI"].to_numpy(dtype=float)

            price_min_idx = price_recent.argmin()
            price_max_idx = price_recent.argmax()

            # Bullish Divergence: Price makes lower low, RSI makes higher low
            if price_min_idx > lookback // 2:
                prev_price_lows = price_recent[:price_min_idx]
                prev_rsi_lows = rsi_recent[:price_min_idx]

                if len(prev_price_lows) > 0:
                    prev_low_idx = prev_price_lows.argmin()
                    if (
                        price_recent[price_min_idx] < prev_price_lows[prev_low_idx]
                        and rsi_recent[price_min_idx] > prev_rsi_lows[prev_low_idx]
                    ):
                        df.loc[df.index[-1], "RSI_Divergence"] = "Bullish"

            # Bearish Divergence: Price makes higher high, RSI makes lower high
            if price_max_idx > lookback // 2:
                prev_price_highs = price_recent[:price_max_idx]
                prev_rsi_highs = rsi_recent[:price_max_idx]

                if len(prev_price_highs) > 0:
                    prev_high_idx = prev_price_highs.argmax()
                    if (
                        price_recent[price_max_idx] > prev_price_highs[prev_high_idx]
                        and rsi_recent[price_max_idx] < prev_rsi_highs[prev_high_idx]
                    ):
                        df.loc[df.index[-1], "RSI_Divergence"] = "Bearish"

            return df
        except Exception:
            df["RSI_Divergence"] = "None"
            return df

    @staticmethod
    def detect_macd_divergence(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
        """Detect MACD Histogram divergence vs Price."""
        try:
            if "MACD_Hist" not in df.columns or "Close" not in df.columns:
                df["MACD_Divergence"] = "None"
                return df

            df["Close"].to_numpy(dtype=float)
            df["MACD_Hist"].to_numpy(dtype=float)

            df["MACD_Divergence"] = "None"

            if len(df) < lookback:
                return df

            recent_data = df.tail(lookback)
            price_recent = recent_data["Close"].to_numpy(dtype=float)
            macd_recent = recent_data["MACD_Hist"].to_numpy(dtype=float)

            price_min_idx = price_recent.argmin()
            price_max_idx = price_recent.argmax()

            # Bullish Divergence
            if price_min_idx > lookback // 2:
                prev_price_lows = price_recent[:price_min_idx]
                prev_macd_lows = macd_recent[:price_min_idx]

                if len(prev_price_lows) > 0:
                    prev_low_idx = prev_price_lows.argmin()
                    if (
                        price_recent[price_min_idx] < prev_price_lows[prev_low_idx]
                        and macd_recent[price_min_idx] > prev_macd_lows[prev_low_idx]
                    ):
                        df.loc[df.index[-1], "MACD_Divergence"] = "Bullish"

            # Bearish Divergence
            if price_max_idx > lookback // 2:
                prev_price_highs = price_recent[:price_max_idx]
                prev_macd_highs = macd_recent[:price_max_idx]

                if len(prev_price_highs) > 0:
                    prev_high_idx = prev_price_highs.argmax()
                    if (
                        price_recent[price_max_idx] > prev_price_highs[prev_high_idx]
                        and macd_recent[price_max_idx] < prev_macd_highs[prev_high_idx]
                    ):
                        df.loc[df.index[-1], "MACD_Divergence"] = "Bearish"

            return df
        except Exception:
            df["MACD_Divergence"] = "None"
            return df
