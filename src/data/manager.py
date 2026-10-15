"""
File: src/classes/DataManagementService.py
Purpose: Decouple data repair, download, and index logic from the main entry point.

Dependencies:
External:
- pandas>=2.2.3: [data] result and index processing
- rich>=13.9.2: [CLI] terminal UI formatting
Internal:
- download_historical_data: [download] data retrieval logic
- repair_data: [repair] raw data restoration
- classes.DataHealthCheck: [health] integrity validation
- classes.DataIndexManager: [index] data tracking
- classes.HolidayFetcher: [config] holiday synchronization
- classes.StockUniverseSelector: [selector] universe filtering

Key Components:
Classes:
- DataManagementService: Service orchestrator for data-related CLI operations.
Functions:
- data_health_dashboard: Render interactive health summary.
- repair_data: Orchestrate raw data and screening result repair.
- download_historical_data: Trigger bulk OHLCV downloads.
- update_holidays: Synchronize trading holiday configuration.
- view_data_index: Display and refresh stock data index.

Last Modified: 2026-02-19
Modified By: LLM

Open Tasks:
- [ ] [MEDIUM] Implement background auto-indexing [4h]
"""

from collections.abc import Callable
from typing import Any, List, Optional

import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from src.data.DataHealthCheck import DataHealthCheck
from src.data.DataIndexManager import DataIndexManager
from src.data.HolidayFetcher import HolidayFetcher

console = Console()


class DataManagementService:
    """
    Decouple data repair, download, and index logic from the main entry point.

    Design Pattern: Service - Encapsulates data management domain logic.

    Attributes:
        menu (Optional[Any]): Reference to MenuService for sub-navigation | None
        console (Console): Rich console instance for UI rendering | global console

    Public Methods:
        - data_health_dashboard(): Show data health dashboard.
        - repair_data(): Repair data issues.
        - download_historical_data(): Download historical data.
        - update_holidays(): Update holiday calendar.
        - view_data_index(): View and regenerate data index.

    Private Methods:
        - _reprocess_missing_results(): Internal helper for reprocessing logic.

    Usage Flow:
        1. Instantiate with optional menu service.
        2. Call public methods to handle specific CLI user requests.

    State Management:
        - Valid states: Initialized.
        - State transitions: N/A (Stateless service).

    Thread Safety: Partial - relies on underlying module concurrency safety.

    Dependencies:
        External: pandas, rich
        Internal: DataHealthCheck, DataIndexManager, HolidayFetcher, StockUniverseSelector
    """

    def __init__(self, menu_service: Any | None = None) -> None:
        """
        Initialize the service with UI dependencies.

        Logic:
            Step 1: Assign menu service reference.
            Step 2: Assign global console instance.

        Parameters:
            menu_service (Optional[Any]): Service for menu operations | None

        Returns:
            None: Constructor
        """
        self.menu = menu_service
        self.console = console

    def data_health_dashboard(self) -> None:
        """
        Show data health dashboard interactive report.

        Logic:
            Step 1: Print dashboard header.
            Step 2: Initialize DataHealthCheck and trigger report generation.
            Step 3: Wait for user input to confirm receipt.

        Parameters:
            None

        Returns:
            None: Side-effect (console output)

        Performance:
            Time Complexity: O(N) [where N is number of data files]
            Space Complexity: O(M) [where M is summary data size]
        """
        self.console.print("\n[bold cyan]📊 Data Health Dashboard[/bold cyan]")
        self.console.print("=" * 80)
        checker = DataHealthCheck()
        checker.generate_report()
        input("\nPress Enter to continue...")

    def repair_data(self, run_scan_callback: Callable) -> None:
        """
        Repair data issues including raw candles and screening results.

        Logic:
            Step 1: Present repair mode selection.
            Step 2: If mode 2, delegate to result reprocessing.
            Step 3: If mode 1, prompt for universe and execute raw data repair.

        Parameters:
            run_scan_callback (Callable): Callback for executing scanner [run_scan]

        Returns:
            None: Side-effect (CLI interaction and file mutation)

        Raises:
            Exception: Propagated from underlying repair modules.
        """
        self.console.print("\n[bold cyan]🔧 Repair Data[/bold cyan]")
        self.console.print("  1 > Repair Raw Data (Downloads missing candles)")
        self.console.print(
            "  2 > Reprocess Missing TA/ML Results (Runs scanner on missing stocks)"
        )

        mode = input("\nSelect mode (default: 1): ").strip() or "1"

        if mode == "2":
            self._reprocess_missing_results(run_scan_callback)
            return

        # Mode 1: Original Repair Data
        self.console.print("\nSelect stock universe:")
        self.console.print(
            "  1 > Nifty 50\n  2 > Nifty 100\n  3 > Nifty 200\n  4 > Nifty 500\n  5 > Custom Watchlist"
        )
        universe = input("\nSelect universe (default: 1): ").strip() or "1"
        dry_run = input("\nDry run mode? (y/n, default: n): ").strip().lower() == "y"

        import repair_data as rd

        rd.repair_data(
            universe=universe, timeframe="1d", dry_run=dry_run, interactive=True
        )
        input("\nPress Enter to continue...")

    def _reprocess_missing_results(self, run_scan_callback: Callable) -> None:
        """
        Internal helper for analyzing gaps in screening results and reprocessing.

        Logic:
            Step 1: Scan DATA_DIR for all parquet files.
            Step 2: Load results file and identify symbols with missing results.
            Step 3: Optionally filter by Nifty 50.
            Step 4: Execute callback on identified symbols.

        Parameters:
            run_scan_callback (Callable): Callback for executing scanner [run_scan]

        Returns:
            None: Side-effect (scanner execution)
        """
        checker = DataHealthCheck()
        self.console.print("\nChecking for missing screening results...")

        raw_files = list(checker.DATA_DIR.glob("*.parquet"))
        all_raw_stocks = [f.stem for f in raw_files]
        stocks_to_scan: list[str] = []

        if checker.RESULTS_FILE.exists():
            try:
                results_df = pd.read_parquet(checker.RESULTS_FILE)
                screened_stocks = (
                    set(results_df["Symbol"].unique())
                    if "Symbol" in results_df.columns
                    else set()
                )
                stocks_to_scan = [s for s in all_raw_stocks if s not in screened_stocks]
            except Exception:
                stocks_to_scan = all_raw_stocks
        else:
            stocks_to_scan = all_raw_stocks

        self.console.print(
            f"Found {len(stocks_to_scan)} stocks with raw data but missing/outdated results."
        )

        if not stocks_to_scan:
            self.console.print("✅ All stocks have results.")
            input("\nPress Enter to continue...")
            return

        self.console.print(
            "\nSelect universe filter for reprocessing:\n  1 > Process ALL missing stocks\n  2 > Process only Nifty 50 missing stocks"
        )
        if (input("\nSelect (default: 1): ").strip() or "1") == "2":
            from src.ui.StockUniverseSelector import StockUniverseSelector

            selector = StockUniverseSelector()
            nifty50 = set(selector.get_stocks("1"))
            stocks_to_scan = [s for s in stocks_to_scan if s in nifty50]
            self.console.print(f"Filtered to {len(stocks_to_scan)} Nifty 50 stocks.")

        if (
            input(f"\nStart processing {len(stocks_to_scan)} stocks? (y/n): ").lower()
            == "y"
        ):
            run_scan_callback(
                stocks_to_scan, min_score=-100, scan_name="Reprocess Missing Results"
            )

    def download_historical_data(self) -> None:
        """
        Download historical OHLCV data for selected universes.

        Logic:
            Step 1: Prompt for universe, period, and refresh flag.
            Step 2: Delegate to dhd.download_historical_data.

        Parameters:
            None

        Returns:
            None: Side-effect (file downloads)
        """
        self.console.print("\n[bold cyan]📥 Download Historical Data[/bold cyan]")

        self.console.print(
            "\nSelect stock universe:\n  1 > Nifty 50\n  2 > Nifty 100\n  3 > Nifty 200\n  4 > Nifty 500\n  5 > Custom Watchlist"
        )
        universe = input("\nSelect universe (default: 1): ").strip() or "1"

        self.console.print(
            "\nSelect period:\n  1 > 1 year\n  2 > 2 years\n  3 > 5 years\n  4 > Max"
        )
        period_map = {"1": "1y", "2": "2y", "3": "5y", "4": "max"}
        period = period_map.get(
            input("\nSelect period (default: 2): ").strip() or "2", "2y"
        )

        force = (
            input("\nForce refresh (re-download existing)? (y/n, default: n): ")
            .strip()
            .lower()
            == "y"
        )
        import download_historical_data as dhd

        dhd.download_historical_data(
            universe=universe, period=period, timeframes=["1d"], force=force
        )
        input("\nPress Enter to continue...")

    def update_holidays(self) -> None:
        """
        Synchronize trading holiday configuration from external sources.

        Logic:
            Step 1: Initialize HolidayFetcher and call update_config.

        Parameters:
            None

        Returns:
            None: Side-effect (config mutation)
        """
        self.console.print("\n[bold cyan]📅 Update Trading Holidays[/bold cyan]")
        self.console.print("Fetching latest holiday list from NSE...")
        HolidayFetcher().update_config()
        input("\nPress Enter to continue...")

    def view_data_index(self) -> None:
        """
        Render stock data index summary and record details.

        Logic:
            Step 1: Initialize index manager and trigger refresh.
            Step 2: Read index file and render summary statistics.
            Step 3: Render sample table of indexed stocks.

        Parameters:
            None

        Returns:
            None: Side-effect (console output)
        """
        self.console.print("\n[bold cyan]📑 Data Index[/bold cyan]")
        manager = DataIndexManager()
        manager.update_index()

        if manager.INDEX_FILE.exists():
            df = pd.read_csv(manager.INDEX_FILE)
            self.console.print(f"\nTotal Records: [bold]{len(df)}[/bold]")

            table = Table(box=box.SIMPLE)
            for col in df.columns:
                table.add_column(col)
            for _, row in df.head(10).iterrows():
                table.add_row(*[str(x) for x in row])
            self.console.print(table)

            self.console.print(
                f"\n[bold]Summary Status:[/bold]\n  Stocks with TA Results: [green]{len(df[df['TA Updated'] == 'Yes'])}[/green]\n  Stocks with ML Models: [green]{len(df[df['ML Ready'] == 'Yes'])}[/green]"
            )
        else:
            self.console.print("[red]❌ Index file could not be created.[/red]")
        input("\nPress Enter to continue...")
