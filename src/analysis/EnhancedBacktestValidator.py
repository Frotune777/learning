"""
Enhanced Backtest Validator with Auto-Strategy Selection
"""

from src.ml.selector import AutoStrategySelector
from src.analysis.backtesting import MultiTimeframeBacktest


class EnhancedBacktestValidator:
    """
    Validates trading signals with backtesting
    Now supports auto-strategy selection
    """

    def __init__(self):
        self.backtester = MultiTimeframeBacktest()
        self.auto_selector = AutoStrategySelector()

    def validate_signal(
        self,
        symbol: str,
        strategy_class=None,  # Now optional!
        timeframe: str = "1d",
        period: str = "1y",
        min_return: float = 10.0,
        min_sharpe: float = 0.8,
        min_sortino: float = 1.0,
        min_calmar: float = 1.0,
        min_trades: int = 5,
        auto_select: bool = False,  # NEW: Auto-select best strategy
    ):
        """
        Validate signal with backtesting

        Args:
            symbol: Stock symbol
            strategy_class: Strategy to test (None = auto-select)
            timeframe: Timeframe
            period: Data period
            min_return: Minimum return required
            min_sharpe: Minimum Sharpe ratio
            min_trades: Minimum trades for significance
            auto_select: If True, test all strategies and pick best

        Returns:
            (is_valid, results_dict)
        """
        # Auto-select strategy if requested or no strategy provided
        if auto_select or strategy_class is None:
            strategy_class, strategy_name, all_results = (
                self.auto_selector.select_best_strategy(
                    symbol, timeframe, period, verbose=False
                )
            )

            if strategy_class is None:
                return False, {
                    "error": "No valid strategy found",
                    "failure_reasons": ["All strategies failed backtesting"],
                }
        else:
            strategy_name = strategy_class.__name__

        # Run backtest
        try:
            bt_results = self.backtester.run_multi_timeframe_backtest(
                symbol,
                strategy_class,
                timeframes=[timeframe],
                period=period,
                cash=100000,
                commission=0.001,
            )

            if not bt_results[timeframe]:
                return False, {
                    "error": "Backtest failed",
                    "failure_reasons": ["No backtest results"],
                }

            result = bt_results[timeframe]

            # Validate criteria
            failure_reasons = []

            if result["Return [%]"] < min_return:
                failure_reasons.append(
                    f"Return {result['Return [%]']:.1f}% < {min_return}% required"
                )

            if result["Sharpe Ratio"] < min_sharpe:
                failure_reasons.append(
                    f"Sharpe {result['Sharpe Ratio']:.2f} < {min_sharpe} required"
                )

            if result.get("Sortino Ratio", 0) < min_sortino:
                failure_reasons.append(
                    f"Sortino {result.get('Sortino Ratio', 0):.2f} < {min_sortino} required"
                )

            if result.get("Calmar Ratio", 0) < min_calmar:
                failure_reasons.append(
                    f"Calmar {result.get('Calmar Ratio', 0):.2f} < {min_calmar} required"
                )

            if result["Trades"] < min_trades:
                failure_reasons.append(
                    f"Only {result['Trades']} trades (need {min_trades}+ for significance)"
                )

            is_valid = len(failure_reasons) == 0

            return is_valid, {
                "return": result["Return [%]"],
                "sharpe": result["Sharpe Ratio"],
                "sortino": result.get("Sortino Ratio", 0),
                "calmar": result.get("Calmar Ratio", 0),
                "win_rate": result["Win Rate [%]"],
                "trades": result["Trades"],
                "max_drawdown": result["Max Drawdown [%]"],
                "avg_trade": result["Avg Trade [%]"],
                "strategy_used": strategy_name,
                "failure_reasons": failure_reasons if not is_valid else [],
            }

        except Exception as e:
            return False, {
                "error": str(e),
                "failure_reasons": [f"Backtest error: {str(e)[:100]}"],
            }

    def validate_with_best_strategy(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1y",
        min_return: float = 10.0,
        min_sharpe: float = 0.8,
    ):
        """
        Convenience method: Always use best strategy
        """
        return self.validate_signal(
            symbol,
            strategy_class=None,
            timeframe=timeframe,
            period=period,
            min_return=min_return,
            min_sharpe=min_sharpe,
            auto_select=True,
        )

    def suggest_strategy(self, symbol: str, timeframe: str = "1d"):
        """
        Suggest optimal strategy based on market conditions

        Returns:
            (strategy_class, strategy_name, reasoning)
        """
        strategy, name, condition, reasoning = (
            self.auto_selector.suggest_strategy_by_market_condition(
                symbol, timeframe, verbose=False
            )
        )

        return strategy, name, reasoning
