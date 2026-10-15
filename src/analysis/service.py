from typing import Any, Dict

import pandas as pd

from src.analysis.indicators.momentum import MomentumIndicators
from src.analysis.indicators.trend import TrendIndicators
from src.analysis.indicators.volatility import VolatilityIndicators
from src.analysis.indicators.volume import VolumeIndicators


class AnalyticsService:
    """
    Centralized service for technical analysis and statistical calculations.
    Decouples logic from the Screener loop.
    """

    def __init__(self):
        pass

    def resample_data(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Resample OHLCV data to a different timeframe.
        Target timeframe should be a pandas offset alias (e.g., '5T', '1H', '1D').
        """
        if df is None or df.empty:
            return df

        # Flatten MultiIndex if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                raise ValueError("DataFrame index must be DatetimeIndex for resampling")

        conversion = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }

        # Handle custom columns if exist (e.g. 'Adj Close')
        if "Adj Close" in df.columns:
            conversion["Adj Close"] = "last"

        # Filter conversion dict to only include columns present in df
        conversion = {k: v for k, v in conversion.items() if k in df.columns}

        try:
            # Ensure columns are float for aggregation to avoid object errors
            cols_to_convert = [c for c in conversion.keys() if c in df.columns]
            df_resample = df[cols_to_convert].copy()  # Work on subset
            for col in cols_to_convert:
                df_resample[col] = pd.to_numeric(df_resample[col], errors="coerce")

            resampled = df_resample.resample(timeframe).agg(conversion)
            return resampled.dropna()
        except Exception as e:
            print(f"Resampling error: {e}")
            return df

    def calculate_technical_indicators(
        self, df: pd.DataFrame, config: Dict[str, Any] = None
    ) -> pd.DataFrame:
        """
        Apply a suite of technical indicators to the DataFrame.
        Returns the DataFrame with added indicator columns.
        """
        if df is None or df.empty:
            return df

        # Ensure we work on a copy to avoid side effects if not intended
        df = df.copy()

        # Flatten MultiIndex if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.loc[:, ~df.columns.duplicated()]

        # Ensure all columns are numeric
        cols = ["Open", "High", "Low", "Close", "Volume"]
        for col in cols:
            if col in df.columns:
                try:
                    df[col] = df[col].astype(float)
                except Exception as e:
                    print(f"Error casting {col}: {e}")
                    df[col] = pd.to_numeric(df[col], errors="coerce")

        # Apply Modular Indicators
        # 1. Trend
        df = TrendIndicators.moving_averages(df, periods=[20, 50, 200])
        df = TrendIndicators.macd(df)
        df = TrendIndicators.adx(df)
        df = TrendIndicators.vwap(df)
        df = TrendIndicators.anchored_vwap(df, anchor_mode="low")
        df = TrendIndicators.pivots(df)
        df = TrendIndicators.fibonacci_retracements(df)
        df = TrendIndicators.ichimoku(df)

        # 2. Momentum
        df = MomentumIndicators.rsi(df)
        df = MomentumIndicators.stochastic(df)
        df = MomentumIndicators.cci(df)
        df = MomentumIndicators.detect_rsi_divergence(df)
        df = MomentumIndicators.detect_macd_divergence(df)

        # 3. Volatility
        df = VolatilityIndicators.atr(df)
        df = VolatilityIndicators.bollinger_bands(df)

        # 4. Volume
        df = VolumeIndicators.volume_profile(df)

        return df
