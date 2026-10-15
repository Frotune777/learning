"""
Multi-Timeframe Backtest Engine
Extends BacktestInterface with multi-timeframe capabilities
"""

# Ensure src is in sys.path
import os
import sys

if os.path.join(os.getcwd(), "src") not in sys.path:
    sys.path.append(os.path.join(os.getcwd(), "src"))

from typing import Dict, List

import numpy as np
import pandas as pd
import scipy.stats as stats_sci
from backtesting import Backtest, Strategy

from src.data.Fetcher import Fetcher


class MultiTimeframeBacktest:
    """
    Backtest strategies across multiple timeframes
    """

    def __init__(self):
        self.fetcher = Fetcher()

    def run_multi_timeframe_backtest(
        self,
        symbol: str,
        strategy_class: type,
        timeframes: list[str] = ["5m", "15m", "1h", "1d"],
        period: str = "3mo",
        cash: float = 100000,
        commission: float = 0.001,
    ) -> dict:
        """
        Run backtest across multiple timeframes

        Args:
            symbol: Stock symbol
            strategy_class: Strategy class (must inherit from backtesting.Strategy)
            timeframes: List of timeframes to test
            period: Data period
            cash: Initial cash
            commission: Commission rate

        Returns:
            Dict with results per timeframe
        """
        results = {}

        for tf in timeframes:
            print(f"\n[{tf}] Running backtest for {symbol}...")

            # Fetch data
            data = self.fetcher.fetch_data(symbol, tf, period)

            if data.empty or len(data) < 50:
                print(f"  ⚠️ Insufficient data ({len(data)} rows)")
                results[tf] = None
                continue

            try:
                # Run backtest
                bt = Backtest(data, strategy_class, cash=cash, commission=commission)
                stats = bt.run()

                # Advanced Stats
                adv_stats = self._calculate_advanced_stats(stats)

                results[tf] = {
                    "Return [%]": stats["Return [%]"],
                    "Sharpe Ratio": stats.get("Sharpe Ratio", 0),
                    "Sortino Ratio": stats.get("Sortino Ratio", 0),
                    "Calmar Ratio": stats.get("Calmar Ratio", 0),
                    "Max Drawdown [%]": stats["Max. Drawdown [%]"],
                    "Win Rate [%]": stats.get("Win Rate [%]", 0),
                    "Trades": stats["# Trades"],
                    "Avg Trade [%]": stats.get("Avg. Trade [%]", 0),
                    **adv_stats,
                }

                print(
                    f"  ✅ Return: {stats['Return [%]']:.2f}% | Trades: {stats['# Trades']} | VaR: {adv_stats.get('VaR [95%]', 0):.2f}%"
                )

            except Exception as e:
                print(f"  ❌ Error: {e}")
                results[tf] = None

        return results

    def _calculate_advanced_stats(self, stats) -> dict:
        """Calculate VaR, p-value, and Information Ratio from backtest stats"""
        adv = {}
        try:
            # Equity curve or returns needed
            equity = stats["_equity_curve"]["Equity"]
            returns = equity.pct_change().dropna()

            # Benchmark (Buy and Hold)
            # Find first and last close to calculate B&H return
            # stats["_strategy"].data is available? No, stats["_strategy"].data leads to the data.
            # But backtesting.py stores the input data in stats["_strategy"].data
            bh_return = (
                stats["_strategy"].data.Close[-1] / stats["_strategy"].data.Close[0] - 1
            ) * 100
            adv["Buy & Hold Return [%]"] = bh_return

            if not returns.empty:
                # Value at Risk (VaR)
                adv["VaR [95%]"] = np.percentile(returns, 5) * 100

                # p-value for strategy significance (T-test vs 0 return)
                t_stat, p_val = stats_sci.ttest_1samp(returns, 0)
                adv["p-value"] = p_val

                # Information Ratio (Relative to Buy & Hold)
                # We need tracking error: std(strategy_returns - benchmark_returns)
                # For daily data, we assume equal steps
                # Simplified: (Ann. Strategy Return - Ann. B&H Return) / Ann. Tracking Error
                stats["Return (Ann.) [%]"] / 100
                # Approximate B&H Annualized if not provided by backtesting.py
                # Let's see if backtesting.py provides Buy & Hold Return [%] in stats
                bh_backtest_val = stats.get("Buy & Hold Return [%]")
                if bh_backtest_val is not None:
                    bh_return = bh_backtest_val

                # Calculate excess returns
                # We approximate excess return on a per-step basis
                # Note: This is a simplified IR without external benchmark data
                adv["Information Ratio"] = (
                    (stats["Return [%]"] - bh_return) / stats["Volatility (Ann.) [%]"]
                    if stats.get("Volatility (Ann.) [%]", 0) > 0
                    else 0
                )

            return adv
        except Exception as e:
            print(f"  ⚠️ Advanced stats error: {e}")
            return {"VaR [95%]": 0, "p-value": 1.0, "Information Ratio": 0}

    def walk_forward_optimization(
        self,
        symbol: str,
        strategy_class: type,
        timeframe: str = "1d",
        train_period: int = 120,  # days
        test_period: int = 30,  # days
        step: int = 30,  # days
        total_period: str = "1y",
    ) -> dict:
        """
        Walk-forward optimization
        Train on one period, test on next period, roll forward

        Args:
            symbol: Stock symbol
            strategy_class: Strategy class
            timeframe: Timeframe to test
            train_period: Training window (days)
            test_period: Testing window (days)
            step: Step size (days)
            total_period: Total data period

        Returns:
            Dict with walk-forward results
        """
        print(f"\n{'=' * 80}")
        print(f"WALK-FORWARD OPTIMIZATION: {symbol} ({timeframe})")
        print(f"Train: {train_period}d | Test: {test_period}d | Step: {step}d")
        print(f"{'=' * 80}\n")

        # Fetch data
        data = self.fetcher.fetch_data(symbol, timeframe, total_period)

        if data.empty:
            return {"error": "No data available"}

        results = []
        total_bars = len(data)

        # Convert days to bars (approximate)
        if timeframe == "1d":
            train_bars = train_period
            test_bars = test_period
            step_bars = step
        elif timeframe == "1h":
            train_bars = train_period * 6  # ~6 hours per day
            test_bars = test_period * 6
            step_bars = step * 6
        else:
            train_bars = int(train_period * 0.7)  # Rough estimate
            test_bars = int(test_period * 0.7)
            step_bars = int(step * 0.7)

        start_idx = 0

        while start_idx + train_bars + test_bars <= total_bars:
            # Split data
            train_data = data.iloc[start_idx : start_idx + train_bars]
            test_data = data.iloc[
                start_idx + train_bars : start_idx + train_bars + test_bars
            ]

            print(f"Window {len(results) + 1}:")
            print(
                f"  Train: {train_data.index[0].strftime('%Y-%m-%d')} to {train_data.index[-1].strftime('%Y-%m-%d')}"
            )
            print(
                f"  Test:  {test_data.index[0].strftime('%Y-%m-%d')} to {test_data.index[-1].strftime('%Y-%m-%d')}"
            )

            try:
                # Train (optimize on train data)
                bt_train = Backtest(
                    train_data, strategy_class, cash=100000, commission=0.001
                )

                # If strategy has optimizable params, optimize them
                # For demonstration, optimizing common params if they exist
                opt_params = {}
                if hasattr(strategy_class, "sma_period"):
                    opt_params["sma_period"] = range(10, 50, 10)
                if hasattr(strategy_class, "supertrend_period"):
                    opt_params["supertrend_period"] = range(7, 21, 7)

                if opt_params:
                    stats_train = bt_train.optimize(**opt_params, maximize="Return [%]")
                    # Extract best params
                    best_params = {
                        k: getattr(stats_train._strategy, k) for k in opt_params.keys()
                    }
                else:
                    stats_train = bt_train.run()
                    best_params = {}

                # Test (validate on test data using best params from train)
                bt_test = Backtest(
                    test_data, strategy_class, cash=100000, commission=0.001
                )
                stats_test = bt_test.run(**best_params)

                results.append(
                    {
                        "window": len(results) + 1,
                        "train_return": stats_train["Return [%]"],
                        "test_return": stats_test["Return [%]"],
                        "train_trades": stats_train["# Trades"],
                        "test_trades": stats_test["# Trades"],
                        "best_params": best_params,
                    }
                )

                print(f"  Train Return: {stats_train['Return [%]']:.2f}%")
                print(f"  Test Return:  {stats_test['Return [%]']:.2f}%\n")

            except Exception as e:
                print(f"  ❌ Error: {e}\n")

            start_idx += step_bars

        # Summary
        if results:
            avg_test_return = np.mean([r["test_return"] for r in results])
            std_test_return = np.std([r["test_return"] for r in results])

            return {
                "windows": results,
                "avg_test_return": avg_test_return,
                "std_test_return": std_test_return,
                "consistency": (avg_test_return / std_test_return)
                if std_test_return > 0
                else 0,
            }

        return {"error": "No valid windows"}

    def monte_carlo_simulation(
        self,
        symbol: str,
        strategy_class: type,
        timeframe: str = "1d",
        period: str = "1y",
        simulations: int = 100,
        cash: float = 100000,
    ) -> dict:
        """
        Monte Carlo simulation for risk assessment
        Randomly shuffle trade order to assess strategy robustness

        Args:
            symbol: Stock symbol
            strategy_class: Strategy class
            timeframe: Timeframe
            period: Data period
            simulations: Number of simulations
            cash: Initial cash

        Returns:
            Dict with simulation results
        """
        print(f"\n{'=' * 80}")
        print(f"MONTE CARLO SIMULATION: {symbol} ({timeframe})")
        print(f"Simulations: {simulations}")
        print(f"{'=' * 80}\n")

        # Fetch data
        data = self.fetcher.fetch_data(symbol, timeframe, period)

        if data.empty:
            return {"error": "No data available"}

        # Run base backtest
        bt = Backtest(data, strategy_class, cash=cash, commission=0.001)
        base_stats = bt.run()

        print(f"Base Strategy Return: {base_stats['Return [%]']:.2f}%\n")

        # Run simulations with randomized data
        sim_returns = []

        for i in range(simulations):
            # Shuffle data (maintain OHLC relationships)
            shuffled_data = data.sample(frac=1).reset_index(drop=True)
            shuffled_data.index = data.index  # Keep original dates

            try:
                bt_sim = Backtest(
                    shuffled_data, strategy_class, cash=cash, commission=0.001
                )
                stats_sim = bt_sim.run()
                sim_returns.append(stats_sim["Return [%]"])
            except Exception:
                pass

        if sim_returns:
            return {
                "base_return": base_stats["Return [%]"],
                "sim_mean": np.mean(sim_returns),
                "sim_std": np.std(sim_returns),
                "sim_min": np.min(sim_returns),
                "sim_max": np.max(sim_returns),
                "percentile_5": np.percentile(sim_returns, 5),
                "percentile_95": np.percentile(sim_returns, 95),
                "simulations": len(sim_returns),
            }

        return {"error": "No valid simulations"}


# Example Strategy for Testing
class SimpleMAStrategy(Strategy):
    """Simple Moving Average Crossover Strategy"""

    def init(self):
        close = self.data.Close
        self.sma20 = self.I(lambda x: pd.Series(x).rolling(20).mean(), close)
        self.sma50 = self.I(lambda x: pd.Series(x).rolling(50).mean(), close)

    def next(self):
        if self.sma20[-1] > self.sma50[-1] and self.sma20[-2] <= self.sma50[-2]:
            if not self.position:
                self.buy()
        elif self.sma20[-1] < self.sma50[-1] and self.sma20[-2] >= self.sma50[-2]:
            if self.position:
                self.position.close()
