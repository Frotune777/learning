"""
File: src/nse_bhavcopy/ma_slope.py
Purpose: Calculates the Moving Average Slope angle and trend strength for a given stock.
Last Modified: 2026-05-27
"""

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.linear_model import LinearRegression


def calculate_ma_slope(
    prices: pd.Series, ma_window: int = 20, slope_period: int = 30
) -> tuple[float, pd.Series]:
    """
    Calculate the slope of the moving average line for a given time period.

    Parameters:
        prices (pd.Series): Series of historical closing prices.
        ma_window (int): Window size for the moving average calculation.
        slope_period (int): Time period over which to calculate the slope.

    Returns:
        Tuple[float, pd.Series]: The slope value and the moving average series.

    Raises:
        ValueError: If there are not enough data points.
    """
    if len(prices) < ma_window + slope_period:
        raise ValueError(f"Need at least {ma_window + slope_period} data points")

    ma_series = prices.rolling(window=ma_window).mean()
    ma_values = ma_series.dropna().iloc[-slope_period:].values

    if len(ma_values) < slope_period:
        raise ValueError("Not enough non-NA MA values to compute slope.")

    # Reshape for sklearn
    x = np.array(range(slope_period)).reshape(-1, 1)

    model = LinearRegression()
    model.fit(x, ma_values)

    slope = float(model.coef_[0])
    return slope, ma_series


def analyze_stock_ma_slope(
    ticker_symbol: str,
    ma_window: int = 20,
    slope_period: int = 30,
    days_of_data: int = 200,
) -> dict[str, Any]:
    """
    Analyze the moving average slope for a given stock ticker.

    Parameters:
        ticker_symbol (str): Yahoo Finance ticker symbol.
        ma_window (int): Window size for moving average.
        slope_period (int): Period to calculate slope.
        days_of_data (int): Historical data fetch window.

    Returns:
        dict[str, Any]: A dictionary containing slope metrics and trend description.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_of_data + 50)

    # Note: .NS suffix is assumed to be passed if it's an Indian stock,
    # but we fetch whatever is passed verbatim.
    try:
        data: pd.DataFrame = yf.download(
            ticker_symbol,
            start=start_date,
            end=end_date,
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        return {"error": f"Failed to download data: {e}"}

    if data.empty:
        return {"error": f"No data found for ticker {ticker_symbol}"}

    # Handle multi-index columns if downloading single ticker via yfinance
    if isinstance(data.columns, pd.MultiIndex):
        try:
            closing_prices = data["Close"].squeeze()
        except KeyError:
            return {"error": "Close price missing from data payload."}
    else:
        closing_prices = data["Close"]

    if len(closing_prices) < ma_window + slope_period:
        needed = ma_window + slope_period
        return {"error": f"Not enough data. Need at least {needed} trading days."}

    try:
        slope, _ = calculate_ma_slope(closing_prices, ma_window, slope_period)
    except ValueError as e:
        return {"error": str(e)}

    abs_slope = abs(slope)
    if abs_slope < 0.1:
        strength = "very weak"
    elif abs_slope < 0.5:
        strength = "weak"
    elif abs_slope < 1.0:
        strength = "moderate"
    elif abs_slope < 2.0:
        strength = "strong"
    else:
        strength = "very strong"

    direction = "upward" if slope > 0 else "downward"
    if abs_slope < 0.05:
        trend_description = "mostly flat"
    else:
        trend_description = f"{strength} {direction}"

    return {
        "symbol": ticker_symbol,
        "ma_window": ma_window,
        "slope_period": slope_period,
        "slope": slope,
        "trend": trend_description,
    }
