#
"""
------------------------------------------------------------------------------------
                          FabTrader Algo Trading
------------------------------------------------------------------------------------
This utility calculates the slope of a moving average for a given scrip

For more information, visit our alog trading community:
www.fabtrader.in
"""

from datetime import datetime, timedelta

import numpy as np
import yfinance as yf
from sklearn.linear_model import LinearRegression


def calculate_ma_slope(prices, ma_window=20, slope_period=30):
    """
    Calculate the slope of the moving average line for a given time period.

    Parameters:
    ----------
    prices : pandas Series
        Series of historical closing prices.
    ma_window : int
        Window size for the moving average calculation (default: 20 days).
    slope_period : int
        Time period over which to calculate the slope (default: 30 days).

    Returns:
    -------
    slope : float
        The slope of the moving average line over the specified period.
    """
    # Ensure we have enough data
    if len(prices) < ma_window + slope_period:
        raise ValueError(f"Need at least {ma_window + slope_period} data points")

    # Calculate moving average
    ma_series = prices.rolling(window=ma_window).mean()

    # Get the last slope_period points where MA is available
    ma_values = ma_series.dropna().iloc[-slope_period:].values

    # Create X values (time indices)
    X = np.array(range(slope_period)).reshape(-1, 1)

    # Fit linear regression to find the slope
    model = LinearRegression()
    model.fit(X, ma_values)

    # Get the slope coefficient
    slope = model.coef_[0]

    return slope, ma_series


def analyze_stock_ma_slope(
    ticker_symbol="AAPL", ma_window=20, slope_period=30, days_of_data=200
):
    """
    Analyze the moving average slope for a given stock ticker.

    Parameters:
    ----------
    ticker_symbol : str
        Yahoo Finance ticker symbol (default: "AAPL" for Apple Inc).
    ma_window : int
        Window size for the moving average calculation (default: 20 days).
    slope_period : int
        Time period over which to calculate the slope (default: 30 days).
    days_of_data : int
        Number of days of historical data to retrieve (default: 200).
    """
    # Download data
    end_date = datetime.now()
    start_date = end_date - timedelta(
        days=days_of_data + 50
    )  # Add buffer for weekends/holidays

    # print(
    #     f"Downloading data for {ticker_symbol} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")

    data = yf.download(
        ticker_symbol, start=start_date, end=end_date, progress=False, auto_adjust=True
    )

    if data.empty:
        print(f"No data found for ticker {ticker_symbol}")
        return

    # print(f"Retrieved {len(data)} days of data for {ticker_symbol}")

    # Ensure we have enough data
    if len(data) < ma_window + slope_period:
        print(
            f"Not enough data. Need at least {ma_window + slope_period} trading days."
        )
        return

    # Calculate MA and its slope
    closing_prices = data["Close"]
    slope, ma_series = calculate_ma_slope(closing_prices, ma_window, slope_period)

    print(f"\nStock : {ticker_symbol}")
    print(f"{ma_window}-Day MA slope over the last {slope_period} days: {slope[0]:.4f}")

    # Determine trend strength and direction
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

    print(f"Moving Average Slope Trend: {trend_description}")


if __name__ == "__main__":
    # You can change these parameters
    ticker = "AAPL"  # Apple Inc.
    ma_window = 20  # 20-day moving average
    slope_period = 30  # Calculate slope over 30 days

    analyze_stock_ma_slope(
        ticker_symbol=ticker, ma_window=ma_window, slope_period=slope_period
    )
