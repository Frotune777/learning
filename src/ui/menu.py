import asyncio
import os
from datetime import datetime
from typing import Any, Callable, List

from rich import box
from rich.console import Console
from rich.table import Table

from src.utils.config import ConfigManager
from src.ui.telegram import TelegramService
from src.ui.VisualUI import VisualUI

console = Console()


class MenuService:
    """Handle all CLI interactions using VisualUI for premium aesthetics."""

    def __init__(self):
        self.console = console
        self.ui = VisualUI()

    def print_header(self):
        """Print standardized scanner header"""
        self.ui.render_header(
            "INTERACTIVE PRODUCTION SCANNER",
            f"Multi-Timeframe, ML-Enhanced, Backtest-Validated | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        )

    def show_main_menu(self) -> str:
        """Display categorized main menu using VisualUI specs."""
        sections = {
            "SCANNING & ANALYSIS": [
                {
                    "id": "1",
                    "name": "Quick Scan (Nifty 50)",
                    "emoji": "🚀",
                    "status": "Ready",
                    "details": "Nifty 50 universe",
                },
                {
                    "id": "2",
                    "name": "Custom Scan",
                    "emoji": "🔍",
                    "status": "Ready",
                    "details": "Custom parameters",
                },
                {
                    "id": "3",
                    "name": "Watchlist Scan",
                    "emoji": "📋",
                    "status": "Ready",
                    "details": "User watchlist",
                },
                {
                    "id": "4",
                    "name": "Train ML Models",
                    "emoji": "🤖",
                    "status": "Ready",
                    "details": "XGBoost/LSTM",
                },
                {
                    "id": "5",
                    "name": "Saved Presets",
                    "emoji": "📋",
                    "status": "Ready",
                    "details": "Load criteria",
                },
                {
                    "id": "42",
                    "name": "Auto-Optimize Strategy",
                    "emoji": "🎯",
                    "status": "Ready",
                    "details": "AI tuning",
                },
                {
                    "id": "P",
                    "name": "Paper Trading",
                    "emoji": "💰",
                    "status": "Ready",
                    "details": "Virtual portfolio",
                },
            ],
            "DATA MANAGEMENT": [
                {
                    "id": "D",
                    "name": "Health Dashboard",
                    "emoji": "📊",
                    "status": "Ready",
                    "details": "Visual audit",
                },
                {
                    "id": "R",
                    "name": "Repair Data",
                    "emoji": "🔧",
                    "status": "Ready",
                    "details": "Gap filling",
                },
                {
                    "id": "H",
                    "name": "Download Historical",
                    "emoji": "📥",
                    "status": "Ready",
                    "details": "Bulk fetch",
                },
                {
                    "id": "U",
                    "name": "Update Holidays",
                    "emoji": "📅",
                    "status": "Ready",
                    "details": "Annual check",
                },
                {
                    "id": "I",
                    "name": "View Data Index",
                    "emoji": "📑",
                    "status": "Ready",
                    "details": "Cache overview",
                },
            ],
            "SYSTEM & CONFIG": [
                {
                    "id": "C",
                    "name": "Configure Alerts",
                    "emoji": "🔔",
                    "status": "Ready",
                    "details": "Telegram/App",
                },
                {
                    "id": "E",
                    "name": "Export Results",
                    "emoji": "📤",
                    "status": "Ready",
                    "details": "CSV/JSON",
                },
                {
                    "id": "T",
                    "name": "Run Tests",
                    "emoji": "🧪",
                    "status": "Ready",
                    "details": "Pytest suite",
                },
                {
                    "id": "S",
                    "name": "System Health Check",
                    "emoji": "🏥",
                    "status": "Ready",
                    "details": "Service status",
                },
            ],
            "EXIT": [
                {
                    "id": "Q",
                    "name": "Quit",
                    "emoji": "❌",
                    "status": "",
                    "details": "Close application",
                }
            ],
        }

        self.render_header()  # Ensure header is printed if not already
        self.ui.render_menu("MAIN MENU", sections)
        return self.get_user_input("", lambda x: x.strip().upper())

    def render_header(self):
        """Helper to ensure header doesn't repeat unnecessarily"""
        if not hasattr(self, "_header_rendered"):
            self.print_header()
            self._header_rendered = True

    def get_user_input(self, prompt: str, validator: Callable = None) -> Any:
        """Generic validated input handler."""
        while True:
            try:
                user_input = input(prompt)
                if validator:
                    return validator(user_input)
                return user_input
            except Exception as e:
                self.console.print(f"[red]Invalid input: {e}[/red]")

    def display_message(self, message: str, style: str = "white"):
        """Display a simple message."""
        self.console.print(f"[{style}]{message}[/{style}]")

    def display_table(self, title: str, columns: List[str], rows: List[List[Any]]):
        """Display a generic table."""
        table = Table(title=title, box=box.SIMPLE)
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*[str(x) for x in row])
        self.console.print(table)

    def display_live_backtest_pipeline(
        self, results, validator, strategy_class, validated_results_list
    ):
        """Display a live updating table for backtest results."""
        from rich.live import Live

        live_table = Table(title="Live Backtest Results", box=box.SIMPLE)
        live_table.add_column("Stock", style="bold white")
        live_table.add_column("Status", justify="center")
        live_table.add_column("Return/Reason", style="dim")
        live_table.add_column("Trades", justify="right")

        with Live(live_table, refresh_per_second=4, console=self.console):
            for idx, row in results.iterrows():
                symbol = row["symbol"]

                is_valid, bt_result = validator.validate_signal(
                    symbol, strategy_class, min_return=10.0, min_sharpe=0.8
                )

                if is_valid:
                    validated_results_list.append(
                        {"result": row.to_dict(), "backtest": bt_result}
                    )
                    live_table.add_row(
                        symbol,
                        "[green]✅ PASS[/green]",
                        f"[green]{bt_result['return']:.1f}% return[/green]",
                        str(bt_result.get("trades", 0)),
                    )
                else:
                    reason = "Failed"
                    if "failure_reasons" in bt_result and bt_result["failure_reasons"]:
                        reason = bt_result["failure_reasons"][0]
                    elif "error" in bt_result:
                        reason = f"Error: {bt_result['error']}"
                    elif "return" in bt_result:
                        reason = f"Return {bt_result['return']:.1f}% < 10%"

                    live_table.add_row(
                        symbol,
                        "[red]❌ FAIL[/red]",
                        f"[red]{reason}[/red]",
                        str(bt_result.get("trades", 0)),
                    )

    # =========================================================================
    # Configuration & System Methods (Migrated from ConfigManagementService)
    # =========================================================================

    def configure_alerts(self) -> None:
        """Execute interactive Telegram alert configuration flow."""
        self.console.print("\n[bold cyan]🔔 Configure Telegram Alerts[/bold cyan]")

        config = ConfigManager()
        config.getConfig(config.parser)

        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Key", style="dim")
        table.add_column("Value", style="bold white")
        table.add_row(
            "Bot Token",
            config.telegramBotToken
            if config.telegramBotToken
            else "[red]Not Configured[/red]",
        )
        table.add_row(
            "Chat ID",
            config.telegramChatID
            if config.telegramChatID
            else "[red]Not Configured[/red]",
        )
        self.console.print(table)

        if input("\nUpdate credentials? (y/n): ").lower() == "y":
            config.telegramBotToken = input("Enter Bot Token: ").strip()
            config.telegramChatID = input("Enter Chat ID: ").strip()
            config.setConfig(config.parser, default=False, showFileCreatedText=False)
            self.console.print("[green]✅ Configuration updated![/green]")

        if config.telegramBotToken and config.telegramChatID:
            if input("\nSend test message? (y/n): ").lower() == "y":
                tg = TelegramService(config.telegramBotToken, config.telegramChatID)
                try:
                    asyncio.run(
                        tg.send_message(
                            "🔔 Test message from Screeni-py Interactive Scanner"
                        )
                    )
                    self.console.print("[green]✅ Test message sent![/green]")
                except Exception as e:
                    self.console.print(f"[red]❌ Failed to send: {e}[/red]")
        input("\nPress Enter to continue...")

    def run_tests(self) -> None:
        """Execute the project unit test suite via CLI."""
        self.console.print("\n[bold yellow]🚀 Running Tests...[/bold yellow]")
        os.system("uv run pytest tests/ -v")
        input("\nPress Enter to continue...")
