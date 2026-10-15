#!/usr/bin/env python3
"""
File: interactive_scanner.py
Purpose: Main CLI entry point for the Stock Screener application.

Dependencies:
External:
- rich.console: [CLI formatting]
- sys, os: [environment management]
Internal:
- ui.MenuService: [UI menu management]
- scanning.ScanOrchestrator: [Core business logic]
- data.DataManagementService: [Data operations]
- ui.ReportingService: [Output formatting]
- config.ConfigManager: [System alerts and configuration]
- data.DataIndexManager: [Data tracking]
- data.PersistenceService: [Data storage]
- data.PaperTrading: [Virtual portfolio]
- utils.error_handling: [Safe execution wrappers]

Key Components:
Functions:
- show_detailed_view: Render deep-dive panel for a symbol
- handle_paper_trading: Manage virtual portfolio loop
- handle_presets: Manage scan criteria loop
- export_results: Multi-format export handler
- main: Application bootstrap and dispatch loop

Last Modified: 2026-02-19
Modified By: LLM
"""

import os
import sys

# Ensure src is in path for absolute imports
sys.path.append(os.path.join(os.getcwd(), "src"))

from rich.console import Console  # noqa: E402

from src.data.DataManagementService import DataManagementService  # noqa: E402
from src.data.manager import DataIndexManager  # noqa: E402
from src.data.PaperTrading import PaperTrading  # noqa: E402
from src.data.PersistenceService import PersistenceService  # noqa: E402
from src.engine.orchestrator import ScanOrchestrator  # noqa: E402
from src.ui.MenuService import MenuService  # noqa: E402
from src.ui.ReportingService import ReportingService  # noqa: E402
from src.ui.VisualUI import VisualUI  # noqa: E402
from src.utils.config import ConfigManager  # noqa: E402
from src.utils.error_handling import safe_execution  # noqa: E402

console = Console()
ui = VisualUI()
preset_manager = ConfigManager()  # Replaces PresetManager
paper_trading = PaperTrading()


@safe_execution
def show_detailed_view(item: dict) -> None:
    """
    Render a multi-panel deep dive view for a specific stock.

    Args:
        item (dict): Results item containing 'result' and 'backtest' details.
    """
    symbol = item.get("result", {}).get("symbol", "Unknown")
    ui.render_header(
        f"DETAILED VIEW: {symbol}", "Institutional structural & statistical analysis"
    )
    ui.render_detailed_view(symbol, item.get("result", {}))
    input("\n[cyan]Press [Enter] to return to results...[/cyan]")


@safe_execution
def handle_paper_trading() -> None:
    """
    Virtual portfolio management sub-loop.
    """
    while True:
        ui.render_header("PAPER TRADING 💰", "Track your virtual portfolio performance")
        summary = paper_trading.get_summary()
        console.print(f"  [cyan]Portfolio Balance:[/cyan] ₹{summary['cash']:,.2f}")
        console.print(f"  [cyan]Open Positions:[/cyan]    {summary['positions_count']}")

        console.print("\n  [cyan]1 >[/cyan] Buy Position")
        console.print("  [cyan]2 >[/cyan] Sell Position (Close)")
        console.print("  [cyan]3 >[/cyan] View Trade History")
        console.print("  [cyan]B >[/cyan] Back to Main Menu")

        choice = input("\n[+] Selection: ").strip().upper()
        if choice == "B":
            break
        elif choice == "1":
            symbol = input("  Enter Symbol: ").strip().upper()
            price = float(input("  Market Price: ").strip())
            value = float(input("  Allocation Amount: ").strip())
            success, msg = paper_trading.buy(symbol, price, value=value)
            console.print(f"  {msg}")
        elif choice == "2":
            symbol = input("  Enter Symbol to Sell: ").strip().upper()
            price = float(input("  Exit Price: ").strip())
            success, msg = paper_trading.sell(symbol, price)
            console.print(f"  {msg}")
        elif choice == "3":
            console.print("\n[bold]Trade Log:[/bold]")
            for t in paper_trading.trades:
                pnl = t.get("pnl", 0)
                pnl_color = "green" if pnl >= 0 else "red"
                pnl_str = (
                    f" | [ {pnl_color}]P&L: ₹{pnl:,.2f}[/{pnl_color}]"
                    if "pnl" in t
                    else ""
                )
                console.print(
                    f"  {t['type']} {t['symbol']} | {t['shares']} @ ₹{t['price']:,.2f}{pnl_str}"
                )
            input("\nPress [Enter]...")


@safe_execution
def handle_presets() -> None:
    """
    Scan criteria preset management sub-loop.
    """
    while True:
        ui.render_header(
            "SCAN PRESETS 📋", "Load or manage institutional screening criteria"
        )
        presets = preset_manager.list_presets()
        if not presets:
            console.print("  [yellow]No saved presets found.[/yellow]")
        else:
            for i, p in enumerate(presets, 1):
                console.print(f"  [cyan]{i} >[/cyan] {p}")

        console.print("\n  [cyan]N >[/cyan] Save Current (Coming Soon)")
        console.print("  [cyan]B >[/cyan] Back")

        choice = input("\n[+] Selection: ").strip().upper()
        if choice == "B":
            break
        input("\nPress [Enter]...")


@safe_execution
def export_results() -> None:
    """
    Multi-format export selection handler.
    """
    ui.render_header("EXPORT RESULTS 📤", "Generate institutional trade reports")
    df = PersistenceService.load_last_results()
    if df.empty:
        ui.render_error("No scan results in memory to export.", is_warning=True)
        return

    console.print("  [cyan]1 >[/cyan] Standard CSV Report")
    console.print("  [cyan]2 >[/cyan] Rich JSON Dataset (ML Ready)")
    console.print("  [cyan]3 >[/cyan] Generated Multiple Formats (Both)")

    choice = input("\n[+] Format Choice: ").strip()
    formats = []
    if choice in ["1", "3"]:
        formats.append("csv")
    if choice in ["2", "3"]:
        formats.append("json")

    if formats:
        PersistenceService.save_results(df, "Production_Export", formats=formats)
    else:
        console.print("[yellow]No format selected. Export aborted.[/yellow]")


def main() -> None:
    """
    Bootstrap services and execute main dispatch loop.
    """
    # Service Initialization
    menu = MenuService()
    reporting = ReportingService()
    orchestrator = ScanOrchestrator(menu, reporting)
    data_mgmt = DataManagementService()
    # config_mgmt = ConfigManagementService() # Consolidated into MenuService
    index_mgr = DataIndexManager()

    # Initial Health Check
    if not os.path.exists("data_index.csv"):
        menu.display_message(
            "⚠️ Initializing Data Index for the first time...", style="yellow"
        )
        index_mgr.update_index()

    while True:
        choice = menu.show_main_menu()

        # Dispatch Logic
        results = None
        if choice == "1":
            results = orchestrator.execute_quick_scan()
        elif choice == "2":
            results = orchestrator.execute_custom_scan()
        elif choice == "3":
            results = orchestrator.execute_watchlist_scan()
        elif choice == "4":
            orchestrator.train_ml_models()
        elif choice == "5":
            handle_presets()
        elif choice == "42":
            orchestrator.run_optimizer()
        elif choice == "P":
            handle_paper_trading()
        elif choice == "D":
            data_mgmt.data_health_dashboard()
        elif choice == "R":
            data_mgmt.repair_data(orchestrator.run_scan)
        elif choice == "H":
            data_mgmt.download_historical_data()
        elif choice == "U":
            data_mgmt.update_holidays()
        elif choice == "I":
            data_mgmt.view_data_index()
        elif choice == "C":
            menu.configure_alerts()
        elif choice == "E":
            export_results()
        elif choice == "T":
            menu.run_tests()
        elif choice == "S":
            os.system("uv run python src/data/DataHealthCheck.py")
        elif choice == "Q":
            console.print(
                "\n[yellow]Terminating services... Happy Trading! 🚀[/yellow]"
            )
            sys.exit(0)

        # Post-Scan Detailed Interaction Loop
        if results:
            while True:
                console.print(
                    f"\n{ui.colors.info('[?]')} Select symbol for [bold white]Detailed Analysis[/bold white] (or 'B' to return): ",
                    end="",
                )
                sub_choice = input().strip().upper()
                if sub_choice == "B":
                    break

                match = next(
                    (
                        item
                        for item in results
                        if item.get("result", {}).get("symbol", "").upper()
                        == sub_choice
                    ),
                    None,
                )
                if match:
                    show_detailed_view(match)
                else:
                    console.print(
                        f"  [red]Symbol '{sub_choice}' not found in results.[/red]"
                    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print(
            "\n[yellow]⚠️  Application interrupted by user. Closing safely...[/yellow]"
        )
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]❌ Critical System Error: {e}[/bold red]")
        sys.exit(1)
