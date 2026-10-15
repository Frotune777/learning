"""
Auto-Strategy Selector
Intelligently selects best strategy based on:
1. Backtest performance on historical data
2. Market condition analysis (trending/ranging/volatile)
3. Stock characteristics (volatility, volume, etc.)
"""

# Ensure src is in sys.path
import os
import sys

if os.path.join(os.getcwd(), "src") not in sys.path:
    sys.path.append(os.path.join(os.getcwd(), "src"))

from typing import Any

import numpy as np
import pandas as pd

from src.analysis.MultiTimeframeBacktest import MultiTimeframeBacktest


class AutoStrategySelector:
    """
    Automatically selects the best strategy for a stock.

    Note:
        `self.strategies` is an empty registry by default. Populate it with
        `{display_name: StrategyClass}` entries (StrategyClass must inherit
        from backtesting.Strategy) before calling `select_best_strategy()`
        or `compare_all_strategies()`.

        `suggest_strategy_by_market_condition()` works without any registered
        strategies — it derives its recommendation from price action alone.
    """

    def __init__(self):
        self.backtester = MultiTimeframeBacktest()

        # Strategy registry — populate before calling select_best_strategy()
        # or compare_all_strategies(). Keys are display names, values are
        # classes that inherit from backtesting.Strategy.
        self.strategies: dict[str, Any] = {}

    def select_best_strategy(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1y",
        verbose: bool = True,
    ):
        """
        Test all strategies and return the best one

        Args:
            symbol: Stock symbol
            timeframe: Timeframe to test
            period: Data period
            verbose: Print progress

        Returns:
            (best_strategy_class, best_strategy_name, results_dict)
        """
        if verbose:
            print(f"\n{'=' * 80}")
            print(f"AUTO-SELECTING BEST STRATEGY FOR {symbol}")
            print(f"{'=' * 80}\n")

        results = {}

        # Test each strategy
        for name, strategy_class in self.strategies.items():
            if verbose:
                print(f"Testing {name}...", end=" ")

            try:
                bt_results = self.backtester.run_multi_timeframe_backtest(
                    symbol,
                    strategy_class,
                    timeframes=[timeframe],
                    period=period,
                    cash=100000,
                    commission=0.001,
                )

                if bt_results[timeframe]:
                    result = bt_results[timeframe]

                    # Calculate composite score
                    score = self._calculate_strategy_score(result)

                    results[name] = {
                        "strategy_class": strategy_class,
                        "return": result["Return [%]"],
                        "sharpe": result["Sharpe Ratio"],
                        "win_rate": result["Win Rate [%]"],
                        "trades": result["Trades"],
                        "score": score,
                    }

                    if verbose:
                        print(
                            f"✅ Score: {score:.2f} (Return: {result['Return [%]']:.2f}%)"
                        )
                else:
                    if verbose:
                        print("❌ Failed")

            except Exception as e:
                if verbose:
                    print(f"❌ Error: {str(e)[:50]}")

        if not results:
            if verbose:
                print("\n❌ No valid strategies found")
            return None, None, None

        # Select best strategy by score
        best_name = max(results, key=lambda k: results[k]["score"])
        best_result = results[best_name]

        if verbose:
            print(f"\n{'=' * 80}")
            print(f"BEST STRATEGY: {best_name}")
            print(f"{'=' * 80}")
            print(f"  Score: {best_result['score']:.2f}")
            print(f"  Return: {best_result['return']:.2f}%")
            print(f"  Sharpe: {best_result['sharpe']:.2f}")
            print(f"  Win Rate: {best_result['win_rate']:.1f}%")
            print(f"  Trades: {best_result['trades']}")
            print(f"{'=' * 80}\n")

        return best_result["strategy_class"], best_name, results

    def suggest_strategy_by_market_condition(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "3mo",
        verbose: bool = True,
    ):
        """
        Analyze market conditions and suggest optimal strategy

        Returns:
            (suggested_strategy_class, strategy_name, market_condition, reasoning)
        """
        if verbose:
            print(f"\n{'=' * 80}")
            print(f"ANALYZING MARKET CONDITIONS FOR {symbol}")
            print(f"{'=' * 80}\n")

        # Fetch data
        from src.data.Fetcher import Fetcher

        fetcher = Fetcher()
        data = fetcher.fetch_data(symbol, timeframe, period)

        if data.empty:
            return None, None, None, "No data available"

        # Analyze market conditions
        condition = self._analyze_market_condition(data)

        if verbose:
            print(f"Market Condition: {condition['type'].upper()}")
            print(f"  Trend Strength: {condition['trend_strength']:.2f}")
            print(f"  Volatility: {condition['volatility']:.2f}%")
            print(f"  Volume Trend: {condition['volume_trend']}")
            print()

        # Suggest strategy based on conditions
        suggestion = self._match_strategy_to_condition(condition)

        if verbose:
            print(f"Suggested Strategy: {suggestion['name']}")
            print(f"Reasoning: {suggestion['reasoning']}")
            print(f"{'=' * 80}\n")

        return (
            self.strategies[suggestion["name"]],
            suggestion["name"],
            condition,
            suggestion["reasoning"],
        )

    def _calculate_strategy_score(self, result):
        """
        Calculate composite score for strategy
        Weights: Return (40%), Sharpe (30%), Win Rate (20%), Trades (10%)
        """
        # Normalize metrics
        return_score = min(result["Return [%]"] / 50.0, 1.0) * 40  # Max 50% return
        sharpe_score = min(result["Sharpe Ratio"] / 2.0, 1.0) * 30  # Max 2.0 Sharpe
        win_rate_score = (result["Win Rate [%]"] / 100.0) * 20

        # Penalize if too few trades
        if result["Trades"] < 5:
            trade_score = 0
        elif result["Trades"] < 10:
            trade_score = 5
        else:
            trade_score = 10

        return return_score + sharpe_score + win_rate_score + trade_score

    def _analyze_market_condition(self, data):
        """
        Analyze market conditions from price data

        Returns:
            Dict with market condition metrics
        """
        close = data["Close"]

        # 1. Trend Strength (ADX-like)
        high_low = data["High"] - data["Low"]
        high_close = abs(data["High"] - close.shift())
        low_close = abs(data["Low"] - close.shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(14).mean()

        # Price movement vs ATR
        price_change = abs(close - close.shift(20))
        trend_strength = (price_change / atr).iloc[-1] if atr.iloc[-1] > 0 else 0

        # 2. Volatility
        returns = close.pct_change()
        volatility = returns.std() * np.sqrt(252) * 100  # Annualized

        # 3. Trend Direction
        sma_20 = close.rolling(20).mean()
        sma_50 = close.rolling(50).mean()

        if close.iloc[-1] > sma_20.iloc[-1] > sma_50.iloc[-1]:
            trend_direction = "uptrend"
        elif close.iloc[-1] < sma_20.iloc[-1] < sma_50.iloc[-1]:
            trend_direction = "downtrend"
        else:
            trend_direction = "ranging"

        # 4. Volume Trend
        volume = data["Volume"]
        volume_sma = volume.rolling(20).mean()

        if volume.iloc[-5:].mean() > volume_sma.iloc[-1]:
            volume_trend = "increasing"
        else:
            volume_trend = "decreasing"

        # 5. Market Type
        if trend_strength > 1.5 and volatility < 30:
            market_type = "trending"
        elif volatility > 40:
            market_type = "volatile"
        else:
            market_type = "ranging"

        return {
            "type": market_type,
            "trend_strength": trend_strength,
            "trend_direction": trend_direction,
            "volatility": volatility,
            "volume_trend": volume_trend,
        }

    def _match_strategy_to_condition(self, condition):
        """
        Match optimal strategy to market conditions
        """
        market_type = condition["type"]
        trend_dir = condition["trend_direction"]
        volatility = condition["volatility"]

        # Decision logic
        if market_type == "trending" and trend_dir == "uptrend":
            return {
                "name": "TrendFollowing",
                "reasoning": "Strong uptrend detected. Trend-following strategy works best in trending markets.",
            }

        elif market_type == "volatile" or volatility > 40:
            return {
                "name": "RSIMeanReversion",
                "reasoning": "High volatility detected. Mean reversion strategy captures oversold bounces.",
            }

        elif market_type == "ranging":
            return {
                "name": "RSIMeanReversion",
                "reasoning": "Ranging market detected. Mean reversion works best in sideways markets.",
            }

        else:
            # Default to most robust strategy
            return {
                "name": "SuperTrendOBV",
                "reasoning": "Mixed conditions. SuperTrend+OBV provides balanced approach with volume confirmation.",
            }

    def compare_all_strategies(self, symbol, timeframe="1d", period="1y"):
        """
        Comprehensive comparison of all strategies

        Returns:
            DataFrame with comparison
        """
        print(f"\n{'=' * 80}")
        print(f"COMPREHENSIVE STRATEGY COMPARISON: {symbol}")
        print(f"{'=' * 80}\n")

        comparison = []

        for name, strategy_class in self.strategies.items():
            print(f"Testing {name}...")

            try:
                bt_results = self.backtester.run_multi_timeframe_backtest(
                    symbol, strategy_class, timeframes=[timeframe], period=period
                )

                if bt_results[timeframe]:
                    result = bt_results[timeframe]
                    comparison.append(
                        {
                            "Strategy": name,
                            "Return (%)": result["Return [%]"],
                            "Sharpe": result["Sharpe Ratio"],
                            "Win Rate (%)": result["Win Rate [%]"],
                            "Trades": result["Trades"],
                            "Avg Trade (%)": result["Avg Trade [%]"],
                            "Max DD (%)": result["Max Drawdown [%]"],
                            "Score": self._calculate_strategy_score(result),
                        }
                    )
            except Exception as e:
                print(f"  Error: {e}")

        if comparison:
            df = pd.DataFrame(comparison)
            df = df.sort_values("Score", ascending=False)

            print(f"\n{'=' * 80}")
            print("COMPARISON RESULTS")
            print(f"{'=' * 80}\n")
            print(df.to_string(index=False))
            print(f"\n{'=' * 80}\n")

            return df

        return None


# Test function
def test_auto_selector():
    """Test auto-strategy selector"""
    selector = AutoStrategySelector()

    # Test 1: Select best strategy by backtest
    print("\nTest 1: Auto-select best strategy")
    best_strategy, best_name, results = selector.select_best_strategy("SBIN")

    # Test 2: Suggest by market conditions
    print("\nTest 2: Suggest by market conditions")
    suggested, name, condition, reasoning = (
        selector.suggest_strategy_by_market_condition("SBIN")
    )

    # Test 3: Compare all
    print("\nTest 3: Compare all strategies")
    selector.compare_all_strategies("SBIN")


if __name__ == "__main__":
    test_auto_selector()
