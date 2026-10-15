"""
Feature Engineering Pipeline for ML
Extracts features from OHLCV data and technical indicators
"""

import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.analysis.indicators.momentum import MomentumIndicators
from src.analysis.indicators.trend import TrendIndicators
from src.analysis.indicators.volatility import VolatilityIndicators
from src.analysis.indicators.volume import VolumeIndicators


class FeatureEngineer:
    """
    Extract ML features from market data
    """

    def __init__(self):
        self.trend_ind = TrendIndicators()
        self.momentum_ind = MomentumIndicators()
        self.volume_ind = VolumeIndicators()
        self.volatility_ind = VolatilityIndicators()

    def extract_features(
        self, data: pd.DataFrame, include_patterns: bool = False
    ) -> pd.DataFrame:
        """
        Extract all features from OHLCV data

        Args:
            data: DataFrame with OHLCV columns
            include_patterns: Whether to include pattern features

        Returns:
            DataFrame with extracted features
        """
        features = data.copy()

        # Price-based features
        features = self.create_price_features(features)

        # Indicator-based features
        features = self.create_indicator_features(features)

        # Pattern-based features (optional - computationally expensive)
        if include_patterns:
            features = self.create_pattern_features(features)

        # Drop OHLCV columns, keep only features
        feature_cols = [
            col
            for col in features.columns
            if col
            not in [
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "Adj Close",
                "Date",
                "Timestamp",
            ]
        ]

        # Prepare final feature set
        result = features[feature_cols].copy()

        # Global cleaning: Handle inf and NaN
        result = result.replace([np.inf, -np.inf], np.nan)
        result = result.fillna(0)

        return result

    def create_price_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create price-based features"""
        df = data.copy()

        # Returns
        for p in [1, 2, 3, 5, 10, 20]:
            df[f"returns_{p}d"] = df["Close"].pct_change(p)

        # ROC (Rate of Change)
        for p in [5, 10, 20]:
            df[f"roc_{p}"] = ((df["Close"] - df["Close"].shift(p)) / df["Close"].shift(p)) * 100

        # Volatility (rolling std of returns)
        for p in [5, 10, 20, 50]:
            df[f"volatility_{p}d"] = df["returns_1d"].rolling(p).std()

        # Distribution metrics
        df["skew_20d"] = df["returns_1d"].rolling(20).skew()
        df["kurt_20d"] = df["returns_1d"].rolling(20).kurt()

        # Momentum
        df["momentum_5d"] = df["Close"] / df["Close"].shift(5) - 1
        df["momentum_10d"] = df["Close"] / df["Close"].shift(10) - 1

        # Price position (current price vs recent high/low)
        for p in [20, 50, 250]:  # 250d is ~approx 52 weeks
            df[f"high_{p}d"] = df["High"].rolling(p).max()
            df[f"low_{p}d"] = df["Low"].rolling(p).min()
            df[f"price_pos_{p}d"] = (df["Close"] - df[f"low_{p}d"]) / (
                df[f"high_{p}d"] - df[f"low_{p}d"]
            )

        # Gap features
        df["gap"] = (df["Open"] - df["Close"].shift(1)) / df["Close"].shift(1)

        # Candle features
        df["body_size"] = abs(df["Close"] - df["Open"]) / df["Open"]
        df["upper_shadow"] = (df["High"] - df[["Open", "Close"]].max(axis=1)) / df["Open"]
        df["lower_shadow"] = (df[["Open", "Close"]].min(axis=1) - df["Low"]) / df["Open"]
        df["hl_range"] = (df["High"] - df["Low"]) / df["Close"]

        return df

    def create_indicator_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create indicator-based features"""
        df = data.copy()

        # Moving Averages (SMA)
        df = TrendIndicators.moving_averages(df, periods=[20, 50, 200])
        df["sma_20_50_ratio"] = df["SMA_20"] / df["SMA_50"]
        df["sma_50_200_ratio"] = df["SMA_50"] / df["SMA_200"]
        df["price_to_sma20"] = df["Close"] / df["SMA_20"]
        df["price_to_sma50"] = df["Close"] / df["SMA_50"]
        df["price_to_sma200"] = df["Close"] / df["SMA_200"]

        # Exponential Moving Averages (EMA)
        df = TrendIndicators.exponential_moving_averages(df, periods=[9, 21])
        df["ema_9_21_ratio"] = df["EMA_9"] / df["EMA_21"]

        # MACD
        df = TrendIndicators.macd(df)
        df["macd_signal_diff"] = df["MACD"] - df["MACD_Signal"]

        # RSI
        df = MomentumIndicators.rsi(df)
        df["rsi_oversold"] = (df["RSI"] < 30).astype(int)
        df["rsi_overbought"] = (df["RSI"] > 70).astype(int)
        df["rsi_change_5d"] = df["RSI"].pct_change(5)

        # Stochastic
        df = MomentumIndicators.stochastic(df)
        df["stoch_diff"] = df["Stoch_K"] - df["Stoch_D"]

        # CCI
        df = MomentumIndicators.cci(df)

        # MFI
        df = MomentumIndicators.mfi(df)

        # ADX
        df = TrendIndicators.adx(df)

        # ATR (volatility)
        df = VolatilityIndicators.atr(df)
        df["atr_ratio"] = df["ATR"] / df["Close"]

        # SuperTrend
        st_df = TrendIndicators.supertrend(df)
        df["SuperTrend"] = st_df["SuperTrend"]
        df["supertrend_diff"] = (df["Close"] - df["SuperTrend"]) / df["Close"]

        # Bollinger Bands
        df = VolatilityIndicators.bollinger_bands(df)
        df["bb_position"] = (df["Close"] - df["BB_Lower"]) / (
            df["BB_Upper"] - df["BB_Lower"]
        )
        df["bb_width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"]

        # Volume features
        df["volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
        df["volume_trend"] = (
            df["Volume"].rolling(5).mean() / df["Volume"].rolling(20).mean()
        )
        df["volume_change_1d"] = df["Volume"].pct_change(1)

        # OBV
        obv_calc = VolumeIndicators()
        df["OBV"] = obv_calc.obv(df)
        df["obv_trend"] = df["OBV"].pct_change(5)

        return df

    def create_pattern_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create pattern-based features (SMC, fractals)"""
        df = data.copy()

        # Import here to avoid circular dependency
        from src.analysis.SMCPatterns import SMCPatterns, WilliamsFractals

        # BOS detection
        bos = SMCPatterns.detect_bos(df)
        df["bos_bullish"] = (bos == "Bullish BOS").astype(int)
        df["bos_bearish"] = (bos == "Bearish BOS").astype(int)

        # CHOCH detection
        choch = SMCPatterns.detect_choch(df)
        df["choch_bullish"] = (choch == "Bullish CHOCH").astype(int)
        df["choch_bearish"] = (choch == "Bearish CHOCH").astype(int)

        # Fractals
        fractal_highs, fractal_lows = WilliamsFractals.detect_fractals(df)
        df["fractal_high"] = fractal_highs.notna().astype(int)
        df["fractal_low"] = fractal_lows.notna().astype(int)

        return df

    def create_target(
        self, data: pd.DataFrame, forward_periods: int = 5, threshold: float = 0.02
    ) -> pd.Series:
        """
        Create target variable for ML

        Args:
            data: DataFrame with Close prices
            forward_periods: How many periods ahead to look
            threshold: Minimum return to consider as "up" (2% default)

        Returns:
            Series with 1 (up), 0 (down), or -1 (neutral)
        """
        future_return = data["Close"].shift(-forward_periods) / data["Close"] - 1

        target = pd.Series(index=data.index, dtype=int)
        target[future_return > threshold] = 1  # Up
        target[future_return < -threshold] = 0  # Down
        target[
            (future_return >= -threshold) & (future_return <= threshold)
        ] = -1  # Neutral

        return target

    def scale_features(
        self, features: pd.DataFrame, method: str = "standard"
    ) -> pd.DataFrame:
        """
        Scale features for ML

        Args:
            features: DataFrame with features
            method: 'standard' (z-score) or 'minmax'

        Returns:
            Scaled features
        """
        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        if method == "standard":
            scaler = StandardScaler()
        else:
            scaler = MinMaxScaler()

        # Only scale numeric columns
        numeric_cols = features.select_dtypes(include=[np.number]).columns

        scaled = features.copy()
        scaled[numeric_cols] = scaler.fit_transform(features[numeric_cols])

        return scaled

    def select_features(
        self, features: pd.DataFrame, target: pd.Series, top_n: int = 20
    ) -> list[str]:
        """
        Select top N most important features

        Args:
            features: DataFrame with features
            target: Target variable
            top_n: Number of features to select

        Returns:
            List of selected feature names
        """
        from sklearn.ensemble import RandomForestClassifier

        # Remove rows where target is -1 (neutral) or NaN
        mask = (target != -1) & (target.notna())
        X = features[mask].fillna(0)
        y = target[mask]

        if len(y) < 50:
            # Not enough samples, return all features
            return features.columns.tolist()[:top_n]

        # Train quick RF to get feature importance
        rf = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        rf.fit(X, y)

        # Get feature importance
        importance = pd.DataFrame(
            {"feature": X.columns, "importance": rf.feature_importances_}
        ).sort_values("importance", ascending=False)

        return importance.head(top_n)["feature"].tolist()
