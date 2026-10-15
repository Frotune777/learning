import os
from datetime import datetime, timedelta

from rich.console import Console

from screeni.analysis.EnhancedBacktestValidator import (
    EnhancedBacktestValidator as BacktestValidator,
)
from screeni.analysis.StrategyOptimizer import StrategyOptimizer
from screeni.utils.SignalBus import SignalEmitter
from screeni.utils.config import ConfigManager
from screeni.data.DataIndexManager import DataIndexManager
from screeni.data.Fetcher import Fetcher
from screeni.data.PersistenceService import PersistenceService
from scanning.Scanner import (
    UltraOptimizedMultiTimeframeScanner as MultiTimeframeScanner,
)
from scanning.ScanningCriteria import ScanningCriteria
from screeni.strategies.AdvancedStrategies import TrendFollowingStrategy
from screeni.ui.StockUniverseSelector import StockUniverseSelector
from screeni.ui.telegram import TelegramService
from screeni.ui.VisualUI import VisualUI

console = Console()


class ScanOrchestrator(SignalEmitter):
    """Pure business logic for coordinating different scan types with VisualUI enhancement."""

    def __init__(self, menu_service=None, reporting_service=None):
        super().__init__()  # Initialize SignalEmitter for signal_bus
        self.menu = menu_service
        self.reporting = reporting_service
        self.console = console
        self.ui = VisualUI()

    def execute_quick_scan(self):
        """Quick scan with defaults - Nifty 50"""
        self.ui.render_header(
            "QUICK SCAN - NIFTY 50", "Running institutional grade screening pipeline"
        )
        selector = StockUniverseSelector()
        stocks = selector.get_stocks("1")
        if not stocks:
            self.ui.render_error("Failed to fetch Nifty 50 stocks")
            return
        self.run_scan(stocks, min_score=4, scan_name="Quick Scan - Nifty 50")

    def execute_custom_scan(self):
        """Custom scan with user selections"""
        selector = StockUniverseSelector()
        stocks = selector.show_menu()
        if not stocks:
            self.console.print("❌ No stocks selected!")
            return
        criteria_selector = ScanningCriteria()
        criteria = criteria_selector.show_menu()
        if not criteria:
            self.console.print("❌ No criteria selected!")
            return
        self.run_scan(
            stocks,
            min_score=criteria.get("min_score", 0),
            scan_name=f"Custom Scan - {criteria['name']}",
            scan_criteria=criteria,
        )

    def execute_watchlist_scan(self):
        """Scan watchlist stocks"""
        self.console.print("\n🚀 Watchlist Scan...")
        selector = StockUniverseSelector()
        stocks = selector._get_watchlist()
        if not stocks:
            self.console.print(
                "❌ No watchlist found! Create watchlist.xlsx with column 'Stock Code'"
            )
            return
        self.run_scan(stocks, min_score=4, scan_name="Watchlist Scan")

    def run_scan(self, stocks, min_score=4, scan_name="Stock Scan", scan_criteria=None):
        """Core scan execution pipeline."""
        self.console.print(f"\n{'=' * 80}\n{scan_name}\n{'=' * 80}\n")
        self.console.print(
            f"Scanning {len(stocks)} stocks...\nTimeframes: 1d, 1h\nMin Score: {min_score}\nBacktest validation: Enabled\n"
        )

        scanner = MultiTimeframeScanner()
        validator = BacktestValidator()
        results = scanner.scan_multiple_stocks(
            stocks,
            timeframes=["1d", "1h"],
            min_score=min_score,
            include_ml=True,
            scan_criteria=scan_criteria,
        )

        if results.empty:
            self.ui.render_error(
                f"No stocks passed screening (score >= {min_score})", is_warning=True
            )
            PersistenceService.clear_persistence()
            return

        phases = [
            {"name": "Initial Screening", "status": "Complete", "time": "12"},
            {"name": "Backtest Validation", "status": "In progress", "time": "0"},
            {"name": "ML Inference", "status": "⏳", "time": ""},
        ]
        self.ui.render_progress("BACKTEST PIPELINE", phases, 45)

        validated_results: list[dict] = []
        if self.menu and hasattr(self.menu, "display_live_backtest_header"):
            self.menu.display_live_backtest_pipeline(
                results, validator, TrendFollowingStrategy, validated_results
            )
        else:
            # Fallback if no menu service for live display
            for idx, row in results.iterrows():
                is_valid, bt_result = validator.validate_signal(
                    row["symbol"],
                    TrendFollowingStrategy,
                    min_return=10.0,
                    min_sharpe=0.8,
                )
                if is_valid:
                    validated_results.append(
                        {"result": row.to_dict(), "backtest": bt_result}
                    )

        if not validated_results:
            self.console.print("\n[red]❌ No stocks passed backtest validation[/red]")
            return

        # PERSISTENCE: Save validated signals and trades to SignalDatabase
        for item in validated_results:
            res = item["result"]
            bt = item["backtest"]

            # Prepare signal data
            signal_data = {
                "symbol": res["symbol"],
                "signal_type": res["signal"],
                "signal_score": res["score"],
                "signal_confidence": res["confidence"],
                "ml_prediction": res["ml_prediction"]["direction"]
                if res.get("ml_prediction")
                else None,
                "ml_confidence": res["ml_prediction"]["confidence"]
                if res.get("ml_prediction")
                else None,
                "ml_model_name": "Ensemble_v1",
                "stop_loss": res["risk_management"]["stop_loss"],
                "take_profit": res["risk_management"]["take_profit"],
                "risk_reward": res["risk_management"]["risk_reward_ratio"],
            }
            sig_id = self.emit_signal(signal_data)

            # Prepare trade data (synthetic from backtest for analytics)
            trade_data = {
                "signal_id": sig_id,
                "entry_price": res["risk_management"]["current_price"],
                "exit_price": res["risk_management"]["current_price"]
                * (1 + bt["avg_trade"] / 100),
                "entry_time": datetime.now().isoformat(),
                "exit_time": (datetime.now() + timedelta(days=5)).isoformat(),  # Proxy
                "position_size": 100000 / res["risk_management"]["current_price"],
                "pnl": bt["return"] * 1000,  # Approximate
                "pnl_percent": bt["return"],
                "r_multiple": bt["sharpe"],  # Proxy for simplified analytics
                "exit_reason": "Backtest Simulation",
            }
            self.emit_trade(trade_data)

        if self.reporting:
            self.reporting.print_results_table(validated_results)
            flat_results = self.reporting.prepare_export_data(validated_results)
            PersistenceService.save_results(flat_results, scan_name)

        DataIndexManager().update_index()
        self._handle_telegram_notification(scan_name, validated_results)
        return validated_results

    def _handle_telegram_notification(self, scan_name, validated_results):
        """Send formatted results to Telegram."""
        config = ConfigManager()
        import configparser

        config.getConfig(configparser.ConfigParser(strict=False))
        if config.telegramBotToken and config.telegramChatID:
            self.console.print("\n📤 Sending results to Telegram...")
            try:
                import asyncio

                tg = TelegramService(config.telegramBotToken, config.telegramChatID)
                tg_results = [
                    {
                        "symbol": item["result"]["symbol"],
                        "passed": True,
                        "reasons": {"final": f"Score: {item['result']['score']}"},
                    }
                    for item in validated_results
                ]
                asyncio.run(
                    tg.send_results_table(f"📊 {scan_name} Results", tg_results)
                )
                self.console.print("✅ Sent to Telegram!")
            except Exception as e:
                self.console.print(f"⚠️ Telegram Error: {e}")

    def train_ml_models(self):
        """Train ML models for selected stocks"""
        import subprocess

        self.console.print("\n" + "=" * 80 + "\nML MODEL TRAINING\n" + "=" * 80 + "\n")
        self.console.print(
            "This will train ML models for stocks in a universe.\nTraining takes 5-10 minutes per stock.\n"
        )
        self.console.print(
            "Select stock universe to train:\n\n 1 > Nifty 50 (~4-8 hours)\n 2 > Nifty Next 50 (~4-8 hours)\n 0 > Cancel\n"
        )
        choice = input("\n[+] Select option: ").strip().upper()
        if choice == "0":
            return
        universe_map = {"1": "Nifty 50", "2": "Nifty Next 50"}
        if choice in universe_map:
            universe = universe_map[choice]
            self.console.print(
                f"\n🤖 Training models for {universe}...\nThis will run in the foreground. Press Ctrl+C to cancel.\n"
            )
            try:
                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "python",
                        "train_all_models.py",
                        "--universe",
                        universe,
                    ],
                    cwd=os.getcwd(),
                )
                if result.returncode == 0:
                    self.console.print("\n✅ Training completed successfully!")
                else:
                    self.console.print("\n⚠️ Training completed with some errors")
            except KeyboardInterrupt:
                self.console.print("\n\n⚠️ Training interrupted by user")
            except Exception as e:
                self.console.print(f"\n❌ Error: {e}")
        else:
            self.console.print("\n❌ Invalid option")

    def run_optimizer(self):
        """Run strategy optimizer"""
        self.console.print(
            "\n" + "=" * 80 + "\n🎯 STRATEGY OPTIMIZER\n" + "=" * 80 + "\n"
        )
        symbol = (
            input("Enter stock symbol to optimize (e.g., SBIN, TCS): ").strip().upper()
        )
        if not symbol:
            return
        self.console.print(f"\nFetching data for {symbol}...")
        data = Fetcher().fetch_data(symbol, timeframe="1d", period="2y")
        if data is None or data.empty:
            self.console.print("❌ Failed to fetch data.")
            return
        StrategyOptimizer().optimize(data, symbol)
        input("\nPress Enter to continue...")
