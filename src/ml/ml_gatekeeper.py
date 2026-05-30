"""
File: src/nse_bhavcopy/ml_gatekeeper.py
Purpose: ML-powered data quality gatekeeper to detect bad ticks and corporate actions.
Last Modified: 2026-05-30
"""

import logging
from enum import Enum

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


class GatekeeperDecision(Enum):
    OK = "OK"
    BAD_TICK = "BAD_TICK"
    CORP_ACTION = "CORP_ACTION"


class MLDataGatekeeper:
    """
    Evaluates new incremental OHLCV rows against existing historical data
    using an Isolation Forest anomaly detection model.
    """

    def __init__(self, contamination: float = 0.01) -> None:
        try:
            from sklearn.ensemble import IsolationForest

            self._IsolationForest = IsolationForest
            self.model = IsolationForest(contamination=contamination, random_state=42)
            self._enabled = True
        except ImportError:
            LOGGER.warning("scikit-learn not found. MLGatekeeper disabled.")
            self._enabled = False
            self.model = None

        # Standard corporate action ratios (1:1 split, 1:5 split, etc.)
        self.STANDARD_RATIOS = [0.5, 0.2, 0.1, 1 / 1.5, 0.8, 1 / 3, 1 / 4]

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create volatility and relative change features for the model."""
        features = pd.DataFrame(index=df.index)
        features["Return"] = df["Close"].pct_change().fillna(0)

        # High-Low spread percentage (Intraday volatility)
        features["HL_Spread"] = (df["High"] - df["Low"]) / df["Close"]
        features["HL_Spread"] = features["HL_Spread"].fillna(0)

        # Volume relative to 5-day moving average (if enough data)
        if "Volume" in df.columns:
            # We use rolling on the feature df to avoid shifting issues later
            vol_sma = df["Volume"].rolling(window=5, min_periods=1).mean()
            # Prevent div by 0
            features["Vol_Ratio"] = df["Volume"] / vol_sma.replace(0, 1)
        else:
            features["Vol_Ratio"] = 1.0

        return features

    def evaluate(
        self, existing_df: pd.DataFrame, new_df: pd.DataFrame
    ) -> GatekeeperDecision:
        """
        Evaluate new daily candles for anomalies.
        Returns GatekeeperDecision.
        """
        if not self._enabled or existing_df.empty or new_df.empty:
            return GatekeeperDecision.OK

        # We need enough data to establish a baseline
        if len(existing_df) < 50:
            return self._fallback_rule_based(existing_df, new_df)

        # Combine data for feature engineering so we get correct pct_change on the boundary
        # Take only the last 252 rows of existing to train on recent volatility regime
        train_df = existing_df.iloc[-252:].copy()

        # Calculate features on train
        train_features = self._engineer_features(train_df)

        # We only train on non-NaN rows
        X_train = train_features.dropna().values
        if len(X_train) < 20:
            return self._fallback_rule_based(existing_df, new_df)

        self.model.fit(X_train)

        # Now evaluate new data
        combined_df = pd.concat([train_df.iloc[-1:], new_df])
        new_features = self._engineer_features(combined_df)

        # The first row of combined_df is the old data, so we drop it
        new_features = new_features.iloc[1:]

        X_test = new_features.values
        predictions = self.model.predict(X_test)

        for i, pred in enumerate(predictions):
            new_close = float(new_df["Close"].iloc[i])

            # Find the previous close to calculate the actual gap ratio
            if i == 0:
                prev_close = float(train_df["Close"].iloc[-1])
            else:
                prev_close = float(new_df["Close"].iloc[i - 1])

            if prev_close <= 0 or new_close <= 0:
                continue

            ratio = new_close / prev_close

            # Always evaluate if it's an extreme jump (>20%) OR if ML model flagged it
            is_extreme = ratio < 0.80 or ratio > 1.20

            if pred == -1 or is_extreme:  # Anomaly detected
                # Check if it's a corporate action
                is_corp_action = False
                for std_factor in self.STANDARD_RATIOS:
                    if abs(ratio - std_factor) < 0.05:
                        is_corp_action = True
                        break

                if is_corp_action:
                    LOGGER.info(
                        "ML Gatekeeper: Detected corporate action ratio %.3f", ratio
                    )
                    return GatekeeperDecision.CORP_ACTION

                # If not a corp action, but it's a huge deviation, classify as BAD_TICK
                # We use a 5-sigma rule on the returns
                train_returns = train_features["Return"].dropna()
                mean_ret = train_returns.mean()
                std_ret = train_returns.std()

                if std_ret > 0:
                    z_score = abs((ratio - 1) - mean_ret) / std_ret
                    # If it's a crazy z_score OR it's just an extreme >20% move that isn't a split
                    if z_score > 5.0 or is_extreme:
                        LOGGER.warning(
                            "ML Gatekeeper: Detected BAD TICK. Z-Score: %.2f", z_score
                        )
                        return GatekeeperDecision.BAD_TICK

        return GatekeeperDecision.OK

    def _fallback_rule_based(
        self, existing_df: pd.DataFrame, new_df: pd.DataFrame
    ) -> GatekeeperDecision:
        """Fallback to the old 20% threshold if not enough data for ML."""
        last_close = float(existing_df["Close"].iloc[-1])
        first_new_close = float(new_df["Close"].iloc[0])

        if last_close > 0 and first_new_close > 0:
            ratio = first_new_close / last_close
            if ratio < 0.80 or ratio > 2.0:
                # Check if it matches std ratio
                for std_factor in self.STANDARD_RATIOS:
                    if abs(ratio - std_factor) < 0.05:
                        return GatekeeperDecision.CORP_ACTION
                # If it doesn't match standard ratio but dropped >20%, assume BAD TICK for safety
                if ratio < 0.80:
                    return GatekeeperDecision.BAD_TICK

        return GatekeeperDecision.OK
