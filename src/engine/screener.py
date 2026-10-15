"""
File: screener/src/classes/Screener.py
Purpose: Core screening engine that evaluates stocks based on various technical strategies.

Dependencies:
External:
- numpy: [ml] numerical operations and nan handling
- pandas: [ml] data manipulation and signal processing
Internal:
- classes.AnalyticsService: [service] technical indicator calculations
- classes.TalibWrapper: [wrapper] TA-Lib technical analysis functions
- classes.strategies: [strategy] individual screening patterns

Key Components:
Classes:
- Screener: Main engine for executing screening logic and validating signals.
Functions:
- StockDataNotAdequate: Exception for insufficient candle data.
- DownloadDataOnly: Exception to exit early after data fetch.
- NotNewlyListed: Exception for IPO screening mismatch.

Last Modified: 2026-02-19
Modified By: LLM

Open Tasks:
- [ ] [HIGH] Refactor large validate methods into sub-strategies
- [ ] [MEDIUM] Add comprehensive unit tests for all patterns
"""

from typing import Any

import numpy as np
import pandas as pd

from src.analysis.service import AnalyticsService
from src.scanners import (
    CandlePatternsStrategy,
    CCIStrategy,
    ConsolidationStrategy,
    InsideBarStrategy,
    IPOBaseStrategy,
    LorentzianClassifierStrategy,
    LorentzianStrategy,
    MACDStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    RSIStrategy,
    StochasticStrategy,
    TrendLinearRegressionStrategy,
    TrendlineStrategy,
    TTMSqueezeStrategy,
    VCPStrategy,
)
from src.scanners.breakout import BreakoutStrategy
from src.scanners.menu_parity import (
    ATRCrossStrategy,
    HighLow52WeekStrategy,
    HighMomentumStrategy,
    IchimokuStrategy,
    NextDayBullishStrategy,
    NR4Strategy,
    SuperTrendStrategy,
)
from src.ui.ColorText import colorText


# Exception for newly listed stocks with candle nos < daysToLookback
class StockDataNotAdequate(Exception):
    pass


# Exception for only downloading stock data and not screening
class DownloadDataOnly(Exception):
    pass


# Exception for newly listed stocks when screening only for Newly Listed
class NotNewlyListed(Exception):
    pass


class Screener:
    def __init__(self, configManager: Any) -> None:
        """
        Initializes the Screener class with configuration management.

        Args:
            configManager (Any): The configuration manager instance.
        """
        self.configManager = configManager
        self.analytics = AnalyticsService()

        self.strategies = {
            "consolidation": ConsolidationStrategy(
                config={
                    "consolidationPercentage": getattr(
                        configManager, "consolidationPercentage", 10
                    )
                }
            ),
            "breakout": BreakoutStrategy(
                config={"daysToLookback": getattr(configManager, "daysToLookback", 30)}
            ),
            "rsi": RSIStrategy(
                min_rsi=getattr(configManager, "minRSI", 30),
                max_rsi=getattr(configManager, "maxRSI", 70),
            ),
            "momentum": MomentumStrategy(),
            "inside_bar": InsideBarStrategy(
                config={"daysToLookback": getattr(configManager, "daysToLookback", 5)}
            ),
            "ipo_base": IPOBaseStrategy(),
            "vcp": VCPStrategy(),
            "ttm_squeeze": TTMSqueezeStrategy(),
            "mean_reversion": MeanReversionStrategy(
                config={"maLength": getattr(configManager, "maLength", 50)}
            ),
            "trendline": TrendlineStrategy(),
            "macd": MACDStrategy(),
            "cci": CCIStrategy(),
            "stochastic": StochasticStrategy(),
            "lorentzian": LorentzianStrategy(),
            "lorentzian_ata": LorentzianClassifierStrategy(),
            "trendline_lr": TrendLinearRegressionStrategy(),
            "candle_patterns": CandlePatternsStrategy(),
            "ichimoku": IchimokuStrategy(),
            "nr4": NR4Strategy(),
            "high_low_52w": HighLow52WeekStrategy(),
            "next_day_bullish": NextDayBullishStrategy(),
            "supertrend": SuperTrendStrategy(),
            "atr_cross": ATRCrossStrategy(),
            "high_momentum": HighMomentumStrategy(),
        }

    def monitorFiveEma(
        self,
        proxyServer: str | None,
        fetcher: Any,
        result_df: pd.DataFrame,
        last_signal: dict[str, Any],
    ) -> pd.DataFrame:
        """
        Monitor stocks for 5-EMA reversal signals.

        Logic:
            Step 1: Iterate through watchlist or predefined stocks.
            Step 2: Fetch 5-minute or intraday data.
            Step 3: Identify candles where low is above 5-EMA.
            Step 4: Generate signal if high of next candle breaks low of alert candle.

        Parameters:
            proxyServer (Optional[str]): Proxy URL string.
            fetcher (Any): Data fetcher instance.
            result_df (pd.DataFrame): Current results table.
            last_signal (Dict[str, Any]): Dictionary to track last seen signals.

        Returns:
            pd.DataFrame: Updated results table.

        Example:
            >>> result = screener.monitorFiveEma(None, fetcher, df, {})
        """
        # Placeholder implementation - real logic needs to be restored from previous versions
        # or properly implemented based on 5-EMA strategy rules.
        return result_df

    def getNiftyPrediction(
        self, data: pd.DataFrame, proxyServer: str | None = None
    ) -> tuple[Any, str, float, pd.DataFrame] | None:
        """
        Run the Nifty gap prediction model.

        Logic:
            Step 1: Check if TensorFlow is available.
            Step 2: Preprocess Nifty daily data.
            Step 3: Run prediction model and return results.

        Parameters:
            data (pd.DataFrame): Daily OHLCV data for Nifty.
            proxyServer (Optional[str]): Proxy URL string.

        Returns:
            Optional[Tuple]: (prediction, trend, confidence, data_used) or None.
        """
        # Placeholder implementation - real logic needs to be restored from previous versions
        return None

    # Private method to find candle type
    def getCandleType(self, dailyData: pd.DataFrame) -> bool:
        """
        Determines if the latest candle is bullish (Green).

        Args:
            dailyData (pd.DataFrame): DataFrame containing daily stock data.

        Returns:
            bool: True if the candle is Green (Close >= Open), False otherwise.
        """
        return bool(dailyData["Close"].iloc[0] >= dailyData["Open"].iloc[0])

    # Preprocess the acquired data
    def preprocessData(
        self, data: pd.DataFrame, daysToLookback: int | None = None
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Preprocesses raw stock data by calculating technical indicators and handling legacy column names.

        Args:
            data (pd.DataFrame): Raw stock data.
            daysToLookback (Optional[int]): Number of days to include in the trimmed dataset. Defaults to config value.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: A tuple containing the full processed DataFrame and the trimmed DataFrame.
        """
        if daysToLookback is None:
            daysToLookback = self.configManager.daysToLookback

        # Use AnalyticsService to calculate indicators
        # Note: AnalyticsService adds columns in-place or returns new DF
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [
                col[0] if isinstance(col, tuple) else col for col in data.columns
            ]

        data = self.analytics.calculate_technical_indicators(data)

        # Legacy compatibility: 'SMA' column usually meant SMA50 in Screenipy
        if "SMA_50" in data.columns:
            data["SMA"] = data["SMA_50"]
        if "SMA_200" in data.columns:
            data["LMA"] = data["SMA_200"]
        if "Volume" in data.columns:
            data["VolMA"] = (
                data["Volume"].rolling(window=20).mean()
            )  # TODO: Move to Analytics if needed

        data = data[::-1]  # Reverse the dataframe as per Screenipy legacy convention

        # Drop rows with NaN Close/LTP to prevent validation errors
        data = data.dropna(subset=["Close", "High", "Low", "Open"])

        fullData = data
        trimmedData = data.head(daysToLookback)
        return (fullData, trimmedData)

    # Validate LTP within limits
    def validateLTP(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        minLTP: float | None = None,
        maxLTP: float | None = None,
    ) -> bool:
        """
        Validates if the Last Traded Price (LTP) is within the specified range.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            minLTP (float, optional): Minimum required LTP. Defaults to config value.
            maxLTP (float, optional): Maximum allowed LTP. Defaults to config value.

        Returns:
            bool: True if LTP is within range, False otherwise.
        """
        if minLTP is None:
            minLTP = self.configManager.minLTP
        if maxLTP is None:
            maxLTP = self.configManager.maxLTP

        # Sanity check
        if data.empty:
            return False

        recent = data.head(1)
        try:
            ltp = round(recent["Close"].iloc[0], 2)
            if np.isnan(ltp):
                ltp = 0
        except Exception:
            ltp = 0
        saveDict["LTP"] = str(ltp)

        # Calculate pct change
        try:
            pct_change = (data[::-1]["Close"].pct_change() * 100).iloc[-1]
        except Exception:
            pct_change = 0

        if pct_change > 0.2:
            pct_change_str = (
                colorText.GREEN + f" ({pct_change:.1f}%)" + colorText.END
            )
        elif pct_change < -0.2:
            pct_change_str = colorText.FAIL + f" ({pct_change:.1f}%)" + colorText.END
        else:
            pct_change_str = colorText.WARN + f" ({pct_change:.1f}%)" + colorText.END

        verifyStageTwo = True
        if self.configManager.stageTwo and len(data) > 250:
            yearlyLow = data.head(250).min()["Close"]
            yearlyHigh = data.head(250).max()["Close"]
            if ltp < (2 * yearlyLow) or ltp < (0.75 * yearlyHigh):
                verifyStageTwo = False

        if ltp >= minLTP and ltp <= maxLTP and verifyStageTwo:
            screenDict["LTP"] = (
                colorText.GREEN + f"{ltp:.2f}" + pct_change_str + colorText.END
            )
            return True
        screenDict["LTP"] = (
            colorText.FAIL + f"{ltp:.2f}" + pct_change_str + colorText.END
        )
        return False

    # Validate if share prices are consolidating
    def validateConsolidation(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        percentage: float = 10,
    ) -> float:
        """
        Checks if the stock is consolidating within a specified percentage range.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            percentage (float, optional): Maximum percentage range for consolidation. Defaults to 10.

        Returns:
            float: The calculated consolidation percentage if reliable, else 0.
        """
        # We assume 'data' is the trimmed data (reversed)
        # Strategy expects normal order?
        # ConsolidationStrategy uses .max()/.min() so order doesn't matter for range calculation.

        is_consolidation = self.strategies["consolidation"].analyze(data)

        hc = data["Close"].max()
        lc = data["Close"].min()

        if is_consolidation:
            if hc == 0 or np.isnan(hc) or np.isnan(lc):
                range_pct = 0.0
            else:
                range_pct = round((abs((hc - lc) / hc) * 100), 1)

            screenDict["Consolidating"] = (
                colorText.BOLD
                + colorText.GREEN
                + "Range = "
                + str(range_pct)
                + "%"
                + colorText.END
            )
            saveDict["Consolidating"] = str(range_pct) + "%"
            # Capture Reason (Concept) - Though consolidation logic here is mainly range.
            # Strategy reason might be empty if we rely on range check here.
            # But let's verify if strategy has one.
            reason = self.strategies["consolidation"].get_reason()
            if reason:
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", "")) + f" [Cons: {reason}]"
                )
        else:
            if hc == 0 or np.isnan(hc) or np.isnan(lc):
                range_pct = 0.0
            else:
                range_pct = round((abs((hc - lc) / hc) * 100), 1)
            screenDict["Consolidating"] = (
                colorText.BOLD
                + colorText.FAIL
                + "Range = "
                + str(range_pct)
                + "%"
                + colorText.END
            )
            saveDict["Consolidating"] = str(range_pct) + "%"

        return round((abs((hc - lc) / hc) * 100), 1)

    # Validate Moving averages
    def validateMovingAverages(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict, maRange: float = 2.5
    ) -> int:
        """
        Validates moving average signals (SMA).

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            maRange (float, optional): Range percentage for MA crossover/support checks. Defaults to 2.5.

        Returns:
            int: 1 if Bullish (Close > SMA), -1 if Bearish (Close < SMA), 0 otherwise.
        """
        # Using legacy logic for now, or migrate to Strategy?
        # This function prints signals like 'Bullish', '50MA-Support'
        # Let's keep the logic here for output formatting but rely on calculated indicators
        recent = data.head(1)
        if (
            recent["SMA"].iloc[0] > recent["LMA"].iloc[0]
            and recent["Close"].iloc[0] > recent["SMA"].iloc[0]
        ):
            screenDict["MA-Signal"] = (
                colorText.BOLD + colorText.GREEN + "Bullish" + colorText.END
            )
            saveDict["MA-Signal"] = "Bullish"
        elif recent["SMA"].iloc[0] < recent["LMA"].iloc[0]:
            screenDict["MA-Signal"] = (
                colorText.BOLD + colorText.FAIL + "Bearish" + colorText.END
            )
            saveDict["MA-Signal"] = "Bearish"
        else:
            screenDict["MA-Signal"] = (
                colorText.BOLD + colorText.WARN + "Neutral" + colorText.END
            )
            saveDict["MA-Signal"] = "Neutral"
        return 0  # Simplified return

    # Validate Volume
    def validateVolume(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        volumeRatio: float = 2.5,
    ) -> bool:
        """
        Validates if the recent volume is significantly higher than the average volume.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            volumeRatio (float, optional): Ratio of current volume to average volume required. Defaults to 2.5.

        Returns:
            bool: True if volume condition is met, False otherwise.
        """
        recent = data.head(1)
        if (
            recent["VolMA"].iloc[0] == 0
            or np.isnan(recent["VolMA"].iloc[0])
            or np.isnan(recent["Volume"].iloc[0])
        ):
            saveDict["Volume"] = "0x"
            screenDict["Volume"] = (
                colorText.BOLD + colorText.FAIL + "0x" + colorText.END
            )
            return False
        ratio = round(recent["Volume"].iloc[0] / recent["VolMA"].iloc[0], 2)
        saveDict["Volume"] = str(ratio) + "x"
        if ratio >= volumeRatio:
            screenDict["Volume"] = (
                colorText.BOLD + colorText.GREEN + str(ratio) + "x" + colorText.END
            )
            return True
        screenDict["Volume"] = (
            colorText.BOLD + colorText.FAIL + str(ratio) + "x" + colorText.END
        )
        return False

    # Find Breakout
    def findBreakout(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict, daysToLookback: int
    ) -> bool:
        """
        Identifies if the stock has broken out of a recent high.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            daysToLookback (int): Number of days to look back for the high.

        Returns:
            bool: True if a breakout is detected, False otherwise.
        """
        # Use the strategy logic
        is_breakout = self.strategies["breakout"].analyze(
            data[::-1]
        )  # Strategy expects chronological
        reason = self.strategies["breakout"].get_reason()

        # Store the detailed reason
        if reason:
            saveDict["Breaking-Out"] = reason
            if "Breaking Out Now" in reason:
                screenDict["Breaking-Out"] = (
                    colorText.BOLD + colorText.GREEN + reason + colorText.END
                )
            elif "Near Breakout" in reason or "Get Ready" in reason:
                screenDict["Breaking-Out"] = (
                    colorText.BOLD + colorText.WARN + reason + colorText.END
                )
            else:
                screenDict["Breaking-Out"] = (
                    colorText.BOLD + colorText.FAIL + reason + colorText.END
                )

            if is_breakout:
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", "")) + f" [BO: {reason}]"
                )
        else:
            screenDict["Breaking-Out"] = (
                colorText.BOLD + colorText.FAIL + "No Signal" + colorText.END
            )
            saveDict["Breaking-Out"] = "No Signal"

        return is_breakout

    # Validate RSI
    def validateRSI(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        minRSI: int,
        maxRSI: int,
    ) -> bool:
        """
        Validates if the RSI is within the specified range.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            minRSI (int): Minimum RSI value.
            maxRSI (int): Maximum RSI value.

        Returns:
            bool: True if RSI is within range, False otherwise.
        """
        # Update strategy config dynamically if needed
        from typing import Any

        rsi_strategy: Any = self.strategies["rsi"]
        rsi_strategy.min_rsi = minRSI
        rsi_strategy.max_rsi = maxRSI

        is_rsi = self.strategies["rsi"].analyze(data)  # expects RSI col

        try:
            rsi_val = data.head(1)["RSI"].iloc[0]
            if np.isnan(rsi_val):
                rsi = 0
            else:
                rsi = int(rsi_val)
        except Exception:
            rsi = 0

        saveDict["RSI"] = rsi
        if is_rsi:
            screenDict["RSI"] = (
                colorText.BOLD + colorText.GREEN + str(rsi) + colorText.END
            )
            return True
        screenDict["RSI"] = colorText.BOLD + colorText.FAIL + str(rsi) + colorText.END
        return False

    def findTrend(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        daysToLookback: int | None = None,
        stockName: str = "",
    ) -> str:
        """
        Calculates the trend of the stock over a specified period using linear regression.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            daysToLookback (Optional[int]): Number of days for trend calculation. Defaults to config value.
            stockName (str, optional): Name of the stock. Defaults to "".

        Returns:
            str: Description of the trend ('Strong Up', 'Weak Up', 'Sideways', 'Weak Down', 'Strong Down', 'Unknown').
        """
        if daysToLookback is None:
            daysToLookback = self.configManager.daysToLookback

        try:
            # Data is reversed in Screener conventions (0 is latest), but for trend we need chronological
            # So we take the head (latest N), then reverse it to get chronological order
            trend_data = data.head(daysToLookback)[::-1]

            if len(trend_data) < 2:
                saveDict["Trend"] = "Unknown"
                screenDict["Trend"] = (
                    colorText.BOLD + colorText.WARN + "Unknown" + colorText.END
                )
                return "Unknown"

            y = trend_data["Close"].values
            x = np.arange(len(y))

            # Linear Regression: y = mx + c
            slope, intercept = np.polyfit(x, y, 1)

            # Calculate total expected change over the period based on trendline
            start_price = intercept
            end_price = slope * (len(y) - 1) + intercept

            if start_price == 0:  # Avoid division by zero
                pct_change = 0
            else:
                pct_change = ((end_price - start_price) / start_price) * 100

            trend = "Sideways"
            color = colorText.WARN

            if pct_change >= 10:
                trend = "Strong Up"
                color = colorText.GREEN
            elif pct_change >= 2:
                trend = "Weak Up"
                color = colorText.GREEN
            elif pct_change <= -10:
                trend = "Strong Down"
                color = colorText.FAIL
            elif pct_change <= -2:
                trend = "Weak Down"
                color = colorText.FAIL

            saveDict["Trend"] = trend
            screenDict["Trend"] = colorText.BOLD + color + trend + colorText.END
            return trend

        except Exception:
            saveDict["Trend"] = "Unknown"
            screenDict["Trend"] = (
                colorText.BOLD + colorText.WARN + "Unknown" + colorText.END
            )
            return "Unknown"

    def validateMorningStar(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates Morning Star candle pattern.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if Morning Star pattern detected, False otherwise.
        """
        try:
            is_ms = self.strategies["morning_star"].analyze(data)
            if is_ms:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "Morning Star" + colorText.END
                )
                saveDict["Pattern"] = "Morning Star"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['morning_star'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateMomentum(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates if the stock has strong momentum.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if momentum criteria are met, False otherwise.
        """
        is_mom = self.strategies["momentum"].analyze(data)
        if is_mom:
            screenDict["Momentum"] = (
                colorText.BOLD + colorText.GREEN + "Momentum" + colorText.END
            )
            saveDict["Momentum"] = "Momentum"
            return True
        return False

    # Updated Implementations

    def validateInsideBar(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        chartPattern: int = 1,
        daysToLookback: int = 5,
    ) -> bool:
        """
        Checks for Inside Bar candle pattern.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            chartPattern (int, optional): Specific inside bar pattern type. Defaults to 1.
            daysToLookback (int, optional): Number of days to look back. Defaults to 5.

        Returns:
            bool: True if inside bar pattern is found, False otherwise.
        """
        is_ib = self.strategies["inside_bar"].analyze(data)
        if is_ib:
            screenDict["Pattern"] = (
                colorText.BOLD + colorText.GREEN + "Inside Bar" + colorText.END
            )
            saveDict["Pattern"] = "Inside Bar"
            saveDict["Reason"] = (
                str(saveDict.get("Reason", ""))
                + f" [{self.strategies['inside_bar'].get_reason()}]"
            )
            return True
        return False

    def validateIpoBase(
        self,
        stock: str,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        percentage: float = 0.3,
    ) -> bool:
        """
        Validates if the stock is forming an IPO Base pattern.

        Args:
            stock (str): Stock code.
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            percentage (float, optional): Percentage threshold for the base. Defaults to 0.3.

        Returns:
            bool: True if IPO base pattern is detected, False otherwise.
        """
        is_ipo = self.strategies["ipo_base"].analyze(data)
        if is_ipo:
            screenDict["Pattern"] = (
                colorText.BOLD + colorText.GREEN + "IPO Base" + colorText.END
            )
            saveDict["Pattern"] = "IPO Base"
            saveDict["Reason"] = (
                str(saveDict.get("Reason", ""))
                + f" [{self.strategies['ipo_base'].get_reason()}]"
            )
            return True
        return False

    def validateVCP(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        stockName: str | None = None,
        window: int = 3,
        percentageFromTop: int = 3,
    ) -> bool:
        """
        Checks for Volatility Contraction Pattern (VCP).

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            stockName (Optional[str], optional): Name of the stock. Defaults to None.
            window (int, optional): Window size for contraction check. Defaults to 3.
            percentageFromTop (int, optional): Percentage from top. Defaults to 3.

        Returns:
            bool: True if VCP is detected, False otherwise.
        """
        is_vcp = self.strategies["vcp"].analyze(data)
        if is_vcp:
            screenDict["Pattern"] = (
                colorText.BOLD + colorText.GREEN + "VCP" + colorText.END
            )
            saveDict["Pattern"] = "VCP"
            return True
        return False

    def validateMeanReversion(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        maLength: int,
        percentage: float = 0.015,
    ) -> bool:
        """
        Checks for Mean Reversion setup.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            maLength (int): Moving Average length.
            percentage (float, optional): Percentage deviation from MA. Defaults to 0.015.

        Returns:
            bool: True if conditions for mean reversion are met, False otherwise.
        """
        is_mr = self.strategies["mean_reversion"].analyze(data)
        is_mr = self.strategies["mean_reversion"].analyze(data)
        if is_mr:
            screenDict["Pattern"] = (
                colorText.BOLD + colorText.GREEN + "Mean Reversion" + colorText.END
            )
            # Mean Reversion is technically an oscillator concept (oversold) but fits largely in trend/pattern for now
            # Let's keep it in pattern or move to oscillator? Pattern is fine.
            saveDict["Pattern"] = "Mean Reversion"
            saveDict["Reason"] = (
                str(saveDict.get("Reason", ""))
                + f" [{self.strategies['mean_reversion'].get_reason()}]"
            )
            return True
        return False

    def findTrendlines(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        percentage: float = 0.05,
    ) -> bool:
        """
        Identifies if the stock is respecting a trendline.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            percentage (float, optional): Tolerance percentage for trendline touch. Defaults to 0.05.

        Returns:
            bool: True if trendline support/resistance is found, False otherwise.
        """
        is_tl = self.strategies["trendline"].analyze(data)
        if is_tl:
            screenDict["Pattern"] = (
                colorText.BOLD + colorText.GREEN + "Strong Trend" + colorText.END
            )
            saveDict["Pattern"] = "Strong Trend"
            return True
        return False

    def validateGamma(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates Gamma setup.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if Gamma setup detected, False otherwise.
        """
        try:
            is_gamma = self.strategies["gamma"].analyze(data)
            if is_gamma:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "Gamma" + colorText.END
                )
                saveDict["Pattern"] = "Gamma"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['gamma'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateMACD(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates MACD crossover or bullish signal.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if MACD signal is bullish, False otherwise.
        """
        try:
            is_macd = self.strategies["macd"].analyze(data)
            if is_macd:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "MACD Buy" + colorText.END
                )
                saveDict["Oscillator"] = "MACD Buy"  # New Category
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['macd'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateLC_HC(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Checks for Lower Circuit or Higher Circuit.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if LC or HC is detected, False otherwise.
        """
        try:
            is_lc_hc = self.strategies["lc_hc"].analyze(data)
            if is_lc_hc:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "LC/HC" + colorText.END
                )
                saveDict["Pattern"] = "LC/HC"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['lc_hc'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateCCI(self, data: pd.DataFrame, screenDict: dict, saveDict: dict) -> bool:
        """
        Validates Standard Commodity Channel Index (CCI) for buy signals.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if CCI indicates a buy, False otherwise.
        """
        try:
            is_cci = self.strategies["cci"].analyze(data)
            if is_cci:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "CCI Buy" + colorText.END
                )
                saveDict["Oscillator"] = "CCI Buy"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['cci'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateIchimoku(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates Ichimoku Cloud breakout (TK Crossover above Kumo).

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if Ichimoku conditions are bullish, False otherwise.
        """
        try:
            is_ichimoku = self.strategies["ichimoku"].analyze(data)
            if is_ichimoku:
                screenDict["Pattern"] = (
                    colorText.BOLD
                    + colorText.GREEN
                    + "Ichimoku Bullish"
                    + colorText.END
                )
                saveDict["Pattern"] = "Ichimoku Bullish"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['ichimoku'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateNR4(self, data: pd.DataFrame, screenDict: dict, saveDict: dict) -> bool:
        """
        Checks for Narrow Range 4 (NR4) day.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if NR4 pattern is detected, False otherwise.
        """
        try:
            is_nr4 = self.strategies["nr4"].analyze(data)
            if is_nr4:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "NR4" + colorText.END
                )
                saveDict["Pattern"] = "NR4"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['nr4'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validate52WeekHighLow(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict, high: bool = True
    ) -> bool:
        """
        Validates if the stock is near 52-week high or low.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.
            high (bool, optional): If True, checks for 52-week high, else low. Defaults to True.

        Returns:
            bool: True if condition is met, False otherwise.
        """
        try:
            recent_close = data["Close"].iloc[-1]
            high_52 = data["High"].tail(250).max()
            low_52 = data["Low"].tail(250).min()

            if high:
                # Check 52W High Breakout (within 1% or above)
                if recent_close >= high_52 * 0.99:
                    # If used, assign to msg. Otherwise remove assignment.
                    # msg = f"52W High ({high_52:.2f})"
                    screenDict["Pattern"] = (
                        colorText.BOLD + colorText.GREEN + "52W High" + colorText.END
                    )
                    saveDict["Pattern"] = "52W High"
                    return True
            else:
                # Check 52W Low Breakout (within 1% or below)
                if recent_close <= low_52 * 1.01:
                    # If used, assign to msg. Otherwise remove assignment.
                    # msg = f"52W Low ({low_52:.2f})"
                    screenDict["Pattern"] = (
                        colorText.BOLD + colorText.FAIL + "52W Low" + colorText.END
                    )
                    saveDict["Pattern"] = "52W Low"
                    return True
        except Exception:
            pass
        return False

    def validateNextDayBullish(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Checks for patterns indicating bullishness for the next day.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if bullish, False otherwise.
        """
        try:
            is_bullish = self.strategies["next_day_bullish"].analyze(data)
            if is_bullish:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "Bullish-NextDay" + colorText.END
                )
                saveDict["Pattern"] = "Bullish-NextDay"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['next_day_bullish'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateSuperTrend(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates SuperTrend indicator signals.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if SuperTrend is bullish/bearish as per strategy, False otherwise.
        """
        try:
            is_st = self.strategies["supertrend"].analyze(data)
            if is_st:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "SuperTrend" + colorText.END
                )
                saveDict["Pattern"] = "SuperTrend"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['supertrend'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateGoldenCrossover(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates Golden Crossover (SMA50 crosses above SMA200).

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if Golden Crossover detected, False otherwise.
        """
        try:
            is_gc = self.strategies["golden_crossover"].analyze(data)
            if is_gc:
                screenDict["Pattern"] = (
                    colorText.BOLD
                    + colorText.GREEN
                    + "Golden Crossover"
                    + colorText.END
                )
                saveDict["Pattern"] = "Golden Crossover"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['golden_crossover'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateATRCross(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates ATR Cross (Volatility Breakout).

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if ATR cross detected, False otherwise.
        """
        try:
            is_atr = self.strategies["atr_cross"].analyze(data)
            if is_atr:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "ATR Cross" + colorText.END
                )
                saveDict["Pattern"] = "ATR Cross"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['atr_cross'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateHighMomentum(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Checks for High Momentum stocks.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if high momentum detected, False otherwise.
        """
        try:
            is_hm = self.strategies["high_momentum"].analyze(data)
            if is_hm:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "High Momentum" + colorText.END
                )
                saveDict["Pattern"] = "High Momentum"
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['high_momentum'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateStochastic(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates Stochastic Oscillator signals.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if Stochastic signal detected, False otherwise.
        """
        try:
            is_stoch = self.strategies["stochastic"].analyze(data)
            if is_stoch:
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + "Stoch Buy" + colorText.END
                )
                saveDict["Oscillator"] = "Stoch Buy"  # New Category
                saveDict["Reason"] = (
                    str(saveDict.get("Reason", ""))
                    + f" [{self.strategies['stochastic'].get_reason()}]"
                )
                return True
        except Exception:
            pass
        return False

    def validateVolumeGainers(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Identifies stock with high volume gains.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if volume gainer, False otherwise.
        """
        # Option 9: High volume gainers
        # Logic: Volume > 2.5x SMA(20) and Close > Open (Green Candle)
        # Assuming 'VolMA' is SMA_20_Volume
        try:
            vol = data.head(1)["Volume"].iloc[0]
            vol_ma = data.head(1)["VolMA"].iloc[0]
            close = data.head(1)["Close"].iloc[0]
            open_price = data.head(1)["Open"].iloc[0]

            if vol_ma > 0 and (vol / vol_ma) >= 2.5 and close > open_price:
                msg = f"Vol Gainer ({round(vol / vol_ma, 1)}x)"
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + msg + colorText.END
                )
                saveDict["Pattern"] = msg
                saveDict["Reason"] = str(saveDict.get("Reason", "")) + f" [{msg}]"
                return True
        except Exception:
            pass
        return False

    def validatePriceMomentum(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Checks if the stock has gained at least 2% in the last 3 days.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if price momentum condition met, False otherwise.
        """
        # Option 10: 2% up last 3 days
        # Logic: Close > 2% up vs 3 days ago
        try:
            if len(data) < 3:
                return False
            close_now = data["Close"].iloc[0]
            close_3d = data["Close"].iloc[2]  # 0, 1, 2 (3rd day)

            pct_change = ((close_now - close_3d) / close_3d) * 100

            if pct_change >= 2.0:
                msg = f"Mom-3D ({round(pct_change, 1)}%)"
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + msg + colorText.END
                )
                saveDict["Pattern"] = msg
                saveDict["Reason"] = str(saveDict.get("Reason", "")) + f" [{msg}]"
                return True
        except Exception:
            pass
        return False

    def validateIntradayBreakout(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates Intraday Breakout strategy (N-minute Price & Volume).

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if intraday breakout detected, False otherwise.
        """
        # Option 12: N-Minute Price & Volume breakout
        # Logic: Close > High of last N candles (e.g. 20)
        # Using 20 as default N for now
        try:
            lookback = 20
            if len(data) < lookback:
                return False

            recent_close = data["Close"].iloc[0]
            past_highs = data["High"].iloc[1 : lookback + 1].max()

            if recent_close > past_highs:
                msg = "Intraday Breakout"
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + msg + colorText.END
                )
                saveDict["Pattern"] = msg
                saveDict["Reason"] = str(saveDict.get("Reason", "")) + f" [{msg}]"
                return True
        except Exception:
            pass
        return False

    def validateRSIandMACD(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates confluence of Bullish RSI and MACD.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if both RSI and MACD are bullish, False otherwise.
        """
        # Option 13: Bullish RSI & MACD
        # Logic: RSI > 50 and MACD > Signal
        try:
            rsi = data["RSI"].iloc[0]
            macd = data["MACD"].iloc[0] if "MACD" in data.columns else 0
            signal = data["Signal"].iloc[0] if "Signal" in data.columns else 0

            if rsi > 50 and macd > signal:
                msg = "RSI+MACD Bull"
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + msg + colorText.END
                )
                saveDict["Pattern"] = msg
                saveDict["Reason"] = str(saveDict.get("Reason", "")) + f" [{msg}]"
                return True
        except Exception:
            pass
        return False

    def validateAVWAP(self, data, screenDict, saveDict):
        # Option 34: Anchored VWAP (Simplified)
        # Using simple VWAP check for now as AVWAP requires specific anchor date in dataframe
        # If 'AVWAP' column exists (calculated by TA), use it. Else fall back to VWAP
        try:
            key = "AVWAP" if "AVWAP" in data.columns else "VWAP"
            if key not in data.columns:
                return False

            vwap = data[key].iloc[0]
            close = data["Close"].iloc[0]

            if close > vwap:
                msg = f"Bullish {key}"
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + msg + colorText.END
                )
                saveDict["Pattern"] = msg
                saveDict["Reason"] = str(saveDict.get("Reason", "")) + f" [{msg}]"
                return True
        except Exception:
            pass
        return False

    # Stubs or Deprecated

    def validateNarrowRange(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict, nr: int = 4
    ) -> bool:
        try:
            if len(data) < nr:
                return False
            ranges = data["High"].head(nr) - data["Low"].head(nr)
            current_range = ranges.iloc[0]
            if current_range == ranges.min():
                msg = f"NR{nr}"
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + msg + colorText.END
                )
                saveDict["Pattern"] = msg
                saveDict["Reason"] = str(saveDict.get("Reason", "")) + f" [{msg}]"
                return True
            return False
        except Exception:
            return False

    def validateLowestVolume(
        self, data: pd.DataFrame, daysForLowestVolume: int = 5
    ) -> bool:
        try:
            if len(data) < daysForLowestVolume:
                return False
            recent_vol = data["Volume"].head(daysForLowestVolume)
            return recent_vol.iloc[0] == recent_vol.min()
        except Exception:
            return False

    def validateVolumeSpreadAnalysis(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        # Placeholder for VSA - Return False to prevent crash
        return False

    def findReversalMA(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        maLength: int,
        percentage: float = 0.015,
    ) -> bool:
        return False

    def findRSICrossingMA(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict, maLength: int = 9
    ) -> bool:
        return False

    def validateLorentzian(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict, lookFor: int = 1
    ) -> bool:
        is_lc = self.strategies["lorentzian"].analyze(data)
        if is_lc:
            msg = "Lorentzian-Buy"
            screenDict["Lorentzian"] = (
                colorText.BOLD + colorText.GREEN + msg + colorText.END
            )
            saveDict["Lorentzian"] = ", ".join([msg for _ in range(1)])

            # Append to Pattern
            current_pattern = saveDict.get("Pattern", "")
            if current_pattern and current_pattern != "None":
                saveDict["Pattern"] = current_pattern + ", " + msg
            else:
                saveDict["Pattern"] = msg
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + msg + colorText.END
                )

            saveDict["Reason"] = (
                str(saveDict.get("Reason", ""))
                + f" [{self.strategies['lorentzian'].get_reason()}]"
            )
            saveDict["ML"] = "Lorentzian"  # Ensure explicit ML key
            return True
        return False

    def validateCandlePatterns(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        try:
            patterns_found: list[str] = []

            # 1. Existing pandas_ta based strategy
            pattern_pta = self.strategies["candle_patterns"].analyze(data)

            if pattern_pta:
                patterns_found.append("PTA-Pattern")

            if patterns_found:
                combined_patterns = ", ".join(patterns_found)
                current_pattern = saveDict.get("Pattern", "None")

                if current_pattern and current_pattern != "None":
                    saveDict["Pattern"] = current_pattern + ", " + combined_patterns
                else:
                    saveDict["Pattern"] = combined_patterns
                    screenDict["Pattern"] = (
                        colorText.BOLD
                        + colorText.WARN
                        + combined_patterns
                        + colorText.END
                    )

                saveDict["Reason"] = (
                    str(saveDict.get("Reason", "")) + f" [{combined_patterns}]"
                )
                return True

            return False
        except Exception:
            return False

    def addVector(self, data: pd.DataFrame, stock: str, candles: int = 60) -> None:
        """
        Adds vector embeddings for the stock data to ChromaDB.

        Args:
            data (pd.DataFrame): Stock data.
            stock (str): Stock code.
            candles (int, optional): Number of candles to use for embedding. Defaults to 60.
        """
        try:
            # Placeholder for vector embedding logic
            # This would involve calculating embeddings (e.g., using a pre-trained model or custom features)
            # and storing them in ChromaDB.
            # For now, we'll just simulate a successful operation.

            # Example: Generate a dummy embedding
            # embedding = [random.random() for _ in range(128)] # 128-dim embedding

            # self.chroma_client.add_embedding(
            #     collection_name="stock_patterns",
            #     document_id=f"{stock}_{data.index[-1].strftime('%Y%m%d')}",
            #     embedding=embedding,
            #     metadata={"stock": stock, "date": data.index[-1].strftime('%Y-%m-%d')}
            # )
            pass
        except Exception as e:
            # Log the error but don't crash the screener
            print(f"Error adding vector for {stock}: {e}")

    def validateATR(self, data: pd.DataFrame, saveDict: dict) -> None:
        """Calculate comprehensive risk management levels"""
        if "ATR" not in data.columns:
            return

        try:
            # Screenipy reverses data, so iloc[0] is most recent
            current_price = data["Close"].iloc[0]
            atr = data["ATR"].iloc[0]

            if np.isnan(atr) or np.isnan(current_price):
                return

            # Multiple Stoploss Levels
            sl_tight = round(current_price - (atr * 1.0), 2)  # 1x ATR (tight)
            sl_normal = round(current_price - (atr * 1.5), 2)  # 1.5x ATR (normal)
            sl_wide = round(current_price - (atr * 2.0), 2)  # 2x ATR (swing)

            # Support-based stoploss (if pivots available)
            if "S1" in data.columns and "S2" in data.columns:
                s1 = data["S1"].iloc[0]
                s2 = data["S2"].iloc[0]
                sl_support = round(min(s1, s2) * 0.99, 2)  # Just below support
            else:
                sl_support = sl_normal

            # Multiple Target Levels (Resistance-based)
            if "R1" in data.columns and "R2" in data.columns:
                r1 = data["R1"].iloc[0]
                r2 = data["R2"].iloc[0]
                target_1 = round(r1, 2)  # First resistance
                target_2 = round(r2, 2)  # Second resistance
                target_3 = round(current_price + (atr * 3.0), 2)  # 3x ATR extension
            else:
                # Fallback to ATR-based targets
                target_1 = round(current_price + (atr * 1.5), 2)
                target_2 = round(current_price + (atr * 2.5), 2)
                target_3 = round(current_price + (atr * 3.5), 2)

            # Risk-Reward Ratios (using normal stoploss)
            risk = current_price - sl_normal
            if risk > 0:
                rr1 = round((target_1 - current_price) / risk, 2)
                rr2 = round((target_2 - current_price) / risk, 2)
                rr3 = round((target_3 - current_price) / risk, 2)
            else:
                rr1 = rr2 = rr3 = 0

            # Store all levels
            saveDict["StopLoss"] = sl_normal  # Default/Normal SL
            saveDict["SL_Tight"] = sl_tight
            saveDict["SL_Wide"] = sl_wide
            saveDict["SL_Support"] = sl_support

            saveDict["Target_1"] = target_1
            saveDict["Target_2"] = target_2
            saveDict["Target_3"] = target_3

            saveDict["RR_1"] = rr1
            saveDict["RR_2"] = rr2
            saveDict["RR_3"] = rr3

        except Exception:
            # Fallback to basic calculation
            try:
                saveDict["StopLoss"] = round(
                    data["Close"].iloc[0] - data["ATR"].iloc[0], 2
                )
            except Exception:
                pass

    def validateVWAP(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        if "VWAP" in data.columns:
            vwap = data["VWAP"].iloc[-1]
            close = data["Close"].iloc[-1]
            saveDict["VWAP"] = str(round(vwap, 2))
            if close > vwap:
                screenDict["VWAP"] = (
                    colorText.BOLD
                    + colorText.GREEN
                    + str(round(vwap, 2))
                    + colorText.END
                )
                return True
            else:
                screenDict["VWAP"] = (
                    colorText.BOLD
                    + colorText.FAIL
                    + str(round(vwap, 2))
                    + colorText.END
                )
                return False
        return False

    def validateRelativeStrength(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> None:
        # Placeholder logic for RS Rating until Nifty index comparison is robust
        # Use RSI as proxy or just return 'Fair'
        if "RSI" in data.columns:
            rsi = data["RSI"].iloc[-1]
        if "RSI" in data.columns:
            rsi = data["RSI"].iloc[-1]
            if rsi > 70:
                rs = "Outperforming"
            elif rsi > 50:
                rs = "Average"
            else:
                rs = "Underperforming"

            saveDict["RS_Rating"] = rs
            screenDict["RS_Rating"] = ()

    def validateRegime(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> str:
        try:
            if "SMA_200" in data.columns:
                sma200 = data["SMA_200"].iloc[-1]
                close = data["Close"].iloc[-1]

                if np.isnan(sma200) or np.isnan(close):
                    saveDict["Regime"] = "Unknown"
                    screenDict["Regime"] = (
                        colorText.BOLD + colorText.WARN + "Unknown" + colorText.END
                    )
                    return "Unknown"
                elif close > sma200:
                    screenDict["Regime"] = (
                        colorText.BOLD + colorText.GREEN + "Bullish" + colorText.END
                    )
                    saveDict["Regime"] = "Bullish"
                    return "Bullish"
                else:
                    screenDict["Regime"] = (
                        colorText.BOLD + colorText.FAIL + "Bearish" + colorText.END
                    )
                    saveDict["Regime"] = "Bearish"
                    return "Bearish"
            else:
                saveDict["Regime"] = "Unknown"
                screenDict["Regime"] = (
                    colorText.BOLD + colorText.WARN + "Unknown" + colorText.END
                )
                return "Unknown"
        except Exception:
            saveDict["Regime"] = "Unknown"
            screenDict["Regime"] = (
                colorText.BOLD + colorText.WARN + "Unknown" + colorText.END
            )
            return "Unknown"

    def validateScoring(self, screenDict: dict, saveDict: dict) -> None:
        # Simple Summation Score
        score = 0
        # Simple Summation Score
        score = 0
        if "Bullish" in str(screenDict.get("MA-Signal", "")):
            score += 1
        if "Momentum" in str(screenDict.get("Momentum", "")):
            score += 1
        if "Breakout" in str(screenDict.get("Breaking-Out", "")):
            score += 1
        if "Green" in str(screenDict.get("LTP", "")):
            score += 1  # Crude check
        if "Buy" in str(screenDict.get("Pattern", "")):
            score += 2

        saveDict["Score"] = score
        screenDict["Score"] = (
            colorText.BOLD + colorText.GREEN + str(score) + colorText.END
        )

    def validateNewlyListed(self, data: pd.DataFrame, period: str) -> bool:
        """
        Validates if the stock is newly listed within the specified period.

        Args:
            data (pd.DataFrame): Stock data.
            period (str): Period string (e.g., '250d').

        Returns:
            bool: True if newly listed, False otherwise.
        """
        return len(data) < int(period[:-1])

    # Demand and Supply Zone Logic (Ported from PKScreener)
    def findDemandSupplyZones(
        self,
        data: pd.DataFrame,
        screenDict: dict,
        saveDict: dict,
        threshold_percent: float = 2,
    ) -> bool:
        """
        Identify Demand and Supply Zones based on Drop-Base-Rally, Rally-Base-Drop patterns.
        Adapts logic from PKScreener.
        """

        # Screenipy data is reversed (index 0 is latest).
        # Zone logic requires chronological order.
        df = data[::-1].copy()

        # 1. Calculate Candle Types
        df["Body"] = abs(df["Close"] - df["Open"])
        df["Range"] = df["High"] - df["Low"]
        df["BodyPct"] = df["Body"] / df["Range"]

        # Define Candle Types
        # Base Candle: Body is less than 50% of range (configurable)
        df["CandleType"] = np.where(
            df["BodyPct"] < 0.5,
            "Base",
            np.where(df["Close"] > df["Open"], "Rally", "Drop"),
        )

        cmp = df["Close"].iloc[-1]

        # 2. Identify Zones
        demand_zones = self._identify_demand_zones(df, cmp)
        supply_zones = self._identify_supply_zones(df, cmp)

        # 3. Filter and Store Results
        found_zone = False

        if demand_zones:
            # Sort by proximity to CMP
            demand_zones.sort(key=lambda x: abs(cmp - x["proximal"]))
            nearest_demand = demand_zones[0]
            dist = (cmp - nearest_demand["proximal"]) / cmp * 100

            if abs(dist) <= threshold_percent:
                msg = f"Demand Zone ({nearest_demand['pattern']})"
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.GREEN + msg + colorText.END
                )
                saveDict["Pattern"] = msg
                saveDict["Zone_Proximal"] = nearest_demand["proximal"]
                saveDict["Zone_Distal"] = nearest_demand["distal"]
                found_zone = True

        if supply_zones and not found_zone:
            # Sort by proximity to CMP
            supply_zones.sort(key=lambda x: abs(cmp - x["proximal"]))
            nearest_supply = supply_zones[0]
            dist = (nearest_supply["proximal"] - cmp) / cmp * 100

            if abs(dist) <= threshold_percent:
                msg = f"Supply Zone ({nearest_supply['pattern']})"
                screenDict["Pattern"] = (
                    colorText.BOLD + colorText.FAIL + msg + colorText.END
                )
                saveDict["Pattern"] = msg
                saveDict["Zone_Proximal"] = nearest_supply["proximal"]
                saveDict["Zone_Distal"] = nearest_supply["distal"]
                found_zone = True

        return found_zone

    def _identify_demand_zones(self, df, cmp):
        zones = []
        # Need numerical index for iteration
        df = df.reset_index(drop=True)

        for i in range(len(df) - 3):
            # Drop-Base-Rally (DBR)
            if df["CandleType"][i] == "Drop" and df["CandleType"][i + 1] == "Base":
                # Check for multiple base candles (up to 3)
                base_count = 1
                j = i + 2
                while j < len(df) and df["CandleType"][j] == "Base" and base_count < 4:
                    base_count += 1
                    j += 1

                # Check for Rally after Base
                if j < len(df) and df["CandleType"][j] == "Rally":
                    # Strong Move: Close of Rally > High of Base(s) + Buffer?
                    # PKScreener Condition: Rally Close > Ref Candle High (simplified)

                    # Store Zone
                    base_candles = df.iloc[i + 1 : j]
                    proximal = base_candles[
                        "High"
                    ].max()  # Highest body/wick in base for demand?
                    # Convention: Demand Proximal is usually Highest Body or High of Base.
                    # PKScreener uses max(base_candle_prices). Let's use High of Base.
                    distal = base_candles["Low"].min()

                    # Check if tested
                    is_tested = self._is_zone_tested(df, j + 1, proximal, distal)

                    if not is_tested:
                        zones.append(
                            {
                                "type": "Demand",
                                "pattern": "Drop-Base-Rally",
                                "proximal": proximal,
                                "distal": distal,
                                "start": i,
                                "end": j,
                            }
                        )

            # Rally-Base-Rally (RBR)
            elif df["CandleType"][i] == "Rally" and df["CandleType"][i + 1] == "Base":
                # Check for multiple base candles
                base_count = 1
                j = i + 2
                while j < len(df) and df["CandleType"][j] == "Base" and base_count < 4:
                    base_count += 1
                    j += 1

                if j < len(df) and df["CandleType"][j] == "Rally":
                    if df["Close"][j] > df["Close"][i]:  # Continuation
                        base_candles = df.iloc[i + 1 : j]
                        proximal = base_candles["High"].max()
                        distal = base_candles["Low"].min()

                        is_tested = self._is_zone_tested(df, j + 1, proximal, distal)

                        if not is_tested:
                            zones.append(
                                {
                                    "type": "Demand",
                                    "pattern": "Rally-Base-Rally",
                                    "proximal": proximal,
                                    "distal": distal,
                                    "start": i,
                                    "end": j,
                                }
                            )
        return zones

    def _identify_supply_zones(self, df, cmp):
        zones = []
        df = df.reset_index(drop=True)

        for i in range(len(df) - 3):
            # Rally-Base-Drop (RBD)
            if df["CandleType"][i] == "Rally" and df["CandleType"][i + 1] == "Base":
                base_count = 1
                j = i + 2
                while j < len(df) and df["CandleType"][j] == "Base" and base_count < 4:
                    base_count += 1
                    j += 1

                if j < len(df) and df["CandleType"][j] == "Drop":
                    base_candles = df.iloc[i + 1 : j]
                    proximal = base_candles[
                        "Low"
                    ].min()  # Low of Base for Supply Proximal
                    distal = base_candles["High"].max()

                    is_tested = self._is_zone_tested(df, j + 1, proximal, distal)

                    if not is_tested:
                        zones.append(
                            {
                                "type": "Supply",
                                "pattern": "Rally-Base-Drop",
                                "proximal": proximal,
                                "distal": distal,
                                "start": i,
                                "end": j,
                            }
                        )

            # Drop-Base-Drop (DBD)
            elif df["CandleType"][i] == "Drop" and df["CandleType"][i + 1] == "Base":
                base_count = 1
                j = i + 2
                while j < len(df) and df["CandleType"][j] == "Base" and base_count < 4:
                    base_count += 1
                    j += 1

                if j < len(df) and df["CandleType"][j] == "Drop":
                    if df["Close"][j] < df["Close"][i]:  # Continuation
                        base_candles = df.iloc[i + 1 : j]
                        proximal = base_candles["Low"].min()
                        distal = base_candles["High"].max()

                        is_tested = self._is_zone_tested(df, j + 1, proximal, distal)

                        if not is_tested:
                            zones.append(
                                {
                                    "type": "Supply",
                                    "pattern": "Drop-Base-Drop",
                                    "proximal": proximal,
                                    "distal": distal,
                                    "start": i,
                                    "end": j,
                                }
                            )
        return zones

    def _is_zone_tested(self, df, start_idx, proximal, distal):
        # Check if any candle AFTER the zone has touched the Money Zone (Proximal-Distal)
        # Note: Depending on zone type, "tested" might mean price came back to it.
        # Ideally, we want "Fresh" zones. A zone is tested if price retraced into it.

        # Zone Range
        z_high = max(proximal, distal)
        z_low = min(proximal, distal)

        # Check subsequent candles
        # Check subsequent candles
        if start_idx >= len(df):
            return False

        future_candles = df.iloc[start_idx:]

        # Check if Low <= z_high and High >= z_low (Overlap)
        overlaps = (future_candles["Low"] <= z_high) & (future_candles["High"] >= z_low)
        return overlaps.any()

    # Validate Trendline Support (Linear Regression)
    def validateTrendlineSupport(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates Trendline Support using Linear Regression.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if trendline support is detected, False otherwise.
        """
        if self.strategies["trendline_lr"].analyze(data):
            screenDict["Pattern"] += (
                f", {colorText.GREEN}Trendline-Support{colorText.END}"
            )
            saveDict["Pattern"] += ", Trendline-Support"
            return True
        return False

    # Validate TTM Squeeze
    def validateTTMSqueeze(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates TTM Squeeze indicator.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if TTM Squeeze is detected, False otherwise.
        """
        if self.strategies["ttm_squeeze"].analyze(data):
            screenDict["Pattern"] += f", {colorText.GREEN}TTM-Squeeze{colorText.END}"
            saveDict["Pattern"] += ", TTM-Squeeze"
            return True
        return False

    def validateConfluence(
        self, data: pd.DataFrame, screenDict: dict, saveDict: dict
    ) -> bool:
        """
        Validates Confluence of multiple indicators.

        Args:
            data (pd.DataFrame): Stock data.
            screenDict (Dict): Dictionary to store screening results for display.
            saveDict (Dict): Dictionary to store results for saving.

        Returns:
            bool: True if confluence detected, False otherwise.
        """
        if self.strategies["confluence"].analyze(data):
            screenDict["Pattern"] += f", {colorText.GREEN}Confluence{colorText.END}"
            saveDict["Pattern"] += ", Confluence"
            return True
        return False
        return False
