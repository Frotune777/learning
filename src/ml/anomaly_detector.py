"""
File: src/ml/anomaly_detector.py
Purpose: ML-based anomaly detection for data quality and smart money footprints using Isolation Forest.
Last Modified: 2026-05-30
"""

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

LOGGER = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detects statistical outliers in price/volume data using Isolation Forest.
    Can identify both data quality issues (bad splits, zero volume) and trading
    anomalies (smart money accumulation footprints).

    Attributes:
        model (IsolationForest): The underlying Scikit-Learn anomaly model.
        contamination (float): The expected proportion of outliers in the data.

    Public Methods:
        - detect_anomalies(df_prices): Returns a DataFrame of flagged anomalous days.
        - filter_data_quality(df_prices): Returns a cleaned DataFrame with bad ticks removed.

    Thread Safety:
        Yes — fits model locally on instance call.
    """

    def __init__(self, contamination: float = 0.01, random_state: int = 42) -> None:
        """
        Initialize the Isolation Forest anomaly detector.

        Parameters:
            contamination (float): Expected proportion of outliers. | Default 0.01 (1%).
            random_state (int): Seed for random number generator. | Default 42.

        Returns:
            None
        """
        self.contamination: float = contamination
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=random_state,
            n_estimators=100,
        )

    def _prepare_features(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract anomaly detection features from raw OHLCV.
        """
        if len(df) < 25:
            raise ValueError("Insufficient data points for anomaly detection.")

        features = pd.DataFrame(index=df.index)

        # 1. Price Gap (Overnight Jump)
        prev_close = df["Close"].shift(1)
        features["Price_Gap_Pct"] = (df["Open"] - prev_close) / prev_close

        # 2. Daily Return
        features["Daily_Return"] = (df["Close"] - prev_close) / prev_close

        # 3. High-Low Spread (Intraday Volatility)
        features["HL_Spread_Pct"] = (df["High"] - df["Low"]) / df["Close"]

        # 4. Volume Z-Score (Rolling 20-day)
        vol_mean = df["Volume"].rolling(window=20).mean()
        vol_std = df["Volume"].rolling(window=20).std()
        # Avoid division by zero
        features["Vol_ZScore"] = (df["Volume"] - vol_mean) / (vol_std + 1e-9)

        # Fill NaNs for the first 20 days with 0 so we don't lose them completely
        features = features.fillna(0.0)

        # Drop infinity if any bad zeroes occurred in price
        features = features.replace([np.inf, -np.inf], 0.0)

        return df, features

    def detect_anomalies(self, df_prices: pd.DataFrame) -> pd.DataFrame:
        """
        Detect trading anomalies (smart money footprints or extreme volatility).

        Parameters:
            df_prices (pd.DataFrame): Raw OHLCV DataFrame. | Must have Open, High, Low, Close, Volume.

        Returns:
            pd.DataFrame: A DataFrame containing only the rows flagged as anomalies,
                          enriched with the feature values and anomaly scores.

        Raises:
            ValueError: If the dataframe is too small or missing columns.
        """
        req_cols = ["Open", "High", "Low", "Close", "Volume"]
        if not all(c in df_prices.columns for c in req_cols):
            raise ValueError(f"Input dataframe must contain {req_cols}")

        df, features = self._prepare_features(df_prices)

        # Fit and predict (-1 for anomalies, 1 for normal)
        preds = self.model.fit_predict(features)

        # Get anomaly scores (lower means more anomalous)
        scores = self.model.decision_function(features)

        # Combine results
        results = df.copy()
        for col in features.columns:
            results[col] = features[col]

        results["Is_Anomaly"] = preds == -1
        results["Anomaly_Score"] = scores

        # Return only the anomalous rows
        anomalies = results[results["Is_Anomaly"]].copy()

        # Sort by most severe anomaly first
        anomalies = anomalies.sort_values("Anomaly_Score")

        return anomalies

    def filter_data_quality(self, df_prices: pd.DataFrame) -> pd.DataFrame:
        """
        Identify and remove egregious data quality issues (bad splits, zero volume).
        This is a deterministic rules-based filter complementing the ML approach.

        Parameters:
            df_prices (pd.DataFrame): Raw OHLCV DataFrame.

        Returns:
            pd.DataFrame: Cleaned DataFrame.
        """
        clean_df = df_prices.copy()

        # 1. Remove 0 volume days
        if "Volume" in clean_df.columns:
            clean_df = clean_df[clean_df["Volume"] > 0]

        # 2. Remove days with > 25% single day gap (unadjusted corporate action)
        if "Close" in clean_df.columns and "Open" in clean_df.columns:
            prev_close = clean_df["Close"].shift(1)
            gap = (clean_df["Open"] - prev_close) / prev_close
            clean_df = clean_df[(gap.abs() < 0.25) | gap.isna()]

        # 3. Remove zero prices
        if "Close" in clean_df.columns:
            clean_df = clean_df[clean_df["Close"] > 0]

        LOGGER.info(
            "Data Quality Filter removed %d anomalous rows.",
            len(df_prices) - len(clean_df),
        )
        return clean_df
