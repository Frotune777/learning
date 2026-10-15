from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import linregress

from src.scanners.base import BaseStrategy


class TrendLinearRegressionStrategy(BaseStrategy):
    """
    Linear Regression Trendline Support strategy ported from PKScreener.
    Identifies if a stock is currently near its long-term trendline support.
    """

    def __init__(self, config: dict[str, Any] = None):
        super().__init__(config)
        self.description = "Trendline Support (Linear Regression)"
        self.points_limit = 30
        self.proximity_percent = 0.05  # 5% proximity to trendline
        self.min_slope = 0.15  # Minimum positive slope for an uptrend

    def analyze(self, df: pd.DataFrame) -> bool:
        if df is None or len(df) < self.points_limit:
            self.reason = "Insufficient data for Trendline analysis"
            return False

        try:
            # Screenipy data is newest first. Trend analysis needs chronological order.
            data = df.iloc[::-1].copy()
            data["Number"] = np.arange(len(data)) + 1

            data_low = data.copy()

            # Iteratively refine points to find the support trendline
            # This follows PKScreener's logic in ScreeningStatistics.py
            while len(data_low) > self.points_limit:
                try:
                    slope, intercept, r_value, p_value, std_err = linregress(
                        x=data_low["Number"], y=data_low["Low"]
                    )
                except Exception:
                    break

                # Keep points below the current regression line for the next iteration
                data_low = data_low.loc[
                    data_low["Low"] < slope * data_low["Number"] + intercept
                ]

                # Safety break if we filter out too many points in one go
                if len(data_low) < 5:
                    break

            # Final regression on the support points
            if len(data_low) < 2:
                self.reason = "Could not calculate trendline (not enough points)"
                return False

            slope, intercept, r_value, p_value, std_err = linregress(
                x=data_low["Number"], y=data_low["Close"]
            )

            # Predict current support value
            current_number = data["Number"].iloc[-1]
            current_close = data["Close"].iloc[-1]
            predicted_support = slope * current_number + intercept

            # Signal check
            limit_upper = predicted_support + (
                predicted_support * self.proximity_percent
            )
            limit_lower = predicted_support - (
                predicted_support * self.proximity_percent
            )

            if limit_lower < current_close < limit_upper and slope > self.min_slope:
                self.reason = f"Trendline Support Found (Slope: {slope:.2f}, Support: {predicted_support:.2f})"
                return True

            self.reason = f"No Trendline Support (Slope: {slope:.2f}, Support: {predicted_support:.2f}, Price: {current_close:.2f})"
            return False

        except Exception as e:
            self.reason = f"Trendline Analysis Error: {str(e)}"
            return False

    def get_description(self) -> str:
        return self.description
