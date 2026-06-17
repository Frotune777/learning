"""
File: src/cli/visual.py
Purpose: Centralized Rich-based UI rendering engine for the NSE pipeline CLI.
         Adapted from screeni-py's VisualUI, extended with learning-specific features:
         - Consensus callout column (⭐/⚠️ score-based)
         - 13-strategy color signals
         - RSI/MACD divergence badges
         - Strategy Inspector multi-panel view

Dependencies:
    External:
    - rich>=13.0.0: CLI formatting, panels, tables, progress bars
    - pandas>=2.2.3: Data handling for table rendering
    Internal: None

Key Components:
    Classes:
    - Colors: ANSI/Rich color constants (single source of truth)
    - BoxStyles: Box style constants
    - VisualUI: All 10 standardized CLI output formats

Last Modified: 2026-06-01
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Color & Style Constants
# ---------------------------------------------------------------------------


class Colors:
    """Single source of truth for Rich color styling."""

    CYAN = "cyan"
    GREEN = "green"
    RED = "red"
    YELLOW = "yellow"
    BLUE = "blue"
    MAGENTA = "magenta"
    WHITE = "white"
    DIM = "dim"

    SUCCESS = GREEN
    ERROR = RED
    WARNING = YELLOW
    INFO = CYAN
    HEADER = CYAN
    CATEGORY = "magenta"
    HIGHLIGHT = "bold white"
    MUTED = "dim"

    @staticmethod
    def success(t: str) -> str:
        return f"[green]{t}[/green]"

    @staticmethod
    def error(t: str) -> str:
        return f"[red]{t}[/red]"

    @staticmethod
    def warn(t: str) -> str:
        return f"[yellow]{t}[/yellow]"

    @staticmethod
    def info(t: str) -> str:
        return f"[cyan]{t}[/cyan]"

    @staticmethod
    def dim(t: str) -> str:
        return f"[dim]{t}[/dim]"

    @staticmethod
    def header(t: str) -> str:
        return f"[cyan]{t}[/cyan]"

    @staticmethod
    def category(t: str) -> str:
        return f"[magenta]{t}[/magenta]"

    @staticmethod
    def highlight(t: str) -> str:
        return f"[bold white]{t}[/bold white]"


class BoxStyles:
    """Centralized box style constants."""

    HEADER = box.DOUBLE
    MENU = box.SIMPLE
    TABLE = box.ROUNDED
    PANEL = box.SQUARE
    MINIMAL = box.MINIMAL


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

_BUY_SIGNALS = frozenset(
    {
        "Buy",
        "Breakout Buy",
        "Explosive Buy",
        "Level 1 Buy",
        "Level 2 Buy",
        "Level 3 Buy",
        "150 DMA Breakout | CMP > 200 DMA",
        "50 DMA Breakout | CMP > 200 DMA",
        "Super BO Buy",
        "Buy on Support / Demand Level",
        "Buy (55D Breakout)",
        "VCP Tightening",
        "Squeeze Active (Bullish)",
        "Long Entry",
        "Lorentzian Buy",
    }
)
_SELL_SIGNALS = frozenset({"Explosive Sell", "Lorentzian Sell"})


def _action_color(action: str) -> str:
    """Return Rich color tag based on action string."""
    if action in _BUY_SIGNALS:
        return "green"
    if action in _SELL_SIGNALS:
        return "red"
    return "dim"


# ---------------------------------------------------------------------------
# VisualUI
# ---------------------------------------------------------------------------


class VisualUI:
    """
    Standardized UI component library for the NSE pipeline screener.
    Follows screeni-py's VisualUI design, extended with new strategy columns.

    Public Methods:
        render_header(title, subtitle)   — double-border ╔═╗ header
        render_menu(title, sections)     — categorized ╭─╮ menu
        render_results_table(df)         — screener summary with color signals
        render_strategy_inspector(sym, row) — all 13 strategies in Rich table
        render_detailed_view(sym, data)  — multi-panel TA stock view
        render_progress(name, phases, pct) — spinner + phase tracking
        render_system_check(metrics)     — system health dashboard
        render_consensus_leaderboard(df) — top stocks by CONSENSUS_SCORE
        get_user_choice(prompt, valid)   — validated input
        live_scan_table()                — context manager for live-updating table
    """

    def __init__(self) -> None:
        self.console = Console()
        self.width = self.console.width
        self.colors = Colors()
        self.box_styles = BoxStyles()

    # =========================================================================
    # Format 1: Main Header (Double Border ╔═╗)
    # =========================================================================

    def render_header(self, title: str, subtitle: str = "") -> None:
        """Print a double-border centered header."""
        self.console.print()
        w = self.width
        self.console.print("╔" + "═" * (w - 2) + "╗", style="bold cyan")

        title_pad = (w - 2 - len(title)) // 2
        self.console.print(
            "║"
            + " " * title_pad
            + title
            + " " * (w - 2 - len(title) - title_pad)
            + "║",
            style="bold white",
        )

        if subtitle:
            sub_pad = (w - 2 - len(subtitle)) // 2
            self.console.print(
                "║"
                + " " * sub_pad
                + subtitle
                + " " * (w - 2 - len(subtitle) - sub_pad)
                + "║",
                style="dim",
            )

        self.console.print("╚" + "═" * (w - 2) + "╝", style="bold cyan")
        self.console.print()

    # =========================================================================
    # Format 2: Categorized Menu (╭─╮)
    # =========================================================================

    def render_menu(
        self, title: str, sections: dict[str, list[dict[str, Any]]]
    ) -> None:
        """Print a categorized menu with rounded box borders."""
        self.console.print()
        w = self.width

        self.console.print("╭" + "─" * (w - 2) + "╮", style="cyan")
        title_line = f"│   {title}" + " " * (w - len(title) - 7) + "│"
        self.console.print(title_line, style="bold white")

        for section_name, options in sections.items():
            self.console.print("├" + "─" * (w - 2) + "┤", style="cyan")
            self.console.print(
                f"│   [magenta]📋 {section_name}[/magenta]"
                + " " * (w - len(section_name) - 11)
                + "│"
            )

            for opt in options:
                num = opt.get("id", "")
                name = opt.get("name", "")
                emoji = opt.get("emoji", "")
                status = opt.get("status", "")
                details = opt.get("details", "")

                status_colored = (
                    f"[green]{status}[/green]"
                    if status == "Ready"
                    else f"[dim]{status}[/dim]"
                )
                line = f"│  [cyan]{num:>3}.[/cyan] {emoji} {name}  {status_colored}"

                details_text = f"[dim]{details}[/dim]"
                # Right-align details
                clean_len = len(f"│  {num:>3}. {emoji} {name}   {status}") + 2
                padding = max(1, w - clean_len - len(details) - 2)
                self.console.print(line + " " * padding + details_text + "│")

        self.console.print("╰" + "─" * (w - 2) + "╯", style="cyan")
        self.console.print()
        self.console.print("[cyan][?][/cyan] Enter your choice: ", end="")

    # =========================================================================
    # Format 3: Screener Summary Table
    # =========================================================================

    def render_results_table(
        self,
        df: pd.DataFrame,
        title: str = "SCREENER RESULTS",
        max_rows: int = 50,
    ) -> None:
        """
        Print color-coded screener results table.

        Columns shown:
            RANK · SYMBOL · CMP · TREND_STATUS · CAR_RATING · CONSENSUS_SCORE
            CONSENSUS_CALLOUT · TECH_SCORE · RSI_14 · DELIV_PCT
        """
        if df.empty:
            self.console.print("[yellow]No stocks matched the criteria.[/yellow]")
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
        table.add_column("CMP ₹", justify="right", width=9)
        table.add_column("TREND", width=14)
        table.add_column("CAR", width=14)
        table.add_column("CONSENSUS", justify="center", width=10)
        table.add_column("CALLOUT", width=38)
        table.add_column("TA ★", justify="center", width=8)
        table.add_column("RSI", justify="right", width=7)
        table.add_column("DELIV%", justify="right", width=7)

        for i, (_, row) in enumerate(df.head(max_rows).iterrows(), 1):
            rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else str(i)

            cmp_val = row.get("CMP", float("nan"))
            cmp_str = f"{cmp_val:,.2f}" if pd.notna(cmp_val) else "—"

            trend = str(row.get("TREND_STATUS", ""))
            trend_text = Text(trend)
            if "Bull" in trend:
                trend_text.stylize("green")
            elif "Bear" in trend:
                trend_text.stylize("red")
            else:
                trend_text.stylize("dim")

            car = str(row.get("CAR_RATING", ""))
            car_text = Text(car)
            car_text.stylize("green" if "Buy" in car else "dim")

            score = row.get("CONSENSUS_SCORE", 0)
            try:
                score_int = int(score)
            except (ValueError, TypeError):
                score_int = 0
            score_text = Text(str(score_int))
            score_text.stylize(
                "bold green" if score_int >= 4 else "yellow" if score_int > 0 else "dim"
            )

            callout = str(row.get("CONSENSUS_CALLOUT", ""))
            callout_text = Text(callout[:38])
            if "HIGH CONVICTION BUY" in callout:
                callout_text.stylize("bold green")
            elif "BUY" in callout:
                callout_text.stylize("green")
            elif "SELL" in callout:
                callout_text.stylize("red")
            else:
                callout_text.stylize("dim")

            tech_score = row.get("TECH_SCORE", float("nan"))
            stars = self._score_to_stars(tech_score, max_val=10.0)

            rsi = row.get("RSI_14", float("nan"))
            rsi_str = f"{rsi:.1f}" if pd.notna(rsi) else "—"
            rsi_text = Text(rsi_str)
            if pd.notna(rsi):
                rsi_text.stylize(
                    "red" if rsi >= 70 else "green" if rsi <= 35 else "white"
                )

            deliv = row.get("DELIV_PCT", float("nan"))
            deliv_str = f"{deliv:.1f}" if pd.notna(deliv) else "—"

            table.add_row(
                rank,
                str(row.get("SYMBOL", "")),
                cmp_str,
                trend_text,
                car_text,
                score_text,
                callout_text,
                stars,
                rsi_text,
                deliv_str,
            )

        self.console.print(table)
        self.console.print(
            f"\n  [dim]{min(len(df), max_rows)} of {len(df)} records shown[/dim]"
        )

    # =========================================================================
    # Format 4: Strategy Inspector (all 13 strategies for one stock)
    # =========================================================================

    def render_strategy_inspector(self, symbol: str, row: pd.Series | dict) -> None:
        """
        Print all 13 strategy signals for a single stock in a Rich table,
        plus divergence badges and consensus summary.
        """
        self.render_header(
            f"STRATEGY INSPECTOR — {symbol}",
            f"All 13 strategies · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        )

        strategy_map = {
            # Core strategies
            "Nifty Shop": ("STR_NIFTY_SHOP_ACTION", None),
            "Buy Low Sell High": ("STR_BUY_LOW_ACTION", None),
            "Turtle Trading": ("STR_TURTLE_ACTION", "STR_TURTLE_SL"),
            "RDX": ("STR_RDX_ACTION", "STR_RDX_TARGET"),
            "100 SMA Breakout": ("STR_100SMA_ACTION", "STR_100SMA_TARGET"),
            "ETF Shop": ("STR_ETF_SHOP_ACTION", "STR_ETF_SHOP_DIFF"),
            "Super BO": ("STR_SUPER_BO_ACTION", "STR_SUPER_BO_TARGET"),
            "DMA Reverse": ("STR_DMA_REV_ACTION", "STR_DMA_REV_TARGET"),
            "DMA (No SL)": ("STR_DMA_NOSL_ACTION", "STR_DMA_NOSL_TARGET"),
            # New strategies
            "VCP (Minervini)": ("STR_VCP_ACTION", None),
            "TTM Squeeze": ("STR_TTM_ACTION", None),
            "Dual Supertrend": ("STR_SUPERTREND_ACTION", None),
            "Lorentzian ML": ("STR_LORENTZIAN_ACTION", None),
        }

        strat_table = Table(
            box=BoxStyles.TABLE,
            border_style="cyan",
            header_style="bold magenta",
            title="Strategy Signals",
            title_style="bold white",
        )
        strat_table.add_column("Strategy", style="bold white", width=20)
        strat_table.add_column("Action", width=32)
        strat_table.add_column("Detail", width=24)
        strat_table.add_column("Signal", justify="center", width=10)

        for name, (action_col, detail_col) in strategy_map.items():
            action = str(row.get(action_col, "N/A"))
            detail = str(row.get(detail_col, "—")) if detail_col else "—"
            color = _action_color(action)

            action_text = Text(action)
            action_text.stylize(color)

            if action in _BUY_SIGNALS:
                signal_badge = Text("BUY  ▲", style="bold green")
            elif action in _SELL_SIGNALS:
                signal_badge = Text("SELL ▼", style="bold red")
            else:
                signal_badge = Text("HOLD ─", style="dim")

            strat_table.add_row(name, action_text, detail[:24], signal_badge)

        # Extra signals
        candle = str(row.get("STR_CANDLE_PATTERN", "None"))
        ttm_squeeze = row.get("STR_TTM_SQUEEZE", False)
        rsi_div = str(row.get("RSI_DIVERGENCE", "None"))
        macd_div = str(row.get("MACD_DIVERGENCE", "None"))

        self.console.print(Panel(strat_table, border_style="cyan"))

        # Info panels row
        candle_panel = Panel(
            f"[bold white]Pattern:[/bold white] {candle}\n"
            f"[bold white]TTM Active:[/bold white] {'[green]Yes ✓[/green]' if ttm_squeeze else '[dim]No[/dim]'}",
            title="🕯 Candlestick / TTM",
            border_style="yellow",
            box=BoxStyles.PANEL,
        )

        rsi_color = (
            "green"
            if "Bullish" in rsi_div
            else "red"
            if "Bearish" in rsi_div
            else "dim"
        )
        macd_color = (
            "green"
            if "Bullish" in macd_div
            else "red"
            if "Bearish" in macd_div
            else "dim"
        )
        div_panel = Panel(
            f"[bold white]RSI Divergence:[/bold white] [{rsi_color}]{rsi_div}[/{rsi_color}]\n"
            f"[bold white]MACD Divergence:[/bold white] [{macd_color}]{macd_div}[/{macd_color}]",
            title="📉 Divergences",
            border_style="blue",
            box=BoxStyles.PANEL,
        )

        score = row.get("CONSENSUS_SCORE", 0)
        callout = str(row.get("CONSENSUS_CALLOUT", "No consensus data"))
        score_color = (
            "bold green"
            if score >= 4
            else "yellow"
            if score > 0
            else "red"
            if score < 0
            else "dim"
        )
        consensus_panel = Panel(
            f"[bold white]Score:[/bold white] [{score_color}]{score}/13[/{score_color}]\n"
            f"[dim]{callout}[/dim]",
            title="⭐ Consensus",
            border_style="green",
            box=BoxStyles.PANEL,
        )

        self.console.print(Columns([candle_panel, div_panel, consensus_panel]))

    # =========================================================================
    # Format 5: Detailed TA Stock View (multi-panel)
    # =========================================================================

    def render_detailed_view(self, symbol: str, data: dict[str, Any]) -> None:
        """
        Multi-panel TA stock view:
          Row 1 — Price Info + Technical Score
          Row 2 — Technical Indicators table
          Row 3 — Strategy Signals + Divergences
          Row 4 — Consensus Summary
        """
        self.render_header(
            f"{symbol} — DETAILED ANALYSIS",
            f"Institutional Grade View · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        )

        price_data = data.get("price_info", {})
        price_text = Text()
        price_text.append("CMP:      ", style="dim")
        price_text.append(f"₹{price_data.get('current', 0):,.2f}\n", style="bold white")
        price_text.append("Change:   ", style="dim")
        change = price_data.get("change_pct", 0.0)
        price_text.append(
            f"{change:+.2f}%\n",
            style="green" if change >= 0 else "red",
        )
        price_text.append("Volume:   ", style="dim")
        price_text.append(f"{price_data.get('volume', 0):,.0f}\n", style="white")
        price_text.append("High/Low: ", style="dim")
        price_text.append(
            f"₹{price_data.get('high', 0):,.2f} / ₹{price_data.get('low', 0):,.2f}",
            style="dim",
        )

        price_panel = Panel(
            price_text, title="📈 PRICE", border_style="cyan", box=BoxStyles.PANEL
        )

        # Score panel
        score = data.get("tech_score", 0.0)
        score_pct = min(100, max(0, (score / 10.0) * 100))
        bar_filled = int(score_pct / 5)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        score_text = Text()
        score_text.append(f"Score:  {score:.1f} / 10\n", style="bold white")
        score_text.append(f"[{bar}] {score_pct:.0f}%\n", style="yellow")
        score_text.append("Rating: ", style="dim")
        rating = data.get("tech_rating", "NEUTRAL")
        r_color = (
            "green" if "BUY" in rating else "red" if "SELL" in rating else "yellow"
        )
        score_text.append(rating, style=f"bold {r_color}")

        score_panel = Panel(
            score_text,
            title="📊 TECH SCORE",
            border_style="magenta",
            box=BoxStyles.PANEL,
        )

        self.console.print(Columns([price_panel, score_panel]))
        self.console.print()

        # Indicators table
        ind_table = Table(
            box=BoxStyles.MENU,
            show_header=True,
            header_style="bold cyan",
            title="🔍 TECHNICAL INDICATORS",
            title_style="bold white",
        )
        ind_table.add_column("Indicator", style="white", width=18)
        ind_table.add_column("Value", justify="right", width=12)
        ind_table.add_column("Signal", width=22)

        for ind in data.get("indicators", []):
            sig = ind.get("signal", "")
            sig_color = (
                "green"
                if "Bull" in sig or "Buy" in sig
                else "red"
                if "Bear" in sig or "Sell" in sig
                else "yellow"
            )
            ind_table.add_row(
                ind.get("name", ""),
                str(ind.get("value", "—")),
                f"[{sig_color}]{sig}[/{sig_color}]",
            )

        self.console.print(Panel(ind_table, border_style="cyan"))
        self.console.print()

    # =========================================================================
    # Format 6: Consensus Leaderboard
    # =========================================================================

    def render_consensus_leaderboard(self, df: pd.DataFrame, top_n: int = 20) -> None:
        """Rank stocks by CONSENSUS_SCORE and display top N."""
        if df.empty or "CONSENSUS_SCORE" not in df.columns:
            self.console.print("[yellow]No consensus data available.[/yellow]")
            return

        ranked = (
            df[df["CONSENSUS_SCORE"] > 0]
            .sort_values("CONSENSUS_SCORE", ascending=False)
            .head(top_n)
        )

        if ranked.empty:
            self.console.print(
                "[yellow]No stocks with positive consensus score found.[/yellow]"
            )
            return

        table = Table(
            box=BoxStyles.TABLE,
            border_style="cyan",
            header_style="bold magenta",
            title=f"⭐ CONSENSUS LEADERBOARD — Top {len(ranked)}",
            title_style="bold white",
        )
        table.add_column("Rank", justify="center", width=6)
        table.add_column("Symbol", style="bold white", width=12)
        table.add_column("Score", justify="center", width=8)
        table.add_column("Stars", width=12)
        table.add_column("Callout", width=46)
        table.add_column("VCP", justify="center", width=6)
        table.add_column("TTM", justify="center", width=6)
        table.add_column("ST", justify="center", width=6)
        table.add_column("Lorenz", justify="center", width=8)

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}

        for i, (_, row) in enumerate(ranked.iterrows(), 1):
            rank_str = medals.get(i, str(i))
            score = int(row.get("CONSENSUS_SCORE", 0))
            stars = "⭐" * min(5, max(0, round(score / 2.6)))

            callout = str(row.get("CONSENSUS_CALLOUT", ""))[:46]
            callout_text = Text(callout)
            callout_text.stylize(
                "bold green"
                if "HIGH CONVICTION" in callout
                else "green"
                if "BUY" in callout
                else "dim"
            )

            def _badge(col: str, buy_val: str) -> Text:
                val = str(row.get(col, ""))
                if val == buy_val or val in _BUY_SIGNALS:
                    return Text("✓", style="green")
                return Text("—", style="dim")

            table.add_row(
                rank_str,
                str(row.get("SYMBOL", "")),
                f"[bold green]{score}[/bold green]",
                stars,
                callout_text,
                _badge("STR_VCP_ACTION", "VCP Tightening"),
                _badge("STR_TTM_ACTION", "Squeeze Active (Bullish)"),
                _badge("STR_SUPERTREND_ACTION", "Long Entry"),
                _badge("STR_LORENTZIAN_ACTION", "Lorentzian Buy"),
            )

        self.console.print(table)

    # =========================================================================
    # Format 7: Progress Display
    # =========================================================================

    def render_progress(
        self,
        task_name: str,
        phases: list[dict[str, Any]],
        total_progress: float,
    ) -> None:
        """Spinner + phase tracking progress display."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
        ) as progress:
            task = progress.add_task(f"📊 {task_name}", total=100)
            progress.update(task, completed=total_progress)

            self.console.print()
            for phase in phases:
                status = phase.get("status", "Pending")
                name = phase.get("name", "")
                t = phase.get("time", 0)
                if status == "Complete":
                    self.console.print(
                        f"   {name}: [green]✅ Complete[/green] [dim]({t}s)[/dim]"
                    )
                elif status == "In progress":
                    self.console.print(
                        f"   {name}: [yellow]🔄 In progress[/yellow] [dim]({t}s elapsed)[/dim]"
                    )
                else:
                    self.console.print(f"   {name}: [dim]⏳ Pending[/dim]")

    # =========================================================================
    # Format 8: System Health Check
    # =========================================================================

    def render_system_check(self, metrics: dict[str, Any]) -> None:
        """Render system health as a Rich panel grid."""
        self.render_header(
            "SYSTEM HEALTH CHECK", "DuckDB · Parquets · Ban List · Strategies"
        )

        table = Table(box=BoxStyles.MENU, show_header=False)
        table.add_column("Component", style="white", width=28)
        table.add_column("Status", width=20)
        table.add_column("Detail", style="dim", width=30)

        status_map = {
            True: "[green]✅ OK[/green]",
            False: "[red]❌ FAIL[/red]",
            None: "[yellow]⚠ UNKNOWN[/yellow]",
        }

        for component, (ok, detail) in metrics.items():
            table.add_row(component, status_map.get(ok, str(ok)), str(detail))

        self.console.print(Panel(table, title="Health Check", border_style="cyan"))

    # =========================================================================
    # Helpers
    # =========================================================================

    def _score_to_stars(
        self, score: float | None, max_val: float = 10.0, n: int = 5
    ) -> str:
        """Convert a numeric score to a star rating string."""
        if score is None or (isinstance(score, float) and pd.isna(score)):
            return "☆" * n
        filled = min(n, max(0, round((float(score) / max_val) * n)))
        return "★" * filled + "☆" * (n - filled)

    def _format_status(self, status: str) -> str:
        if status == "Ready":
            return "[green]Ready[/green]"
        if status == "Error":
            return "[red]Error[/red]"
        return f"[dim]{status}[/dim]"

    def get_user_choice(self, prompt: str = "", valid: set | None = None) -> str:
        """Validated user input with optional whitelist."""
        while True:
            raw = input(prompt).strip().upper()
            if valid is None or raw in valid:
                return raw
            self.console.print(f"[red]Invalid choice '{raw}'. Options: {valid}[/red]")

    def live_scan_table(self):
        """Return a Live context manager for real-time scan output."""
        table = Table(
            box=BoxStyles.TABLE,
            border_style="cyan",
            header_style="bold magenta",
            title="🔴 LIVE SCAN",
            title_style="bold white",
        )
        table.add_column("Symbol", style="bold white", width=12)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Action", width=32)
        table.add_column("Score", justify="right", width=8)
        return Live(table, refresh_per_second=4, console=self.console), table
