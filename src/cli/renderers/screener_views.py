"""
Screener, Consensus, and Strategy presentation renderers for Fortune ADSS CLI.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from rich.console import Console
from rich.table import Table

from src.cli.formatters import _subheader, bold, cyan, dim, green, red, warn, yellow
from src.cli.visual import BoxStyles


def render_strategy_inspector_card(
    symbol: str,
    row_or_df: pd.Series | dict[str, Any] | pd.DataFrame,
) -> None:
    """Render color-coded strategy inspector card for a stock with robust column guards."""
    console = Console()
    if isinstance(row_or_df, pd.DataFrame):
        match = row_or_df[row_or_df.get("SYMBOL", pd.Series()).astype(str).str.upper() == symbol.upper()]
        if match.empty:
            console.print(f"[yellow]No data found in current dataset for symbol {symbol}.[/yellow]")
            return
        row: dict[str, Any] = match.iloc[0].to_dict()
    elif isinstance(row_or_df, pd.Series):
        row = row_or_df.to_dict()
    else:
        row = row_or_df

    cmp_val = row.get("CMP") or row.get("Close") or 0.0
    tech_score = row.get("TECH_SCORE", "—")
    consensus = row.get("CONSENSUS_SCORE", row.get("SCORE", "—"))
    car = row.get("CAR_RATING", "—")

    table = Table(
        box=BoxStyles.TABLE,
        border_style="cyan",
        title=f"STRATEGY INSPECTOR: {symbol.upper()} (CMP: ₹{float(cmp_val):,.2f})",
        header_style="bold magenta",
    )
    table.add_column("Strategy Indicator", style="bold white", width=32)
    table.add_column("Signal / State", justify="center", width=18)
    table.add_column("Details", justify="left", width=30)

    strategies = [
        ("Bull Run Setup", row.get("STRATEGY_BULL_RUN", row.get("BULL_RUN", "—"))),
        ("CAR Rating Breakout", car),
        ("GTT Swing Bounce", row.get("STRATEGY_SWING", row.get("SWING_SIGNAL", "—"))),
        ("Super Setup (Confluence)", row.get("STRATEGY_SUPER", row.get("SUPER_SETUP", "—"))),
        ("Minervini VCP", row.get("VCP_SETUP", row.get("MINERVINI_VCP", "—"))),
        ("Momentum Squeeze", row.get("SQUEEZE_STATE", row.get("MOMENTUM_SQUEEZE", "—"))),
        ("Turtle Breakout (20D)", row.get("TURTLE_BREAKOUT", "—")),
        ("Dual SuperTrend", row.get("SUPERTREND_SIGNAL", "—")),
        ("Volume Profile / VSA", row.get("VSA_SIGNAL", "—")),
        ("Darvas Box", row.get("DARVAS_BOX", "—")),
        ("Technical Composite Score", str(tech_score)),
        ("Consensus Agreement", f"{consensus}/13 Strategies" if str(consensus).isdigit() else str(consensus)),
    ]

    for name, val in strategies:
        s_val = str(val) if val is not None else "—"
        if any(w in s_val.upper() for w in ("BUY", "TRUE", "PASS", "BREAKOUT", "FIRED", "1")):
            state = f"[bold green]{s_val}[/bold green]"
        elif any(w in s_val.upper() for w in ("SELL", "BREAKDOWN", "FALSE", "FAIL", "0")):
            state = f"[bold red]{s_val}[/bold red]"
        elif s_val == "—":
            state = "[dim]—[/dim]"
        else:
            state = f"[yellow]{s_val}[/yellow]"
        table.add_row(name, state, "")

    console.print(table)


def render_consensus_leaderboard(
    df: pd.DataFrame,
    title: str = "CONSENSUS STRATEGY LEADERBOARD",
    top_n: int = 20,
) -> None:
    """Render top stocks ranked by consensus agreement with safe column guards."""
    console = Console()
    if df is None or df.empty:
        console.print("[yellow]No consensus data available to display.[/yellow]")
        return

    table = Table(
        box=BoxStyles.TABLE,
        border_style="cyan",
        title=f"{title} (Top {min(len(df), top_n)})",
        header_style="bold magenta",
    )
    table.add_column("#", justify="center", width=4)
    table.add_column("SYMBOL", style="bold white", width=12)
    table.add_column("CMP ₹", justify="right", width=10)
    table.add_column("CONSENSUS", justify="center", width=11)
    table.add_column("CAR", justify="center", width=8)
    table.add_column("TECH SCORE", justify="right", width=11)
    table.add_column("PRIMARY CONVERGENCE", justify="left", width=34)

    # Sort if consensus column present
    sort_col = "CONSENSUS_SCORE" if "CONSENSUS_SCORE" in df.columns else ("SCORE" if "SCORE" in df.columns else None)
    sorted_df = df.sort_values(sort_col, ascending=False) if sort_col else df

    for i, (_, row) in enumerate(sorted_df.head(top_n).iterrows(), 1):
        rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else str(i)
        sym = str(row.get("SYMBOL") or row.get("Symbol") or "—")
        cmp_val = row.get("CMP") or row.get("Close")
        cmp_str = f"₹{float(cmp_val):,.2f}" if cmp_val and pd.notna(cmp_val) else "—"

        score = row.get("CONSENSUS_SCORE") or row.get("SCORE") or "—"
        score_str = f"[bold green]{score}[/bold green]" if str(score).isdigit() and int(score) >= 5 else str(score)

        car = str(row.get("CAR_RATING") or row.get("CAR") or "—")
        tech = row.get("TECH_SCORE")
        tech_str = f"{float(tech):.1f}" if tech is not None and pd.notna(tech) else "—"

        strategies = []
        for c in ["BULL_RUN", "SWING_SIGNAL", "SUPER_SETUP", "MINERVINI_VCP", "TURTLE_BREAKOUT"]:
            if str(row.get(c, "")).upper() in ("TRUE", "BUY", "1"):
                strategies.append(c.replace("STRATEGY_", "").replace("_SIGNAL", ""))
        details = ", ".join(strategies[:3]) if strategies else "Multi-Factor Technical Setup"

        table.add_row(rank, sym, cmp_str, score_str, car, tech_str, details)

    console.print(table)


def render_strategy_results_table(
    df: pd.DataFrame,
    title: str,
    description: str | None = None,
    max_rows: int = 50,
) -> None:
    """Render a generic strategy result table with column guards."""
    console = Console()
    if df is None or df.empty:
        console.print(f"[yellow]No records found for {title}.[/yellow]")
        return

    _subheader(title)
    if description:
        console.print(f"  [dim]{description}[/dim]\n")

    table = Table(box=BoxStyles.TABLE, border_style="cyan", header_style="bold cyan")
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            table.add_column(str(col), justify="right")
        else:
            table.add_column(str(col), justify="left")

    for _, row in df.head(max_rows).iterrows():
        row_vals = []
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                row_vals.append("—")
            elif pd.api.types.is_numeric_dtype(df[col]):
                if any(x in str(col) for x in ["Volume", "Qty", "Score", "Count", "Rows"]):
                    row_vals.append(f"{val:,.0f}")
                else:
                    row_vals.append(f"{val:,.2f}")
            else:
                row_vals.append(str(val))
        table.add_row(*row_vals)

    console.print(table)
    console.print(f"\n  [dim]{min(len(df), max_rows)} of {len(df)} row(s) displayed[/dim]")


def render_unified_signals_table(df: pd.DataFrame, max_rows: int = 50) -> None:
    """Render unified multi-scanner breakout results."""
    render_strategy_results_table(
        df,
        title="UNIFIED MULTI-STRATEGY SIGNALS",
        description="Comprehensive signals aggregated across all active strategy engines.",
        max_rows=max_rows,
    )


def render_lux_regimes_table(records: list[dict[str, Any]] | pd.DataFrame) -> None:
    """Render Stan Weinstein 4-Stage Macro Cycles table."""
    console = Console()
    table = Table(
        box=BoxStyles.TABLE,
        border_style="cyan",
        title="Stan Weinstein 4-Stage Macro Cycles",
        header_style="bold cyan",
    )
    table.add_column("Symbol", style="bold white", width=12)
    table.add_column("Current Stage", justify="left", width=22)
    table.add_column("30-W MA", justify="right", width=12)
    table.add_column("Slope %", justify="right", width=10)
    table.add_column("Vol Ratio", justify="right", width=10)
    table.add_column("Action Signal", justify="center", width=22)

    rows = records if isinstance(records, list) else records.to_dict(orient="records")
    for r in rows:
        sym = str(r.get("symbol") or r.get("SYMBOL") or "—")
        stage_name = str(r.get("stage_name") or r.get("Current Stage") or "—")
        ma_val = r.get("ma_value") or r.get("30-W MA")
        ma_str = f"₹{float(ma_val):,.2f}" if ma_val is not None and pd.notna(ma_val) else "—"
        slope = r.get("ma_slope_pct") or r.get("Slope %")
        slope_str = f"{float(slope):+.2f}%" if slope is not None and pd.notna(slope) else "—"
        vol = r.get("volume_ratio") or r.get("Vol Ratio")
        vol_str = f"{float(vol):.2f}x" if vol is not None and pd.notna(vol) else "—"
        action = str(r.get("action") or r.get("Action Signal") or "—")

        stage_color = "magenta" if "1" in stage_name else "green" if "2" in stage_name else "yellow" if "3" in stage_name else "red"
        table.add_row(
            sym,
            f"[{stage_color}]{stage_name}[/{stage_color}]",
            ma_str,
            slope_str,
            vol_str,
            action,
        )
    console.print(table)


def render_backtest_table(metrics: dict[str, Any], title: str = "Backtest Performance Metrics") -> None:
    """Render performance metrics table for ML classifier and event backtests."""
    console = Console()
    table = Table(box=BoxStyles.TABLE, border_style="cyan", title=title, header_style="bold magenta")
    table.add_column("Performance Metric", style="bold white", width=30)
    table.add_column("Value", justify="right", width=18)

    for k, v in metrics.items():
        if isinstance(v, float):
            val_str = f"{v:.2%}" if "pct" in k.lower() or "rate" in k.lower() or "return" in k.lower() else f"{v:.4f}"
        else:
            val_str = str(v)
        table.add_row(k.replace("_", " ").title(), val_str)

    console.print(table)
