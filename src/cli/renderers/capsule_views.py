"""
Capsule Academy & SMC specialized Rich table renderers.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from rich.console import Console
from rich.table import Table

from src.cli.visual import BoxStyles


def render_capsule_table(
    df: pd.DataFrame,
    title: str = "CAPSULE ACADEMY RESULTS",
    mode: str = "5star",
    max_rows: int = 50,
) -> None:
    """Render specialized Rich table for Capsule Academy setups with full domain metrics."""
    console = Console()
    if df is None or df.empty:
        console.print("[yellow]No stocks matched the criteria.[/yellow]")
        return

    table = Table(
        box=BoxStyles.TABLE,
        border_style="cyan",
        show_header=True,
        header_style="bold magenta",
        title=title,
        title_style="bold white",
    )
    table.add_column("#", justify="center", width=4)
    table.add_column("SYMBOL", style="bold white", width=12)
    table.add_column("CMP ₹", justify="right", width=10)

    if mode == "5star":
        table.add_column("STARS", justify="center", width=9)
        table.add_column("FARMS", justify="center", width=7)
        table.add_column("SUNFLWR", justify="center", width=8)
        table.add_column("SEEDS", justify="center", width=7)
        table.add_column("TURNOVR", justify="center", width=8)
        table.add_column("TRAIN 920", justify="center", width=11)
        table.add_column("RSI (D/W/M)", justify="center", width=14)
        table.add_column("ACTION", justify="center", width=13)
        table.add_column("STOP LOSS", justify="right", width=10)
        table.add_column("TARGET", justify="right", width=10)
    elif mode == "train":
        table.add_column("TF MODE", justify="center", width=13)
        table.add_column("TRAIN SIGNAL", justify="center", width=12)
        table.add_column("RSI (D/W/M)", justify="center", width=15)
        table.add_column("SMC OVERLAP", justify="center", width=24)
        table.add_column("ACTION", justify="center", width=13)
        table.add_column("STOP LOSS", justify="right", width=10)
        table.add_column("TARGET", justify="right", width=10)
    elif mode == "turnover":
        table.add_column("TF MODE", justify="center", width=13)
        table.add_column("STARS", justify="center", width=9)
        table.add_column("TURNOVER SURGE", justify="center", width=16)
        table.add_column("RSI (D)", justify="right", width=8)
        table.add_column("ACTION", justify="center", width=13)
        table.add_column("STOP LOSS", justify="right", width=10)
        table.add_column("TARGET", justify="right", width=10)
    elif mode == "smc":
        table.add_column("SMC OVERLAP", justify="center", width=25)
        table.add_column("SPRING", justify="center", width=8)
        table.add_column("IFC", justify="center", width=8)
        table.add_column("RSI (D/W)", justify="center", width=12)
        table.add_column("ACTION", justify="center", width=13)
        table.add_column("STOP LOSS", justify="right", width=10)
        table.add_column("TARGET", justify="right", width=10)

    for i, (_, row) in enumerate(df.head(max_rows).iterrows(), 1):
        rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else str(i)
        sym = str(row.get("Symbol") or row.get("SYMBOL", ""))
        cmp_val = row.get("Close") if pd.notna(row.get("Close")) else row.get("CMP", 0.0)
        cmp_str = f"₹{float(cmp_val):,.2f}" if cmp_val else "—"

        action = str(row.get("Action", "WATCH"))
        action_style = "bold green" if "BUY" in action else "yellow"
        sl = row.get("Stop_Loss", 0.0)
        sl_str = f"₹{float(sl):,.2f}" if sl else "—"
        tgt = row.get("Target", 0.0)
        tgt_str = f"₹{float(tgt):,.2f}" if tgt else "—"

        if mode == "5star":
            stars = str(row.get("Stars", "—"))
            farms = str(row.get("Monthly_Farms", "—"))
            sunflowers = str(row.get("Weekly_Sunflowers", "—"))
            seeds = str(row.get("Daily_Seeds", "—"))
            turnover = str(row.get("Turnover_Surge", "—"))
            train = str(row.get("Train_920130", "—"))
            rsi_d = row.get("RSI_D", "—")
            rsi_w = row.get("RSI_W", "—")
            rsi_m = row.get("RSI_M", "—")
            rsi_str = f"{rsi_d}/{rsi_w}/{rsi_m}"

            table.add_row(
                rank,
                sym,
                cmp_str,
                stars,
                f"[green]{farms}[/green]" if farms == "✔" else farms,
                f"[green]{sunflowers}[/green]" if sunflowers == "✔" else sunflowers,
                f"[green]{seeds}[/green]" if seeds == "✔" else seeds,
                f"[green]{turnover}[/green]" if turnover == "✔" else turnover,
                f"[bold yellow]{train}[/bold yellow]" if "BOARD" in train else train,
                rsi_str,
                f"[{action_style}]{action}[/{action_style}]",
                sl_str,
                tgt_str,
            )
        elif mode == "train":
            train = str(row.get("Train_920130", "—"))
            rsi_d = row.get("RSI_D", "—")
            rsi_w = row.get("RSI_W", "—")
            rsi_m = row.get("RSI_M", "—")
            rsi_str = f"{rsi_d}/{rsi_w}/{rsi_m}"
            smc_setup = str(row.get("SMC_Setup", "None"))
            tf_m = str(row.get("TF_Mode", "1D_FALLBACK"))
            tf_str = "[bold green]1H INTRADAY[/bold green]" if tf_m == "1H" else "[dim yellow]1D_FALLBACK[/dim yellow]"

            table.add_row(
                rank,
                sym,
                cmp_str,
                tf_str,
                f"[bold yellow]{train}[/bold yellow]" if "BOARD" in train else train,
                rsi_str,
                f"[cyan]{smc_setup}[/cyan]",
                f"[{action_style}]{action}[/{action_style}]",
                sl_str,
                tgt_str,
            )
        elif mode == "turnover":
            stars = str(row.get("Stars", "—"))
            turnover = str(row.get("Turnover_Surge", "—"))
            rsi_d = str(row.get("RSI_D", "—"))
            tf_m = str(row.get("TF_Mode", "1D_FALLBACK"))
            tf_str = "[bold green]1H INTRADAY[/bold green]" if tf_m == "1H" else "[dim yellow]1D_FALLBACK[/dim yellow]"

            table.add_row(
                rank,
                sym,
                cmp_str,
                tf_str,
                stars,
                f"[green]{turnover}[/green]" if turnover == "✔" else turnover,
                rsi_d,
                f"[{action_style}]{action}[/{action_style}]",
                sl_str,
                tgt_str,
            )
        elif mode == "smc":
            smc_setup = str(row.get("SMC_Setup", "None"))
            spring = str(row.get("Spring", "—"))
            ifc = str(row.get("IFC", "—"))
            rsi_d = row.get("RSI_D", "—")
            rsi_w = row.get("RSI_W", "—")
            rsi_str = f"{rsi_d}/{rsi_w}"
            table.add_row(
                rank,
                sym,
                cmp_str,
                f"[cyan]{smc_setup}[/cyan]",
                f"[green]{spring}[/green]" if spring == "✔" else spring,
                f"[green]{ifc}[/green]" if ifc == "✔" else ifc,
                rsi_str,
                f"[{action_style}]{action}[/{action_style}]",
                sl_str,
                tgt_str,
            )

    console.print(table)
    console.print(f"\n  [dim]{min(len(df), max_rows)} of {len(df)} records displayed[/dim]")


# Backward-compatible alias
_render_capsule_table = render_capsule_table
