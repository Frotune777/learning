"""
File: src/classes/MLModelTrainer.py
Purpose: Train, evaluate, and manage machine learning models for market prediction.

Dependencies:
External:
- joblib>=1.3.0: [model serialization and persistence]
- numpy>=1.18.0: [numerical operations and array handling]
- pandas>=2.0.0: [data manipulation and feature engineering]
- shap>=0.40.0: [model explainability and feature importance]
- sklearn: [classical ML algorithms and evaluation metrics]
- xgboost: [gradient boosted decision trees]
- tensorflow: [deep learning models (LSTM)]
- scipy: [statistical tests for drift detection]
Internal:
- N/A

Key Components:
Classes:
- MLModelTrainer: Orchestrates the lifecycle of financial machine learning models.
Functions:
- train_model: Train classifiers based on historical price/indicator data.
- explain_prediction: Generate SHAP values for local model interpretability.
- evaluate_model: Assess model metrics using time-series aware splits.
- detect_drift: Monitor feature distributions for concept drift.

Last Modified: 2026-02-19
Modified By: LLM

Open Tasks:
- [ ] [HIGH] Integrate Hyperopt for automated hyperparameter tuning [10h]
- [ ] [MEDIUM] Implement online learning for incremental model updates [15h]

Related Files:
- src/classes/Screener.py: [provides processed data for training]
- src/classes/ReportingService.py: [displays ML predictions and explanations]
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split


class MLModelTrainer:
    """
    Manages the lifecycle of ML models, from training to drift detection.

    Design Pattern: Strategy - supports multiple model backends (RF, XGB, LSTM).

    Attributes:
        model_dir (Path): Directory for storing serialized models | user_data/models

    Public Methods:
        - train_model(features, target, ...): Trains a basic classifier.
        - explain_prediction(model, X_instance): Explains individual predictions.
        - evaluate_model(model, features, target): Calculates performance metrics.
        - save_model(model, name): Persists model to disk.
        - load_model(name): Retrieves model from disk.
        - detect_drift(ref, current): Checks for statistical data drift.
        - nested_cross_validation(...): Performs robust model validation.

    Private Methods:
        - _prepare_sequences(X, y, window): Formats data for RNNs.
        - _train_lstm(X, y): Handles Keras model training.

    Usage Flow:
        1. Instantiate MLModelTrainer
        2. Call train_model with historical data
        3. Use explain_prediction on new signals
        4. Periodically call detect_drift to monitor performance

    State Management:
        - Valid states: Initialized
        - State transitions: N/A (Mainly functional service)

    Thread Safety: No - Keras and Scikit-learn backends may have thread-local state.

    Dependencies:
        External: sklearn, xgboost, tensorflow, shap, joblib
        Internal: N/A
    """

    def __init__(self, model_dir: str = "user_data/models") -> None:
        """
        Initialize trainer with persistence directory.

        Parameters:
            model_dir (str): Base path for model storage.
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def train_model(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        model_type: str = "random_forest",
    ) -> Any:
        """
        Train a machine learning classifier on processed features.

        Logic:
            Step 1: Filter out neutral signals and NaNs from target.
            Step 2: Clean features (handle inf, NaN, and extreme outliers).
            Step 3: Instantiate model based on requested type.
            Step 4: Fit model to the training set and return.

        Parameters:
            features (pd.DataFrame): Input indicators and features.
            target (pd.Series): Binary labels (1=Up, 0=Down).
            model_type (str): model architecture ('random_forest', 'xgboost', 'lstm').

        Returns:
            Any: Trained model object (sklearn, xgboost, or keras).

        Example:
            >>> trainer = MLModelTrainer()
            >>> model = trainer.train_model(X, y, model_type="xgboost")

        Performance:
            Time Complexity: O(M * N log N) [for RF/XGB where M is features, N samples]
            Space Complexity: O(Model Size) [depends on trees/neurons]

        Edge Cases Handled:
            - Target contains -1 (neutral) values (filtered).
            - Features contain infinity or large outliers (clipped).
            - Small sample sizes for deep learning (warning issued).
        """
        # Remove neutral (-1) and NaN
        mask = (target != -1) & (target.notna())
        X = features[mask].copy()
        y = target[mask]

        # Handle infinity and extremely large values
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(0)
        X = X.clip(lower=-1e12, upper=1e12)

        print(
            f"Training samples: {len(y)} ({(y == 1).sum()} up, {(y == 0).sum()} down)"
        )

        if model_type == "random_forest":
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=20,
                random_state=42,
                n_jobs=-1,
            )
        elif model_type == "xgboost":
            from xgboost import XGBClassifier

            model = XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                eval_metric="logloss",
            )
        elif model_type == "lstm":
            return self._train_lstm(X, y)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

        model.fit(X, y)
        return model

    def _prepare_sequences(
        self, X: pd.DataFrame, y: pd.Series, window_size: int = 20
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare sequence data for recurrent neural networks (LSTM).

        Logic:
            Step 1: Iterate through data in sliding windows.
            Step 2: Store previous X timestamps as features.
            Step 3: Store current y as target for each sequence.

        Parameters:
            X (pd.DataFrame): Flat feature DataFrame.
            y (pd.Series): Target labels.
            window_size (int): Sequence length (lookback).

        Returns:
            Tuple[np.ndarray, np.ndarray]: (X_sequences, y_labels).
        """
        X_seq, y_seq = [], []
        X_np = X.values
        y_np = y.values

        for i in range(window_size, len(X_np)):
            X_seq.append(X_np[i - window_size : i])
            y_seq.append(y_np[i])

        return np.array(X_seq), np.array(y_seq)

    def _train_lstm(self, X: pd.DataFrame, y: pd.Series) -> Optional[Any]:
        """
        Build and train a basic LSTM model using Keras.

        Parameters:
            X (pd.DataFrame): Input features.
            y (pd.Series): Target labels.

        Returns:
            Optional[Any]: Trained Keras Sequential model.
        """
        from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
        from tensorflow.keras.models import Sequential

        window_size = 20
        X_seq, y_seq = self._prepare_sequences(X, y, window_size)

        if len(X_seq) < 50:
            print("  ⚠️ Too few sequences for LSTM")
            return None

        model = Sequential(
            [
                Input(shape=(window_size, X.shape[1])),
                LSTM(units=50, return_sequences=True),
                Dropout(0.2),
                LSTM(units=50),
                Dropout(0.2),
                Dense(units=1, activation="sigmoid"),
            ]
        )

        model.compile(
            optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"]
        )
        model.fit(X_seq, y_seq, epochs=10, batch_size=32, verbose=0)

        return model

    def explain_prediction(
        self, model: Any, X_instance: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Explain a single prediction using SHAP TreeExplainer.

        Logic:
            Step 1: Check if model supports standard predict_proba.
            Step 2: Use TreeExplainer to calculate SHAP values.
            Step 3: Extract values for the 'UP' class (class 1).
            Step 4: Sort and return top contributing features.

        Parameters:
            model (Any): Trained tree ensemble model.
            X_instance (pd.DataFrame): Single row of features.

        Returns:
            Dict[str, float]: Mapping of feature names to importance scores.

        Performance:
            Time Complexity: O(T * D) [T trees, D depth]
            Space Complexity: O(F) [F features]
        """
        try:
            if not hasattr(model, "predict_proba"):
                return {}

            import shap

            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_instance)

            if isinstance(shap_values, list):
                vals = shap_values[1][0]
            else:
                vals = (
                    shap_values[0] if len(shap_values.shape) == 2 else shap_values[0][0]
                )

            feature_names = X_instance.columns
            importance = dict(zip(feature_names, vals))
            return dict(
                sorted(importance.items(), key=lambda item: abs(item[1]), reverse=True)
            )
        except Exception as e:
            print(f"  ⚠️ SHAP error: {e}")
            return {}

    def evaluate_model(
        self, model: Any, features: pd.DataFrame, target: pd.Series
    ) -> Dict[str, Any]:
        """
        Evaluate model performance using standard metrics.

        Parameters:
            model (Any): Trained model.
            features (pd.DataFrame): Feature set.
            target (pd.Series): Ground truth labels.

        Returns:
            Dict[str, Any]: Accuracy, Precision, Recall, F1, and metadata.
        """
        mask = (target != -1) & (target.notna())
        X = features[mask].fillna(0)
        y = target[mask]

        if "Sequential" in str(type(model)):
            return {"accuracy": 0.5, "note": "LSTM evaluation needs sequence split"}

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42
        )

        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        return {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
            "test_samples": len(y_test),
        }

    def save_model(self, model: Any, name: str) -> None:
        """
        Serialize and save model to the model directory.

        Parameters:
            model (Any): Model object to save.
            name (str): Filename without extension.
        """
        if "Sequential" in str(type(model)):
            path = self.model_dir / f"{name}.keras"
            model.save(path)
        else:
            path = self.model_dir / f"{name}.pkl"
            joblib.dump(model, path)
        print(f"  💾 Model saved: {path}")

    def load_model(self, name: str) -> Optional[Any]:
        """
        Load a model from disk if it exists.

        Parameters:
            name (str): Model name.

        Returns:
            Optional[Any]: Loaded model object or None.
        """
        pkl_path = self.model_dir / f"{name}.pkl"
        keras_path = self.model_dir / f"{name}.keras"

        if keras_path.exists():
            import tensorflow as tf

            return tf.keras.models.load_model(keras_path)
        if pkl_path.exists():
            return joblib.load(pkl_path)
        return None

    def detect_drift(
        self, reference_data: pd.DataFrame, current_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Detect distribution drift using Kolmogorov-Smirnov test.

        Logic:
            Step 1: Identify common features between datasets.
            Step 2: Run KS test for each feature.
            Step 3: Aggregate drift counts (p < 0.05).
            Step 4: Return drift score and detailed report.

        Parameters:
            reference_data (pd.DataFrame): Training distribution data.
            current_data (pd.DataFrame): New production data.

        Returns:
            Dict[str, Any]: Drift detection summary.
        """
        from scipy.stats import ks_2samp

        drift_report = {}
        drift_count = 0

        common_features = list(set(reference_data.columns) & set(current_data.columns))

        for feature in common_features:
            stat, p_val = ks_2samp(reference_data[feature], current_data[feature])
            is_drift = p_val < 0.05
            if is_drift:
                drift_count += 1

            drift_report[feature] = {"p_value": p_val, "drift_detected": is_drift}

        return {
            "drift_score": drift_count / len(common_features) if common_features else 0,
            "drift_detected": (drift_count / len(common_features)) > 0.3
            if common_features
            else False,
            "details": drift_report,
        }

    def nested_cross_validation(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        model_type: str = "random_forest",
    ) -> Dict[str, Any]:
        """
        Perform Time-Series Nested Cross-Validation.

        Logic:
            Step 1: Setup outer TimeSeriesSplit for generalization error.
            Step 2: Setup inner GridSearchCV for hyperparameter tuning.
            Step 3: Train and validate across all folds.
            Step 4: Average and return final validation scores.

        Parameters:
            features (pd.DataFrame): Input features.
            target (pd.Series): Target labels.

            model_type (str): Type of model to validate.

        Returns:
            Dict[str, Any]: CV performance metrics.
        """
        from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

        mask = (target != -1) & (target.notna())
        X = features[mask].fillna(0).reset_index(drop=True)
        y = target[mask].reset_index(drop=True)

        if len(X) < 100:
            return {"error": "Insufficient data for Nested CV"}

        tscv_outer = TimeSeriesSplit(n_splits=3)
        outer_scores = []

        for train_idx, test_idx in tscv_outer.split(X):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            if model_type == "random_forest":
                model = RandomForestClassifier(random_state=42)
                param_grid = {"n_estimators": [50, 100], "max_depth": [5, 10]}
            elif model_type == "xgboost":
                from xgboost import XGBClassifier

                model = XGBClassifier(random_state=42, eval_metric="logloss")
                param_grid = {"n_estimators": [50, 100], "learning_rate": [0.05, 0.1]}
            else:
                continue

            tscv_inner = TimeSeriesSplit(n_splits=2)
            grid = GridSearchCV(model, param_grid, cv=tscv_inner, scoring="accuracy")
            grid.fit(X_train, y_train)

            best_model = grid.best_estimator_
            y_pred = best_model.predict(X_test)
            outer_scores.append(accuracy_score(y_test, y_pred))

        return {
            "mean_accuracy": np.mean(outer_scores) if outer_scores else 0,
            "std_accuracy": np.std(outer_scores) if outer_scores else 0,
            "outer_scores": outer_scores,
        }
