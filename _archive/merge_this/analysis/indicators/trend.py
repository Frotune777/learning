import pandas as pd
import talib


class TrendIndicators:
    @staticmethod
    def moving_averages(df: pd.DataFrame, periods=[20, 50, 200]) -> pd.DataFrame:
        """Calculate Simple Moving Averages"""
        for period in periods:
            try:
                # print(f"DEBUG: SMA Input Shape: {df['Close'].to_numpy(dtype=float).shape}")
                df[f"SMA_{period}"] = talib.SMA(
                    df["Close"].to_numpy(dtype=float), timeperiod=period
                )
            except Exception as e:
                print(f"SMA Error: {e}")
                df[f"SMA_{period}"] = pd.NA
        return df

    @staticmethod
    def exponential_moving_averages(df: pd.DataFrame, periods=[9, 21]) -> pd.DataFrame:
        """Calculate Exponential Moving Averages"""
        for period in periods:
            df[f"EMA_{period}"] = talib.EMA(
                df["Close"].to_numpy(dtype=float), timeperiod=period
            )
        return df

    @staticmethod
    def macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
        """Calculate MACD"""
        macd, macdsignal, macdhist = talib.MACD(
            df["Close"].to_numpy(dtype=float),
            fastperiod=fast,
            slowperiod=slow,
            signalperiod=signal,
        )
        df["MACD"] = macd
        df["MACD_Signal"] = macdsignal
        df["MACD_Hist"] = macdhist
        return df

    @staticmethod
    def adx(df: pd.DataFrame, period=14) -> pd.DataFrame:
        """Calculate ADX"""
        df["ADX"] = talib.ADX(
            df["High"].to_numpy(dtype=float),
            df["Low"].to_numpy(dtype=float),
            df["Close"].to_numpy(dtype=float),
            timeperiod=period,
        )
        return df

    @staticmethod
    def vwap(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Cumulative VWAP"""
        v = df["Volume"].values
        tp = (df["High"] + df["Low"] + df["Close"]) / 3
        df["VWAP"] = (tp * v).cumsum() / v.cumsum()
        return df

    @staticmethod
    def session_vwap(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Session VWAP (resets daily)"""
        df = df.copy()
        df["date_only"] = df.index.date

        # Group by date and calculate cumulative sums
        df["tp"] = (df["High"] + df["Low"] + df["Close"]) / 3
        df["tpv"] = df["tp"] * df["Volume"]

        # Cumulative Sums reset per day
        df["cum_tpv"] = df.groupby("date_only")["tpv"].cumsum()
        df["cum_vol"] = df.groupby("date_only")["Volume"].cumsum()

        df["Session_VWAP"] = df["cum_tpv"] / df["cum_vol"]

        # Cleanup
        df.drop(["date_only", "tp", "tpv", "cum_tpv", "cum_vol"], axis=1, inplace=True)
        return df

    @staticmethod
    def anchored_vwap(
        df: pd.DataFrame, anchor_mode="low", anchor_period=None
    ) -> pd.DataFrame:
        """
        Calculate Anchored VWAP
        anchor_mode: 'low' (anchor to lowest low), 'high' (anchor to highest high), 'date' (anchor to specific date)
        """
        # Align with PKScreener logic: Find major low/high
        df_copy = df.copy()

        # PKScreener usually expects data sorted such that oldest is first for calculation?
        # But Screeni-py standard is usually reversed (newest first) inside Screener.py BUT
        # AnalyticsService receives it... wait, AnalyticsService usually gets data in native order (oldest first)?
        # Let's ensure datetime index.

        # Determine anchor date
        anchor_date = None
        if anchor_mode == "low":
            # Find lowest low
            # If period provided, look back that many days?
            min_idx = df_copy["Low"].idxmin()
            anchor_date = min_idx
        elif anchor_mode == "high":
            max_idx = df_copy["High"].idxmax()
            anchor_date = max_idx

        if anchor_date:
            # Calculation
            # Filter data from anchor date
            mask = df_copy.index >= anchor_date

            # Helper for cumsum
            v = df_copy.loc[mask, "Volume"]
            tp = (
                df_copy.loc[mask, "High"]
                + df_copy.loc[mask, "Low"]
                + df_copy.loc[mask, "Close"]
            ) / 3

            # Calculate
            pv = (tp * v).cumsum()
            v_sum = v.cumsum()

            # Assign back
            df.loc[mask, "AVWAP"] = pv / v_sum

        return df

    @staticmethod
    def pivots(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Standard Pivot Points (Fibonacci)"""
        # Using Fibonacci Pivots for expert level
        # P = (H + L + C) / 3
        # R1 = P + (P - L) = 2*P - L (This is standard)
        # Fib R1 = P + 0.382 * (H - L)

        high = df["High"].to_numpy(dtype=float)
        low = df["Low"].to_numpy(dtype=float)
        close = df["Close"].to_numpy(dtype=float)

        pivot = (high + low + close) / 3
        r_range = high - low

        # Fibonacci Levels
        df["Pivot"] = pivot
        df["R1"] = pivot + 0.382 * r_range
        df["S1"] = pivot - 0.382 * r_range
        df["R2"] = pivot + 0.618 * r_range
        df["S2"] = pivot - 0.618 * r_range

        return df

    @staticmethod
    def fibonacci_retracements(df: pd.DataFrame, lookback: int = 50) -> pd.DataFrame:
        """
        Calculate Fibonacci retracement levels from recent swing high/low.
        Returns levels: 23.6%, 38.2%, 50%, 61.8%, 78.6%
        """
        try:
            if len(df) < lookback:
                return df

            recent_data = df.tail(lookback)

            swing_high = recent_data["High"].max()
            swing_low = recent_data["Low"].min()
            diff = swing_high - swing_low

            # Fibonacci levels (retracement from high to low)
            df["Fib_0"] = swing_high
            df["Fib_23.6"] = swing_high - 0.236 * diff
            df["Fib_38.2"] = swing_high - 0.382 * diff
            df["Fib_50"] = swing_high - 0.50 * diff
            df["Fib_61.8"] = swing_high - 0.618 * diff
            df["Fib_78.6"] = swing_high - 0.786 * diff
            df["Fib_100"] = swing_low

            # Flag if current price is near a key level (±1%)
            current_price = df["Close"].iloc[-1]
            tolerance = current_price * 0.01

            df["Near_Fib_Level"] = "None"
            for level_name in [
                "Fib_23.6",
                "Fib_38.2",
                "Fib_50",
                "Fib_61.8",
                "Fib_78.6",
            ]:
                level_value = df[level_name].iloc[-1]
                if abs(current_price - level_value) < tolerance:
                    df.loc[df.index[-1], "Near_Fib_Level"] = level_name
                    break

            return df
        except Exception:
            return df

    @staticmethod
    def supertrend(
        data: pd.DataFrame, period: int = 10, multiplier: float = 3.0
    ) -> pd.DataFrame:
        """
        Calculate SuperTrend indicator
        """
        import numpy as np

        df = data.copy()

        # Calculate ATR
        high_low = df["High"] - df["Low"]
        high_close = np.abs(df["High"] - df["Close"].shift())
        low_close = np.abs(df["Low"] - df["Close"].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = true_range.rolling(period).mean()

        # Calculate bands
        hl_avg = (df["High"] + df["Low"]) / 2
        upper_band = hl_avg + (multiplier * atr)
        lower_band = hl_avg - (multiplier * atr)

        # Initialize
        supertrend = np.zeros(len(df))
        direction = np.zeros(len(df), dtype=int)

        # Convert to numpy for much faster iteration
        upper_vals = upper_band.values
        lower_vals = lower_band.values
        close_vals = df["Close"].values

        for i in range(period, len(df)):
            if i > period:
                if close_vals[i - 1] <= upper_vals[i - 1]:
                    upper_vals[i] = min(upper_vals[i], upper_vals[i - 1])
                if close_vals[i - 1] >= lower_vals[i - 1]:
                    lower_vals[i] = max(lower_vals[i], lower_vals[i - 1])

            if close_vals[i] <= upper_vals[i]:
                supertrend[i] = upper_vals[i]
                direction[i] = -1
            else:
                supertrend[i] = lower_vals[i]
                direction[i] = 1

        return pd.DataFrame(
            {"SuperTrend": supertrend, "Direction": direction}, index=df.index
        )

    @staticmethod
    def ichimoku(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Ichimoku Cloud indicators"""
        # Tenkan-sen (Conversion Line): (9-period high + 9-period low)/2
        nine_period_high = df["High"].rolling(window=9).max()
        nine_period_low = df["Low"].rolling(window=9).min()
        df["TS"] = (nine_period_high + nine_period_low) / 2

        # Kijun-sen (Base Line): (26-period high + 26-period low)/2
        period26_high = df["High"].rolling(window=26).max()
        period26_low = df["Low"].rolling(window=26).min()
        df["KS"] = (period26_high + period26_low) / 2

        # Senkou Span A (Leading Span A): (Conversion Line + Base Line)/2
        df["SpanA"] = ((df["TS"] + df["KS"]) / 2).shift(26)

        # Senkou Span B (Leading Span B): (52-period high + 52-period low)/2
        period52_high = df["High"].rolling(window=52).max()
        period52_low = df["Low"].rolling(window=52).min()
        df["SpanB"] = ((period52_high + period52_low) / 2).shift(26)

        # Chikou Span (Lagging Span): Close plotted 26 days in the past
        df["Chikou"] = df["Close"].shift(-26)

        return df
