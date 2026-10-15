import pandas as pd
import talib


class VolatilityIndicators:
    @staticmethod
    def bollinger_bands(
        df: pd.DataFrame, period=20, dev_up=2, dev_dn=2
    ) -> pd.DataFrame:
        """Calculate Bollinger Bands"""
        upper, middle, lower = talib.BBANDS(
            df["Close"].to_numpy(dtype=float),
            timeperiod=period,
            nbdevup=dev_up,
            nbdevdn=dev_dn,
            matype=0,
        )
        df["BB_Upper"] = upper
        df["BB_Middle"] = middle
        df["BB_Lower"] = lower
        return df

    @staticmethod
    def atr(df: pd.DataFrame, period=14) -> pd.DataFrame:
        """Calculate Average True Range"""
        df["ATR"] = talib.ATR(
            df["High"].to_numpy(dtype=float),
            df["Low"].to_numpy(dtype=float),
            df["Close"].to_numpy(dtype=float),
            timeperiod=period,
        )
        return df

    def donchian_channels(self, data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """Calculate Donchian Channels"""
        df = data.copy()
        df["DC_Upper"] = df["High"].rolling(window=period).max()
        df["DC_Lower"] = df["Low"].rolling(window=period).min()
        df["DC_Middle"] = (df["DC_Upper"] + df["DC_Lower"]) / 2
        return df[["DC_Upper", "DC_Middle", "DC_Lower"]]
