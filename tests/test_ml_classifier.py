"""
File: tests/test_ml_classifier.py
Purpose: Unit tests for MLClassifier.
Last Modified: 2026-05-27
"""

import numpy as np
import pandas as pd

from src.nse_bhavcopy.ml_classifier import MLClassifier


def test_ml_classifier_workflow() -> None:
    """
    Verify the ML feature preparation, training, prediction, and backtesting.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> # Executed by pytest
    """
    # Create mock dataset
    dates = pd.date_range("2026-01-01", periods=60)
    # Generate mock upward trending price with noise
    close = [100.0 + i * 0.5 + np.sin(i) for i in range(60)]
    df_prices = pd.DataFrame(
        {
            "Open": [c - 1 for c in close],
            "High": [c + 2 for c in close],
            "Low": [c - 2 for c in close],
            "Close": close,
            "Volume": [1000 + i * 10 for i in range(60)],
        },
        index=dates,
    )
    df_prices.index.name = "Date"

    # Mock delivery dataframe
    df_delivery = pd.DataFrame(
        {
            "Date": dates,
            "DELIV_PCT": [0.4 + 0.005 * i for i in range(60)],
        }
    )

    clf = MLClassifier(n_estimators=10, max_depth=3, random_state=42)

    # 1. Feature Preparation
    X, y = clf.prepare_features(df_prices, df_delivery)
    assert not X.empty
    assert len(X) == len(y)
    assert "Return_1d" in X.columns
    assert "Return_5d" in X.columns
    assert "RSI_14" in X.columns
    assert "MACD_HIST" in X.columns
    assert "DELIV_PCT" in X.columns
    assert "Hurst_20d" in X.columns

    # 2. Training
    clf.train(X, y)

    # 3. Prediction
    preds = clf.predict(X)
    assert len(preds) == len(X)
    assert all(p in [0, 1] for p in preds)

    probs = clf.predict_probability(X)
    assert probs.shape == (len(X), 2)
    assert all(0.0 <= p <= 1.0 for row in probs for p in row)

    # 4. Backtesting
    results = clf.backtest_model(df_prices, df_delivery)
    assert "accuracy" in results
    assert "precision" in results
    assert "recall" in results
    assert "cumulative_buy_hold_return" in results
    assert "cumulative_strategy_return" in results
    assert len(results["test_predictions"]) > 0
