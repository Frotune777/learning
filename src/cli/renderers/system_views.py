"""
System health, Data Quality, and NSE live terminal views.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.formatters import bold, dim, green, red, yellow
from src.cli.visual import BoxStyles


def render_dq_audit_panel(
    total_symbols: int,
    healthy_count: int,
    low_coverage_count: int,
    stale_count: int,
    nan_indicators_count: int,
    missing_count: int,
    failed_blacklist_count: int,
) -> None:
    """Render the Data Quality System Audit panel in terminal."""
    console = Console()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row(dim("Total Equities in Master:"), bold(str(total_symbols)))
    table.add_row(green("Healthy Data (>=95% Coverage, Fresh, No NaNs):"), bold(str(healthy_count)))
    table.add_row(yellow("Low Coverage (<95% Coverage):"), bold(str(low_coverage_count)))
    table.add_row(yellow("Stale Data (>3 Days Out of Date):"), bold(str(stale_count)))
    table.add_row(yellow("Incomplete / NaN Technical Indicators:"), bold(str(nan_indicators_count)))
    table.add_row(red("Missing Parquet Cache:"), bold(str(missing_count)))
    table.add_row(
        dim("Failed Sync Blacklist (failed_symbols.csv):"),
        bold(str(failed_blacklist_count)),
    )

    panel = Panel(
        table,
        title="[bold cyan]DATA QUALITY SYSTEM AUDIT[/bold cyan]",
        border_style="cyan",
        expand=False,
    )
    console.print(panel)


def render_pre_flight_panel(status: dict[str, Any]) -> None:
    """Render pre-flight environment and connectivity panel."""
    console = Console()
    table = Table(box=BoxStyles.TABLE, border_style="cyan", title="PRE-FLIGHT DIAGNOSTICS", header_style="bold cyan")
    table.add_column("Diagnostic Check", style="bold white", width=28)
    table.add_column("Status", justify="center", width=14)
    table.add_column("Details", justify="left", width=36)

    for item, stat in status.items():
        ok_flag = stat.get("ok", False)
        st_str = "[bold green]PASS[/bold green]" if ok_flag else "[bold red]FAIL[/bold red]"
        table.add_row(item, st_str, str(stat.get("details", "")))

    console.print(table)


def render_nse_live_quote_table(quote: dict[str, Any]) -> None:
    """Render live stock quote table."""
    console = Console()
    table = Table(box=BoxStyles.TABLE, border_style="cyan", title=f"LIVE QUOTE: {quote.get('symbol', 'UNKNOWN')}")
    table.add_column("Metric", style="bold white", width=20)
    table.add_column("Value", justify="right", width=20)

    for k, v in quote.items():
        table.add_row(str(k), str(v))

    console.print(table)


def render_option_chain_table(df_chain: pd.DataFrame, max_rows: int = 20) -> None:
    """Render active option chain snapshot."""
    console = Console()
    if df_chain is None or df_chain.empty:
        console.print("[yellow]Option chain is empty or unavailable.[/yellow]")
        return

    table = Table(box=BoxStyles.TABLE, border_style="cyan", title="NSE DERIVATIVES OPTION CHAIN", header_style="bold magenta")
    for col in df_chain.columns:
        table.add_column(str(col), justify="right" if pd.api.types.is_numeric_dtype(df_chain[col]) else "left")

    for _, row in df_chain.head(max_rows).iterrows():
        row_vals = [f"{v:,.2f}" if isinstance(v, float) else str(v) for v in row]
        table.add_row(*row_vals)

    console.print(table)
