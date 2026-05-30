"""
File: src/nse_bhavcopy/ml_classifier.py
Purpose: Random Forest classifier to predict next-day price direction.
Last Modified: 2026-05-27
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score

from src.nse_bhavcopy.quant_metrics import calculate_hurst_exponent

LOGGER = logging.getLogger(__name__)


class MLClassifier:
    """
    Random Forest Classifier for predicting stock next-day price direction.

    Attributes:
        model (RandomForestClassifier): Underlying Scikit-Learn model.

    Public Methods:
        - prepare_features(df_prices, df_delivery): Calculate features & target.
        - train(X, y): Fit the model.
        - predict(X): Predict binary next-day direction.
        - predict_probability(X): Predict probabilities of up-direction.
        - backtest_model(df_prices, df_delivery): Perform a walk-forward test.

    Thread Safety:
        Yes — fits model locally on instance call.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 5,
        random_state: int = 42,
    ) -> None:
        """
        Initialize the Random Forest model.

        Parameters:
            n_estimators (int): Number of trees in the forest. | Default 100.
            max_depth (int): Maximum depth of the trees. | Default 5.
            random_state (int): Seed for random number generator. | Default 42.

        Returns:
            None

        Raises:
            None

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> clf = MLClassifier(n_estimators=50)
        """
        self.model: RandomForestClassifier = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
        )

    def prepare_features(
        self,
        df_prices: pd.DataFrame,
        df_delivery: pd.DataFrame | None = None,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Extract indicators and calculate features & next-day targets.

        Parameters:
            df_prices (pd.DataFrame): Price data (Close, Date index/col). | Non-empty.
            df_delivery (pd.DataFrame | None): Delivery data (Date, DELIV_PCT). |
                Default None.

        Returns:
            tuple[pd.DataFrame, pd.Series]: Features (X) and target (y).

        Raises:
            ValueError: If df_prices has fewer than 25 rows or is missing Close.

        Complexity:
            Time: O(N * L) where N = rows, L = lookbacks (Hurst & features).
            Space: O(N) for storing temporary features.

        Example:
            >>> X, y = clf.prepare_features(df_prices)
        """
        df = df_prices.copy()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")

        df = df.sort_index()

        if "Close" not in df.columns:
            raise ValueError("Input dataframe must contain 'Close' price column.")

        if len(df) < 25:
            raise ValueError("Insufficient data points to build features.")

        # Lagged Returns
        close = df["Close"].astype("float64")
        df["Return_1d"] = close.pct_change(1)
        df["Return_5d"] = close.pct_change(5)
        df["Return_10d"] = close.pct_change(10)

        # Technical Indicators (Fallbacks if missing)
        if "RSI_14" not in df.columns:
            # Simple RSI calculation
            diff = close.diff(1)
            gain = (diff.where(diff > 0, 0)).rolling(window=14).mean()
            loss = (-diff.where(diff < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-9)
            df["RSI_14"] = 100 - (100 / (1 + rs))

        if "MACD_HIST" not in df.columns:
            # Standard MACD(12,26,9) histogram fallback
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            df["MACD_HIST"] = macd - signal

        # Volatility features
        log_rets = np.log(close / close.shift(1))
        df["Vol_20d"] = log_rets.rolling(20).std()

        # Rolling Hurst Exponent
        hurst_list: list[float] = []
        for i in range(len(df)):
            if i < 20:
                hurst_list.append(0.5)
                continue
            window = close.iloc[i - 20 : i]
            try:
                hurst_list.append(calculate_hurst_exponent(window, lags=5))
            except Exception:
                hurst_list.append(0.5)
        df["Hurst_20d"] = hurst_list

        # Delivery Percentage merge
        if df_delivery is not None and not df_delivery.empty:
            deliv = df_delivery.copy()
            deliv["Date"] = pd.to_datetime(deliv["Date"])
            deliv = deliv.set_index("Date")
            # Limit delivery percentage join to target symbol
            df = df.join(deliv["DELIV_PCT"], how="left")
            df["DELIV_PCT"] = df["DELIV_PCT"].ffill().fillna(0.0)
        else:
            df["DELIV_PCT"] = 0.0

        # Target: Next-day direction (Close_{t+1} > Close_t)
        # Shift close price to align next-day close with today's row
        next_close = close.shift(-1)
        target = (next_close > close).astype(int)

        feature_cols = [
            "Return_1d",
            "Return_5d",
            "Return_10d",
            "RSI_14",
            "MACD_HIST",
            "Vol_20d",
            "Hurst_20d",
            "DELIV_PCT",
        ]

        # Combine features and targets, then drop NaNs
        combined = df[feature_cols].copy()
        combined["Target"] = target
        combined = combined.dropna()

        if combined.empty:
            raise ValueError("No complete feature records found after dropna.")

        X = combined[feature_cols]
        y = combined["Target"]

        return X, y

    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Fit the Random Forest Classifier.

        Parameters:
            X (pd.DataFrame): Training features. | Non-empty.
            y (pd.Series): Training targets. | Match X length.

        Returns:
            None

        Raises:
            ValueError: If inputs are invalid or shape mismatch.

        Complexity:
            Time: O(M * N * log N) where M = n_estimators, N = samples.
            Space: O(M * max_depth) for the tree nodes structure.

        Example:
            >>> clf.train(X, y)
        """
        if len(X) != len(y):
            raise ValueError("Features and targets must have same length.")
        self.model.fit(X, y)
        LOGGER.info("Successfully trained Random Forest Classifier model.")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict next-day direction (0 or 1).

        Parameters:
            X (pd.DataFrame): Feature records. | Valid shape.

        Returns:
            np.ndarray: Predicted binary classes.

        Raises:
            None

        Complexity:
            Time: O(M * max_depth) where M = n_estimators.
            Space: O(P) where P = rows.

        Example:
            >>> preds = clf.predict(X)
        """
        return np.asarray(self.model.predict(X))

    def predict_probability(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probabilities of up-direction.

        Parameters:
            X (pd.DataFrame): Feature records. | Valid shape.

        Returns:
            np.ndarray: Probability array of size (N, 2).

        Raises:
            None

        Complexity:
            Time: O(M * max_depth) where M = n_estimators.
            Space: O(P) where P = rows.

        Example:
            >>> probs = clf.predict_probability(X)
        """
        return np.asarray(self.model.predict_proba(X))

    def backtest_model(
        self,
        df_prices: pd.DataFrame,
        df_delivery: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        """
        Perform walk-forward chronologically split train/test evaluation.

        Parameters:
            df_prices (pd.DataFrame): Price history. | Minimum 40 rows.
            df_delivery (pd.DataFrame | None): Delivery data. | Default None.

        Returns:
            dict[str, Any]: Test metrics and strategy return comparisons.

        Raises:
            ValueError: If data is insufficient.

        Complexity:
            Time: O(N * log N) training and testing.
            Space: O(N)

        Example:
            >>> results = clf.backtest_model(df_prices)
        """
        X, y = self.prepare_features(df_prices, df_delivery)
        if len(X) < 10:
            raise ValueError("Insufficient feature rows to execute backtest.")

        # Chronological split (80% train, 20% test)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

        self.train(X_train, y_train)

        preds = self.predict(X_test)
        probs = self.predict_probability(X_test)[:, 1]

        acc = accuracy_score(y_test, preds)
        prec = precision_score(y_test, preds, zero_division=0)
        rec = recall_score(y_test, preds, zero_division=0)

        # Basic backtest simulated strategy returns
        # Position is 1 if prediction is 1, else 0 (long-only daily rebalancing)
        test_prices = df_prices.iloc[split_idx + 1 :]
        # Check alignment of index and pct change
        test_returns = test_prices["Close"].pct_change().fillna(0.0)

        # Align lengths if needed
        min_len = min(len(preds), len(test_returns))
        preds_align = preds[:min_len]
        rets_align = test_returns.iloc[:min_len]

        strategy_rets = preds_align * rets_align
        cum_bh = (1 + rets_align).prod() - 1.0
        cum_strat = (1 + strategy_rets).prod() - 1.0

        return {
            "accuracy": float(acc),
            "precision": float(prec),
            "recall": float(rec),
            "cumulative_buy_hold_return": float(cum_bh),
            "cumulative_strategy_return": float(cum_strat),
            "test_predictions": preds.tolist(),
            "test_probabilities": probs.tolist(),
        }
