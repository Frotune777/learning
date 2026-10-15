"""
File: src/classes/VisualUI.py
Purpose: Centralized UI rendering engine using the Rich library with strict RULE #022 compliance

Dependencies:
External:
- rich>=13.0.0: [CLI formatting and rendering with box drawings, colors, and emojis]
- pandas>=2.0.0: [data processing for export previews and table formatting]
Internal:
- None

Key Components:
Classes:
- VisualUI: Implements all 10 standardized CLI output formats with exact border/color/emoji specs
- Colors: Centralized color constants for consistent styling across all UI components
- BoxStyles: Centralized box style constants for consistent border types

Last Modified: 2026-02-19
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Add support for custom color themes via config
- [ ] [MEDIUM] Implement screen resize handling for dynamic width adjustment
- [ ] [LOW] Add unit tests for each render method

Related Files:
- src/cli/menu.py: Uses VisualUI for all menu rendering
- src/classes/UltraOptimizedScanner.py: Uses progress displays for scanning
- src/classes/DataHealthMonitor.py: Uses health dashboard formatting
- src/classes/EnhancedBacktestValidator.py: Uses results tables
"""

from collections.abc import Generator
from datetime import datetime
from typing import Any

import pandas as pd
from rich import box
from rich.columns import Columns

# Rich imports for all CLI formatting
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
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# Note: Traceback installation removed for production graceful exit.
# To enable debugging: from rich.traceback import install; install(show_locals=True)


class Colors:
    """
    Centralized color constants for consistent styling across all UI components.

    Design Pattern: Constants Container - provides single source of truth for colors

    Usage:
        >>> console.print("Success!", style=Colors.SUCCESS)
        >>> text = Colors.warn("This is a warning")
    """

    # Base colors
    CYAN = "cyan"
    GREEN = "green"
    RED = "red"
    YELLOW = "yellow"
    BLUE = "blue"
    MAGENTA = "magenta"
    WHITE = "white"
    DIM = "dim"

    # Semantic colors (for consistent meaning)
    SUCCESS = GREEN
    ERROR = RED
    WARNING = YELLOW
    INFO = CYAN
    HEADER = CYAN
    CATEGORY = MAGENTA
    HIGHLIGHT = WHITE
    MUTED = DIM

    @staticmethod
    def success(text: str) -> str:
        """Format text as success message (green)"""
        return f"[{Colors.SUCCESS}]{text}[/{Colors.SUCCESS}]"

    @staticmethod
    def error(text: str) -> str:
        """Format text as error message (red)"""
        return f"[{Colors.ERROR}]{text}[/{Colors.ERROR}]"

    @staticmethod
    def warn(text: str) -> str:
        """Format text as warning message (yellow)"""
        return f"[{Colors.WARNING}]{text}[/{Colors.WARNING}]"

    @staticmethod
    def info(text: str) -> str:
        """Format text as info message (cyan)"""
        return f"[{Colors.INFO}]{text}[/{Colors.INFO}]"

    @staticmethod
    def dim(text: str) -> str:
        """Format text as dim/secondary (gray)"""
        return f"[{Colors.MUTED}]{text}[/{Colors.MUTED}]"

    @staticmethod
    def header(text: str) -> str:
        """Format text as header (cyan)"""
        return f"[{Colors.HEADER}]{text}[/{Colors.HEADER}]"

    @staticmethod
    def category(text: str) -> str:
        """Format text as category (magenta)"""
        return f"[{Colors.CATEGORY}]{text}[/{Colors.CATEGORY}]"

    @staticmethod
    def highlight(text: str) -> str:
        """Format text as highlight (white)"""
        return f"[{Colors.HIGHLIGHT}]{text}[/{Colors.HIGHLIGHT}]"


class BoxStyles:
    """
    Centralized box style constants for consistent border types.

    Design Pattern: Constants Container - ensures all UI components use same border styles

    Usage:
        >>> panel = Panel(content, box=BoxStyles.HEADER)
        >>> table = Table(box=BoxStyles.TABLE)
    """

    HEADER = box.DOUBLE  # ╔══╗ for main headers
    MENU = box.SIMPLE  # ├──┤ for menu sections
    TABLE = box.ROUNDED  # ╭──╮ for data tables
    PANEL = box.SQUARE  # ┌──┐ for panels
    MINIMAL = box.MINIMAL  # ─ ─ for minimal separation
    RULE = box.HEAVY  # ━━ for rule lines


class VisualUI:
    """
    Standardized UI component library for the Stock Screener.
    Follows strict formatting rules for borders, colors, and emojis as per RULE #022.

    Design Pattern: Facade - provides simplified interface to Rich library with consistent styling

    Attributes:
        console (Console): Rich console instance for output
        width (int): Current console width for dynamic formatting

    Public Methods:
        render_header(): Format 1 - Main header with double border
        render_menu(): Format 2 - Categorized menu with simple borders
        render_progress(): Format 3 - Progress display with phases
        render_results_table(): Format 4 - Results table with rounded borders
        render_detailed_view(): Format 5 - Multi-panel detailed stock view
        render_data_health(): Format 6 - Data health dashboard
        render_error(): Format 7 - Error/warning messages
        render_system_check(): Format 8 - System health check
        render_help(): Format 9 - Help/information panel
        render_export_preview(): Format 10 - Export preview
        render_config_wizard(): Configuration wizard helper
        get_user_choice(): Validated user input
        live_table(): Live-updating table for real-time data

    Private Methods:
        _create_results_table(): Create but don't print table
        _format_status(): Format status with proper color
        _calculate_stars(): Convert score to star rating
    """

    def __init__(self):
        """Initialize VisualUI with console and color constants"""
        self.console = Console()
        self.width = self.console.width
        self.colors = Colors()
        self.box_styles = BoxStyles()

    # =========================================================================
    # Format 1: Main Header (Double Border)
    # =========================================================================

    def render_header(self, title: str, subtitle: str = "") -> None:
        """
        Format 1: Main Header with Double Border (╔═╗)

        Logic:
            1. Get current console width for dynamic sizing
            2. Print top border with ╔ and ═ and ╗
            3. Center title in bold white
            4. Add subtitle in dim if provided
            5. Print bottom border with ╚ and ═ and ╝

        Parameters:
            title (str): Main header text (will be bold white)
            subtitle (str): Optional subtitle (will be dim)

        Example:
            >>> ui.render_header("QUICK SCAN RESULTS", "Nifty 50 - 2026-02-19")
            ╔══════════════════════════════════════════════════════════════════╗
            ║                     QUICK SCAN RESULTS                          ║
            ║                  Nifty 50 - 2026-02-19                          ║
            ╚══════════════════════════════════════════════════════════════════╝
        """
        self.console.print()

        # Top border
        self.console.print(
            "╔" + "═" * (self.width - 2) + "╗", style=f"bold {self.colors.HEADER}"
        )

        # Title - centered
        title_padding = (self.width - 2 - len(title)) // 2
        title_line = (
            "║"
            + " " * title_padding
            + title
            + " " * (self.width - 2 - len(title) - title_padding)
            + "║"
        )
        self.console.print(title_line, style=f"bold {self.colors.HIGHLIGHT}")

        # Subtitle if provided
        if subtitle:
            subtitle_padding = (self.width - 2 - len(subtitle)) // 2
            subtitle_line = (
                "║"
                + " " * subtitle_padding
                + subtitle
                + " " * (self.width - 2 - len(subtitle) - subtitle_padding)
                + "║"
            )
            self.console.print(subtitle_line, style=self.colors.MUTED)

        # Bottom border
        self.console.print(
            "╚" + "═" * (self.width - 2) + "╝", style=f"bold {self.colors.HEADER}"
        )
        self.console.print()

    # =========================================================================
    # Format 2: Categorized Menu (Simple Border)
    # =========================================================================

    def render_menu(
        self, title: str, sections: dict[str, list[dict[str, Any]]]
    ) -> None:
        """
        Format 2: Categorized Menu with Simple Borders (├──┤)

        Logic:
            1. Print main container top border (╭──╮)
            2. For each section:
                - Print section header with emoji
                - Print section separator (├──┤)
                - Print each option with number, name, emoji, status, details
                - Format status with appropriate color
            3. Print main container bottom border (╰──╯)
            4. Print footer with available commands

        Parameters:
            title (str): Menu title (displayed at top)
            sections (Dict): {
                "Section Name": [
                    {
                        "id": "1",
                        "name": "Option name",
                        "emoji": "🚀",
                        "status": "Ready",
                        "details": "Additional info"
                    }
                ]
            }

        Example:
            >>> sections = {
            ...     "SCANNING": [
            ...         {"id": "1", "name": "Quick Scan", "emoji": "🚀",
            ...          "status": "Ready", "details": "30 secs"}
            ...     ]
            ... }
            >>> ui.render_menu("MAIN MENU", sections)
        """
        self.console.print()

        # Main container top border
        self.console.print("╭" + "─" * (self.width - 2) + "╮", style=self.colors.HEADER)

        # Title
        title_line = f"│   {title}" + " " * (self.width - len(title) - 7) + "│"
        self.console.print(title_line, style=f"bold {self.colors.HIGHLIGHT}")

        for section_name, options in sections.items():
            # Section separator
            self.console.print(
                "├" + "─" * (self.width - 2) + "┤", style=self.colors.HEADER
            )

            # Section header with emoji
            section_header = f"│   📋 {self.colors.category(section_name)}"
            padding = self.width - len(section_header) - 4  # Adjust for rich tags
            self.console.print(section_header + " " * padding + "│")

            # Options
            for opt in options:
                # Format status with color
                status = opt.get("status", "")
                status_formatted = self._format_status(status)

                # Build option line
                num = opt.get("id", "")
                name = opt.get("name", "")
                emoji = opt.get("emoji", "")
                details = opt.get("details", "")

                left_part = f"│   {self.colors.info(f'{num:>2}.')} {name} {emoji} {status_formatted}"

                # Calculate padding for right-aligned details
                # Remove rich tags for length calculation
                # Use Text.from_markup to get accurate length of rich text
                clean_left_len = len(Text.from_markup(left_part))

                # Total available width for content between pipes is self.width - 2
                # We need to account for the left pipe and 3 spaces: "│   "
                # And the right pipe and 1 space: " │"
                # So, effective content width is self.width - 2 - 3 - 1 = self.width - 6

                # Calculate remaining space for details and padding
                remaining_width = (
                    self.width - clean_left_len - 2
                )  # -2 for the right pipe and its space

                if remaining_width > len(details) + 2:  # +2 for " │"
                    # Put details on same line, right-aligned
                    details_text = f" {self.colors.dim(details)}"
                    padding_needed = remaining_width - len(
                        Text.from_markup(details_text)
                    )

                    self.console.print(
                        left_part + " " * padding_needed + details_text + "│"
                    )
                else:
                    # Details on new line or if they don't fit on the same line
                    self.console.print(
                        left_part + " " * (self.width - clean_left_len - 2) + "│"
                    )

                    # Indent details on a new line
                    details_line_prefix = f"│   {' ' * (len(num) + 2)}   "  # "│   " + spaces for num + ". " + "   "
                    details_content = self.colors.dim(details)

                    # Use Columns to handle overflow for the details line
                    details_panel = Panel(
                        details_content,
                        width=self.width
                        - len(details_line_prefix)
                        - 1,  # -1 for the right pipe
                        box=box.SIMPLE_HEAD,  # No box, just for width/overflow
                        style="none",
                        padding=(0, 0, 0, 0),
                    )
                    self.console.print(details_line_prefix, details_panel, "│", sep="")

        # Main container bottom border
        self.console.print("╰" + "─" * (self.width - 2) + "╯", style=self.colors.HEADER)

        # Footer with commands
        self.console.print()
        self.console.print(
            f"{self.colors.info('[?]')} Options: {self.colors.highlight('[V]')}iew | {self.colors.highlight('[E]')}xport | {self.colors.highlight('[B]')}ack"
        )
        self.console.print(f"{self.colors.info('[+]')} Enter your choice: ", end="")

    # =========================================================================
    # Format 3: Progress Display
    # =========================================================================

    def render_progress(
        self,
        task_name: str,
        phases: list[dict[str, Any]],
        total_progress: float,
        eta_seconds: int = 150,
    ) -> None:
        """
        Format 3: Progress Display with dynamic ETA

        Logic:
            1. Create Rich Progress bar with spinner and time remaining
            2. Add main task with percentage
            3. For each phase, display status with appropriate emoji
            4. Update progress in real-time if used with Live

        Parameters:
            task_name (str): Name of the overall task
            phases (List[Dict]): [
                {
                    "name": "Phase 1",
                    "status": "Complete|In progress|Pending",
                    "time": 12 (seconds elapsed)
                }
            ]
            total_progress (float): Overall progress percentage (0-100)
            eta_seconds (int): Estimated seconds remaining
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
        ) as progress:
            # Main task
            task = progress.add_task(f"📊 {task_name}", total=100)
            progress.update(task, completed=total_progress)

            # Phase status (outside progress bar)
            self.console.print()
            for phase in phases:
                status = phase.get("status", "Pending")
                name = phase.get("name", "")
                time = phase.get("time", 0)

                if status == "Complete":
                    self.console.print(
                        f"   {name}: {self.colors.success('✅ Complete')} ({self.colors.dim(f'{time}s')})"
                    )
                elif status == "In progress":
                    self.console.print(
                        f"   {name}: {self.colors.warn('🔄 In progress')} ({self.colors.dim(f'{time}s elapsed')})"
                    )
                else:
                    self.console.print(f"   {name}: {self.colors.dim('⏳ Pending')}")

            self.console.print()

    # =========================================================================
    # Format 4: Results Table
    # =========================================================================

    def render_results_table(self, results: list[dict[str, Any]]) -> None:
        """
        Format 4: Results Table with Rounded Borders (╭──╮)

        Parameters:
            results (List[Dict]): List of result dictionaries with keys:
                - symbol: Stock symbol
                - signal: BUY/SELL/NEUTRAL
                - score: Numeric score (0-12)
                - confidence: Percentage (0-100)
                - return: 1Y return percentage
                - rr: Risk:Reward ratio
                - ml_dir: UP/DOWN/NEUTRAL
                - ml_conf: ML confidence percentage
        """
        table = self._create_results_table(results)
        self.console.print(table)

    def _create_results_table(self, results: list[dict[str, Any]]) -> Table:
        """
        Create results table without printing (for Live updates)

        Returns:
            Table: Rich Table object ready for display
        """
        table = Table(
            box=self.box_styles.TABLE,
            border_style=self.colors.HEADER,
            show_header=True,
            header_style=f"bold {self.colors.CATEGORY}",
            title="SCAN RESULTS",
            title_style=f"bold {self.colors.HIGHLIGHT}",
        )

        # Define columns
        table.add_column("RANK", justify="center", width=6)
        table.add_column("SYMBOL", style=f"bold {self.colors.HIGHLIGHT}", width=10)
        table.add_column("SIGNAL", justify="left", width=10)
        table.add_column("SCORE", justify="center", width=12)
        table.add_column("CONF", justify="right", width=6)
        table.add_column("1Y RET", justify="right", width=8)
        table.add_column("R:R", justify="right", width=6)
        table.add_column("ML", justify="center", width=8)

        for i, res in enumerate(results, 1):
            # Rank with emoji for top 3
            if i == 1:
                rank = "🥇"
            elif i == 2:
                rank = "🥈"
            elif i == 3:
                rank = "🥉"
            else:
                rank = str(i)

            # Signal with color
            signal = res.get("signal", "NEUTRAL")
            if "BUY" in signal:
                signal_text = Text(signal, style=self.colors.SUCCESS)
            elif "SELL" in signal:
                signal_text = Text(signal, style=self.colors.ERROR)
            else:
                signal_text = Text(signal, style=self.colors.WARNING)

            # Score with stars
            score = res.get("score", 0)
            stars = self._calculate_stars(score)
            score_text = Text()
            score_text.append(f"{score:.1f}/12\n", style=self.colors.HIGHLIGHT)
            score_text.append(stars, style=self.colors.WARNING)

            # Return with color
            ret = res.get("return", 0)
            ret_text = Text(
                f"{'+' if ret > 0 else ''}{ret:.1f}%",
                style=self.colors.SUCCESS if ret > 0 else self.colors.ERROR,
            )

            # ML with icon
            ml_dir = res.get("ml_dir", "NEUTRAL")
            ml_conf = res.get("ml_conf", 0)

            if ml_dir == "UP":
                ml_icon = "🟢UP"
            elif ml_dir == "DOWN":
                ml_icon = "🔴DOWN"
            else:
                ml_icon = "🟡?"

            ml_text = Text()
            ml_text.append(f"{ml_icon}\n", style=self.colors.HIGHLIGHT)
            ml_text.append(f"{ml_conf}%", style=self.colors.MUTED)

            # Add row
            table.add_row(
                rank,
                res.get("symbol", ""),
                signal_text,
                score_text,
                f"{res.get('confidence', 0)}%",
                ret_text,
                f"1:{res.get('rr', 0):.1f}",
                ml_text,
            )

        return table

    def _calculate_stars(self, score: float) -> str:
        """
        Convert score (0-12) to star rating (0-5 stars)

        Logic:
            1. Scale 0-12 to 0-5 (divide by 2.4)
            2. Round to nearest integer
            3. Generate filled stars (⭐) and empty stars (☆)

        Parameters:
            score (float): Score from 0-12

        Returns:
            str: Star rating string (e.g., "⭐⭐⭐☆☆" for 3/5 stars)
        """
        star_count = min(5, max(0, round(score / 2.4)))
        return "⭐" * star_count + "☆" * (5 - star_count)

    # =========================================================================
    # Format 5: Detailed Stock View
    # =========================================================================

    def render_detailed_view(self, symbol: str, data: dict[str, Any]) -> None:
        """
        Format 5: Detailed Stock View with Multiple Panels

        Panels:
            1. Price Information (blue border)
            2. Technical Score (magenta border)
            3. Technical Indicators table
            4. SMC Patterns table
            5. Divergence Detection table
            6. Backtest Results table
            7. Risk Management panel
            8. Strategy Reasoning panel

        Parameters:
            symbol (str): Stock symbol
            data (Dict): Complete stock data with all analysis results
        """
        signal = data.get("signal", "NEUTRAL")
        signal_color = self.colors.SUCCESS if "BUY" in signal else self.colors.ERROR

        # Header
        self.render_header(
            f"{symbol} - {signal}",
            f"Institutional Grade Analysis | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        )

        # ===== Row 1: Price + Technical Score =====
        # Price panel
        price_data = data.get("price_info", {})
        price_text = Text()
        price_text.append("LTP: ", style=self.colors.HIGHLIGHT)
        price_text.append(
            f"₹{price_data.get('current', 0):,.2f}\n",
            style=f"bold {self.colors.HIGHLIGHT}",
        )
        price_text.append("Change: ", style=self.colors.HIGHLIGHT)
        change = price_data.get("change", 0)
        price_text.append(
            f"{change:+.2f}%\n",
            style=self.colors.SUCCESS if change > 0 else self.colors.ERROR,
        )
        price_text.append("Volume: ", style=self.colors.HIGHLIGHT)
        price_text.append(
            f"{price_data.get('volume', 0):,}\n", style=self.colors.HIGHLIGHT
        )
        price_text.append("Avg Vol: ", style=self.colors.HIGHLIGHT)
        price_text.append(
            f"{price_data.get('avg_volume', 0):,}", style=self.colors.MUTED
        )

        price_panel = Panel(
            price_text,
            title="📈 PRICE INFORMATION",
            border_style=self.colors.INFO,
            box=self.box_styles.PANEL,
        )

        # Technical Score panel
        score = data.get("score", 0)
        score_text = Text()
        score_text.append("Total Score: ", style=self.colors.HIGHLIGHT)
        score_text.append(f"{score:.1f}/12\n", style=f"bold {self.colors.HIGHLIGHT}")

        # Progress bar for score percentage
        score_pct = (score / 12) * 100
        bar_length = 20
        filled = int(score_pct / 5)
        bar = "█" * filled + "░" * (bar_length - filled)
        score_text.append(f"[{bar}] {score_pct:.0f}%", style=self.colors.WARNING)

        tech_panel = Panel(
            score_text,
            title="📊 TECHNICAL SCORE",
            border_style=self.colors.CATEGORY,
            box=self.box_styles.PANEL,
        )

        # Display row 1
        self.console.print(Columns([price_panel, tech_panel]))
        self.console.print()

        # ===== Row 2: Technical Indicators Table =====
        ind_table = Table(
            box=self.box_styles.MENU,
            show_header=True,
            header_style=f"bold {self.colors.HEADER}",
            title="🔍 TECHNICAL INDICATORS",
            title_style=f"bold {self.colors.HIGHLIGHT}",
        )
        ind_table.add_column("Indicator", style=self.colors.HIGHLIGHT)
        ind_table.add_column("Value", justify="right")
        ind_table.add_column("Signal", justify="center")
        ind_table.add_column("Status", justify="center")

        for ind in data.get("indicators", []):
            signal = ind.get("signal", "")
            signal_color = (
                self.colors.SUCCESS
                if "Bullish" in signal or "Buy" in signal
                else self.colors.ERROR
                if "Bearish" in signal or "Sell" in signal
                else self.colors.WARNING
            )

            ind_table.add_row(
                ind.get("name", ""),
                str(ind.get("value", "")),
                f"[{signal_color}]{signal}[/{signal_color}]",
                ind.get("status", ""),
            )

        self.console.print(Panel(ind_table, border_style=self.colors.HEADER))
        self.console.print()

        # ===== Row 3: SMC Patterns + Divergence =====
        # SMC Patterns table
        smc_table = Table(
            box=self.box_styles.MENU,
            show_header=True,
            header_style=f"bold {self.colors.CATEGORY}",
        )
        smc_table.add_column("Pattern", style=self.colors.HIGHLIGHT)
        smc_table.add_column("Status", justify="center")
        smc_table.add_column("Confidence", justify="right")
        smc_table.add_column("Timeframe", justify="center")

        for pattern in data.get("smc_patterns", []):
            status = pattern.get("status", "")
            status_color = (
                self.colors.SUCCESS
                if "Bullish" in status or "Active" in status
                else self.colors.ERROR
                if "Bearish" in status
                else self.colors.WARNING
            )

            smc_table.add_row(
                pattern.get("name", ""),
                f"[{status_color}]{status}[/{status_color}]",
                f"{pattern.get('confidence', 0)}%",
                pattern.get("timeframe", ""),
            )

        smc_panel = Panel(
            smc_table,
            title="🤖 SMC PATTERNS",
            border_style=self.colors.CATEGORY,
            box=self.box_styles.PANEL,
        )

        # Divergence table
        div_table = Table(
            box=self.box_styles.MENU,
            show_header=True,
            header_style=f"bold {self.colors.INFO}",
        )
        div_table.add_column("Type", style=self.colors.HIGHLIGHT)
        div_table.add_column("Status", justify="center")
        div_table.add_column("Strength", justify="right")

        for div in data.get("divergence", []):
            status = div.get("status", "")
            status_color = (
                self.colors.SUCCESS
                if "Bullish" in status
                else self.colors.ERROR
                if "Bearish" in status
                else self.colors.WARNING
            )

            div_table.add_row(
                div.get("name", ""),
                f"[{status_color}]{status}[/{status_color}]",
                f"{div.get('strength', 0)}%",
            )

        div_panel = Panel(
            div_table,
            title="📉 DIVERGENCE DETECTION",
            border_style=self.colors.INFO,
            box=self.box_styles.PANEL,
        )

        self.console.print(Columns([smc_panel, div_panel]))
        self.console.print()

        # ===== Row 4: Backtest Results =====
        bt_table = Table(
            box=self.box_styles.TABLE,
            show_header=True,
            header_style=f"bold {self.colors.SUCCESS}",
            title="📚 BACKTEST RESULTS (1 YEAR)",
            title_style=f"bold {self.colors.HIGHLIGHT}",
        )
        bt_table.add_column("Metric", style=self.colors.HIGHLIGHT)
        bt_table.add_column("Value", justify="right")
        bt_table.add_column("Benchmark", justify="right")
        bt_table.add_column("Percentile", justify="center")

        bt_data = data.get("backtest") or {}
        metrics = [
            (
                "Total Return",
                f"{bt_data.get('return', 0):+.1f}%",
                f"{bt_data.get('benchmark_return', 0):+.1f}%",
                bt_data.get("return_percentile", 0),
            ),
            (
                "Sharpe Ratio",
                f"{bt_data.get('sharpe', 0):.2f}",
                f"{bt_data.get('benchmark_sharpe', 0):.2f}",
                bt_data.get("sharpe_percentile", 0),
            ),
            (
                "Sortino Ratio",
                f"{bt_data.get('sortino', 0):.2f}",
                "-",
                bt_data.get("sortino_percentile", 0),
            ),
            (
                "Max Drawdown",
                f"{bt_data.get('max_drawdown', 0):.1f}%",
                f"{bt_data.get('benchmark_dd', 0):.1f}%",
                bt_data.get("dd_percentile", 0),
            ),
            (
                "Win Rate",
                f"{bt_data.get('win_rate', 0)}%",
                "-",
                bt_data.get("win_rate_percentile", 0),
            ),
            (
                "Total Trades",
                str(bt_data.get("trades", 0)),
                "-",
                bt_data.get("trades_percentile", 0),
            ),
        ]

        for metric, value, benchmark, percentile in metrics:
            # Create percentile bar
            bar_length = 10
            filled = int(percentile / 10)
            bar = "█" * filled + "░" * (bar_length - filled)

            bt_table.add_row(metric, value, benchmark, f"{bar} {percentile}%")

        self.console.print(Panel(bt_table, border_style=self.colors.SUCCESS))
        self.console.print()

        # ===== Row 5: Risk Management =====
        risk_data = data.get("risk_management") or {}
        risk_text = Text()
        risk_text.append("Entry: ", style=self.colors.HIGHLIGHT)
        risk_text.append(
            f"₹{risk_data.get('entry', 0):,.2f}\n", style=self.colors.HIGHLIGHT
        )
        risk_text.append("Stop Loss: ", style=self.colors.HIGHLIGHT)
        risk_text.append(
            f"₹{risk_data.get('stop_loss', 0):,.2f} ", style=self.colors.ERROR
        )
        risk_text.append(
            f"({risk_data.get('risk_percent', 0):.1f}%)\n", style=self.colors.MUTED
        )
        risk_text.append("Target 1: ", style=self.colors.HIGHLIGHT)
        risk_text.append(
            f"₹{risk_data.get('target1', 0):,.2f} ", style=self.colors.SUCCESS
        )
        risk_text.append(
            f"(+{risk_data.get('target1_percent', 0):.1f}%)\n", style=self.colors.MUTED
        )
        risk_text.append("Target 2: ", style=self.colors.HIGHLIGHT)
        risk_text.append(
            f"₹{risk_data.get('target2', 0):,.2f} ", style=self.colors.SUCCESS
        )
        risk_text.append(
            f"(+{risk_data.get('target2_percent', 0):.1f}%)\n", style=self.colors.MUTED
        )
        risk_text.append("R:R Ratio: ", style=self.colors.HIGHLIGHT)
        risk_text.append(
            f"1:{risk_data.get('rr', 0):.1f}", style=f"bold {self.colors.WARNING}"
        )

        # Position sizing suggestions
        risk_text.append("\n\n", style=self.colors.HIGHLIGHT)
        risk_text.append("💡 POSITION SIZING:\n", style=self.colors.INFO)
        risk_text.append(
            f"Conservative: {risk_data.get('conservative_shares', 0)} shares ",
            style=self.colors.MUTED,
        )
        risk_text.append(
            f"(₹{risk_data.get('conservative_risk', 0):,})\n", style=self.colors.MUTED
        )
        risk_text.append(
            f"Moderate: {risk_data.get('moderate_shares', 0)} shares ",
            style=self.colors.MUTED,
        )
        risk_text.append(
            f"(₹{risk_data.get('moderate_risk', 0):,})\n", style=self.colors.MUTED
        )
        risk_text.append(
            f"Aggressive: {risk_data.get('aggressive_shares', 0)} shares ",
            style=self.colors.MUTED,
        )
        risk_text.append(
            f"(₹{risk_data.get('aggressive_risk', 0):,})", style=self.colors.MUTED
        )

        risk_panel = Panel(
            risk_text,
            title="💰 RISK MANAGEMENT",
            border_style=self.colors.WARNING,
            box=self.box_styles.PANEL,
        )

        # ===== Row 6: Strategy Reasoning =====
        reasons = data.get("reasoning") or {}
        reasons_text = Text()

        # Buy drivers
        reasons_text.append(
            "PRIMARY BUY DRIVERS:\n", style=f"bold {self.colors.SUCCESS}"
        )
        for reason in reasons.get("buy_drivers") or []:
            reasons_text.append(f"  ✅ {reason}\n", style=self.colors.SUCCESS)

        # Cautions
        reasons_text.append(
            "\nCAUTIONS / RISK FACTORS:\n", style=f"bold {self.colors.WARNING}"
        )
        for caution in reasons.get("cautions") or []:
            reasons_text.append(f"  ⚠️ {caution}\n", style=self.colors.WARNING)

        # Final verdict
        reasons_text.append("\n", style=self.colors.HIGHLIGHT)
        reasons_text.append("FINAL VERDICT: ", style=f"bold {self.colors.HIGHLIGHT}")
        reasons_text.append(reasons.get("verdict", ""), style=self.colors.HIGHLIGHT)

        reasoning_panel = Panel(
            reasons_text,
            title="💡 STRATEGY REASONING",
            border_style=self.colors.INFO,
            box=self.box_styles.PANEL,
        )

        # Display last row
        self.console.print(Columns([risk_panel, reasoning_panel]))
        self.console.print()

        # Footer
        self.console.print(Rule(style=self.colors.MUTED))
        self.console.print(
            f"{self.colors.info('[?]')} Options: {self.colors.highlight('[A]')}dd to watchlist | {self.colors.highlight('[P]')}aper trade | {self.colors.highlight('[B]')}ack | {self.colors.highlight('[E]')}xport"
        )
        self.console.print(f"{self.colors.info('[+]')} Next action: ", end="")

    # =========================================================================
    # Format 6: Data Health Dashboard
    # =========================================================================

    def render_data_health(
        self, metrics: dict[str, Any], gaps: list[dict[str, Any]]
    ) -> None:
        """
        Format 6: Data Health Dashboard

        Parameters:
            metrics (Dict): Overall health metrics
            gaps (List[Dict]): Data gap information
        """
        self.render_header(
            "DATA HEALTH DASHBOARD",
            f"System Integrity Status | {datetime.now().strftime('%Y-%m-%d')}",
        )

        # Overall metrics table
        overall_table = Table(
            box=self.box_styles.TABLE,
            title="🏥 Overall Metrics",
            title_style=f"bold {self.colors.HIGHLIGHT}",
            header_style=f"bold {self.colors.HEADER}",
        )
        overall_table.add_column("Metric", style=self.colors.HIGHLIGHT)
        overall_table.add_column("Status", justify="center")
        overall_table.add_column("Score", justify="right")
        overall_table.add_column("Details", justify="left")

        for m in metrics.get("overall", []):
            score = m.get("score", 0)
            if score >= 90:
                status = f"{self.colors.success('✅ Good')}"
                score_color = self.colors.SUCCESS
            elif score >= 70:
                status = f"{self.colors.warn('⚠️ Warning')}"
                score_color = self.colors.WARNING
            else:
                status = f"{self.colors.error('❌ Critical')}"
                score_color = self.colors.ERROR

            overall_table.add_row(
                m.get("name", ""),
                status,
                f"[{score_color}]{score}%[/{score_color}]",
                m.get("details", ""),
            )

        self.console.print(overall_table)
        self.console.print()

        # Data gap table
        if gaps:
            gap_table = Table(
                box=self.box_styles.TABLE,
                title="⚠️ Top Data Gaps",
                title_style=f"bold {self.colors.WARNING}",
                header_style=f"bold {self.colors.WARNING}",
            )
            gap_table.add_column("Stock", style=self.colors.HIGHLIGHT)
            gap_table.add_column("Missing Days", justify="right")
            gap_table.add_column("Oldest Gap", justify="center")
            gap_table.add_column("Latest Gap", justify="center")
            gap_table.add_column("Action", justify="center")

            for g in gaps[:10]:  # Top 10
                gap_table.add_row(
                    g.get("symbol", ""),
                    str(g.get("gap_count", 0)),
                    g.get("oldest_gap", ""),
                    g.get("latest_gap", ""),
                    f"{self.colors.info('Repair Required')}",
                )

            self.console.print(gap_table)

        # ML Coverage table
        ml_data = metrics.get("ml_coverage", {})
        ml_table = Table(
            box=self.box_styles.MENU,
            title="🤖 ML Model Coverage",
            title_style=f"bold {self.colors.CATEGORY}",
            header_style=f"bold {self.colors.CATEGORY}",
        )
        ml_table.add_column("Universe", style=self.colors.HIGHLIGHT)
        ml_table.add_column("Trained", justify="right")
        ml_table.add_column("Total", justify="right")
        ml_table.add_column("Coverage", justify="right")
        ml_table.add_column("Last Training", justify="center")

        for item in ml_data.get("universes", []):
            coverage = item.get("coverage", 0)
            coverage_color = (
                self.colors.SUCCESS
                if coverage >= 80
                else self.colors.WARNING
                if coverage >= 50
                else self.colors.ERROR
            )

            ml_table.add_row(
                item.get("name", ""),
                str(item.get("trained", 0)),
                str(item.get("total", 0)),
                f"[{coverage_color}]{coverage}%[/{coverage_color}]",
                item.get("last_training", ""),
            )

        self.console.print(ml_table)
        self.console.print()

        # Storage usage
        storage = metrics.get("storage", {})
        storage_text = Text()
        storage_text.append("💾 STORAGE USAGE:\n", style=f"bold {self.colors.INFO}")

        for item in storage.get("breakdown", []):
            size = item.get("size_gb", 0)
            percentage = item.get("percentage", 0)
            bar_length = 20
            filled = int(percentage / 5)
            bar = "█" * filled + "░" * (bar_length - filled)

            storage_text.append(
                f"  {item.get('name', '')}: ", style=self.colors.HIGHLIGHT
            )
            storage_text.append(f"{size:.1f} GB ", style=self.colors.HIGHLIGHT)
            storage_text.append(f"[{bar}] {percentage}%\n", style=self.colors.MUTED)

        self.console.print(Panel(storage_text, border_style=self.colors.INFO))
        self.console.print()

        # Recommended actions
        actions = metrics.get("actions", [])
        if actions:
            actions_text = Text()
            actions_text.append(
                "🔧 RECOMMENDED ACTIONS:\n", style=f"bold {self.colors.WARNING}"
            )

            for action in actions:
                priority = action.get("priority", "MEDIUM")
                if priority == "HIGH":
                    prefix = "🔴"
                    priority_style = self.colors.ERROR
                elif priority == "MEDIUM":
                    prefix = "🟡"
                    priority_style = self.colors.WARNING
                else:
                    prefix = "🟢"
                    priority_style = self.colors.SUCCESS

                actions_text.append(f"  {prefix} ", style=priority_style)
                actions_text.append(f"[{priority_style}]{priority}[/{priority_style}] ")
                actions_text.append(
                    f"{action.get('description', '')}\n", style=self.colors.HIGHLIGHT
                )

            self.console.print(Panel(actions_text, border_style=self.colors.WARNING))

        # Footer
        self.console.print()
        self.console.print(
            f"{self.colors.info('[?]')} Options: {self.colors.highlight('[R]')}epair now | {self.colors.highlight('[S]')}chedule | {self.colors.highlight('[E]')}xport | {self.colors.highlight('[B]')}ack"
        )
        self.console.print(f"{self.colors.info('[+]')} Select action: ", end="")

    # =========================================================================
    # Format 7: Error/Warning Messages
    # =========================================================================

    def render_error(self, message: str, is_warning: bool = False) -> None:
        """
        Format 7: Error/Warning Messages with colored panels

        Parameters:
            message (str): Error or warning message
            is_warning (bool): True for warning, False for error
        """
        style = self.colors.WARNING if is_warning else self.colors.ERROR
        icon = "⚠️" if is_warning else "❌"
        title = "WARNING" if is_warning else "ERROR"

        panel = Panel(
            f"[{style}]{icon} {message}[/{style}]\n\n"
            f"{self.colors.info('💡 Suggestion:')} Check logs or verify connectivity.",
            title=title,
            border_style=style,
            box=self.box_styles.PANEL,
        )

        self.console.print()
        self.console.print(panel)
        self.console.print()

    # =========================================================================
    # Format 8: System Health Check
    # =========================================================================

    def render_system_check(self, components: list[dict[str, Any]]) -> None:
        """
        Format 8: System Health Check Dashboard

        Parameters:
            components (List[Dict]): System component status
        """
        self.render_header(
            "SYSTEM HEALTH CHECK",
            f"Diagnostics | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )

        table = Table(
            box=self.box_styles.TABLE,
            show_header=True,
            header_style=f"bold {self.colors.HEADER}",
        )
        table.add_column("Component", style=self.colors.HIGHLIGHT)
        table.add_column("Status", justify="center")
        table.add_column("Details", justify="left")
        table.add_column("Performance", justify="right")

        for c in components:
            status = c.get("status", "UNKNOWN")
            if status == "OK":
                status_display = f"{self.colors.success('✅ OK')}"
                perf_color = self.colors.SUCCESS
            elif status == "WARN":
                status_display = f"{self.colors.warn('⚠️ WARN')}"
                perf_color = self.colors.WARNING
            else:
                status_display = f"{self.colors.error('❌ ERROR')}"
                perf_color = self.colors.ERROR

            perf = c.get("performance", 0)
            if perf > 0:
                perf_display = f"{self.colors.dim(str(perf))}"
            else:
                perf_display = "-"

            table.add_row(
                c.get("name", ""),
                status_display,
                c.get("detail", ""),
                f"[{perf_color}]{perf_display}[/{perf_color}]",
            )

        self.console.print(table)
        self.console.print()

        # API Rate Limits
        rate_limits = next(
            (c for c in components if c.get("name") == "API Rate Limits"), {}
        )
        if rate_limits:
            remaining = rate_limits.get("remaining", 0)
            total = rate_limits.get("total", 100)
            percentage = (remaining / total) * 100

            bar_length = 30
            filled = int(percentage / (100 / bar_length))
            bar = "█" * filled + "░" * (bar_length - filled)

            self.console.print(f"{self.colors.info('📊 API Rate Limits:')}")
            self.console.print(
                f"[{bar}] {remaining}/{total} remaining ({percentage:.0f}%)"
            )

        self.console.print()
        self.console.print(
            f"{self.colors.info('[?]')} Options: {self.colors.highlight('[R]')}efresh | {self.colors.highlight('[E]')}xport | {self.colors.highlight('[B]')}ack"
        )
        self.console.print(f"{self.colors.info('[+]')} Select action: ", end="")

    # =========================================================================
    # Format 9: Help/Information Panel
    # =========================================================================

    def render_help(
        self, shortcuts: list[dict[str, str]], categories: dict[str, list[str]]
    ) -> None:
        """
        Format 9: Help/Information Panel

        Parameters:
            shortcuts (List[Dict]): Keyboard shortcuts
            categories (Dict): Feature categories and descriptions
        """
        self.render_header("HELP & QUICK REFERENCE", "Keyboard Shortcuts & Features")

        # Shortcuts table
        shortcut_table = Table(
            box=self.box_styles.MENU,
            title="⌨️ Keyboard Shortcuts",
            title_style=f"bold {self.colors.INFO}",
            header_style=f"bold {self.colors.INFO}",
        )
        shortcut_table.add_column(
            "Shortcut", style=self.colors.HIGHLIGHT, justify="center"
        )
        shortcut_table.add_column("Action", style=self.colors.HIGHLIGHT)
        shortcut_table.add_column("Description", style=self.colors.MUTED)

        for s in shortcuts:
            shortcut_table.add_row(
                f"{self.colors.info(s['key'])}",
                s.get("action", ""),
                s.get("description", ""),
            )

        self.console.print(shortcut_table)
        self.console.print()

        # Features by category
        for category, features in categories.items():
            panel_text = Text()
            for feature in features:
                panel_text.append(f"  • {feature}\n", style=self.colors.HIGHLIGHT)

            panel = Panel(
                panel_text,
                title=f"📋 {category}",
                border_style=self.colors.CATEGORY,
                box=self.box_styles.PANEL,
            )
            self.console.print(panel)

        self.console.print()
        self.console.print(
            f"{self.colors.info('💡 Tip:')} Press '{self.colors.highlight('?')}' at any time to see this help screen."
        )
        self.console.print(
            f"{self.colors.info('[?]')} Press {self.colors.highlight('[B]')} to go back"
        )

    # =========================================================================
    # Format 10: Export Preview
    # =========================================================================

    def render_export_preview(
        self, path: str, stats: dict[str, Any], sample: pd.DataFrame
    ) -> None:
        """
        Format 10: Export Results Preview

        Parameters:
            path (str): Export file path
            stats (Dict): Export statistics
            sample (pd.DataFrame): Sample data (first 5 rows)
        """
        self.render_header("EXPORT PREVIEW", f"Target: {path}")

        # File metadata
        meta_text = Text()
        meta_text.append("Format: ", style=self.colors.HIGHLIGHT)
        meta_text.append(
            f"{stats.get('format', 'CSV')}\n", style=f"bold {self.colors.HIGHLIGHT}"
        )
        meta_text.append("Size: ", style=self.colors.HIGHLIGHT)
        meta_text.append(f"{stats.get('size', '0 KB')}\n", style=self.colors.HIGHLIGHT)
        meta_text.append("Rows: ", style=self.colors.HIGHLIGHT)
        meta_text.append(f"{stats.get('rows', 0):,}\n", style=self.colors.HIGHLIGHT)
        meta_text.append("Columns: ", style=self.colors.HIGHLIGHT)
        meta_text.append(f"{stats.get('cols', 0)}", style=self.colors.HIGHLIGHT)

        self.console.print(
            Panel(meta_text, title="📤 File Metadata", border_style=self.colors.INFO)
        )
        self.console.print()

        # Sample data
        if not sample.empty:
            table = Table(
                box=self.box_styles.TABLE,
                title="📋 Sample Data (First 5 Rows)",
                title_style=f"bold {self.colors.HIGHLIGHT}",
            )

            for col in sample.columns:
                table.add_column(str(col), style=self.colors.HIGHLIGHT)

            for _, row in sample.head(5).iterrows():
                table.add_row(*[str(val) for val in row])

            self.console.print(table)

        self.console.print()
        self.console.print(f"{self.colors.success('✅ Export Successful:')} {path}")
        self.console.print(f"File size: {stats.get('size', '0 KB')}")
        self.console.print()

        self.console.print(
            f"{self.colors.info('[?]')} Options: {self.colors.highlight('[O]')}pen folder | {self.colors.highlight('[E]')}mail | {self.colors.highlight('[B]')}ack"
        )
        self.console.print(f"{self.colors.info('[+]')} Select action: ", end="")

    # =========================================================================
    # Configuration Wizard
    # =========================================================================

    def render_config_wizard(
        self, step: int, total_steps: int, current_config: dict[str, Any]
    ) -> None:
        """
        Configuration wizard step header

        Parameters:
            step (int): Current step number
            total_steps (int): Total steps
            current_config (Dict): Current configuration selections
        """
        # Progress bar
        progress_text = f"Step {step} of {total_steps} "
        bar_length = 20
        filled = int((step / total_steps) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        self.console.print(
            f"{self.colors.category(progress_text)} [{self.colors.warning(bar)}]"
        )
        self.console.print()

        # Current selections
        if current_config:
            selections = []
            for k, v in current_config.items():
                if v:  # Only show non-empty selections
                    selections.append(
                        f"{self.colors.info(k)}: {self.colors.highlight(str(v))}"
                    )

            if selections:
                self.console.print(
                    Panel(
                        " | ".join(selections),
                        title="Current Selections",
                        border_style=self.colors.MUTED,
                        box=self.box_styles.MINIMAL,
                    )
                )
                self.console.print()

    # =========================================================================
    # Live Table Support
    # =========================================================================

    def live_table(
        self, data_generator: Generator[list[dict[str, Any]], None, None]
    ) -> None:
        """
        Display live-updating table for real-time data

        Parameters:
            data_generator: Generator yielding chunks of data
        """
        with Live(self.console, refresh_per_second=4) as live:
            for chunk in data_generator:
                table = self._create_results_table(chunk)
                live.update(table)

    # =========================================================================
    # User Input Handling
    # =========================================================================

    def get_user_choice(self, prompt: str, valid_options: list[str] = None) -> str:
        """
        Get validated user input with proper formatting

        Parameters:
            prompt (str): Input prompt
            valid_options (List[str]): Valid options (case-insensitive)

        Returns:
            str: Uppercase user choice

        Example:
            >>> choice = ui.get_user_choice("Select option", ["1", "2", "Q"])
        """
        while True:
            choice = Prompt.ask(
                f"{self.colors.info('[+]')} {prompt}",
                choices=valid_options if valid_options else None,
                show_choices=False,
            )

            if valid_options and choice.upper() not in [
                v.upper() for v in valid_options
            ]:
                self.render_error(
                    f"Invalid option. Choose from: {', '.join(valid_options)}",
                    is_warning=True,
                )
                continue

            return choice.upper()

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _format_status(self, status: str) -> str:
        """
        Format status with appropriate color

        Parameters:
            status (str): Status string

        Returns:
            str: Formatted status with rich markup
        """
        status_lower = status.lower()

        if (
            "ready" in status_lower
            or "complete" in status_lower
            or "success" in status_lower
        ):
            return self.colors.success(status)
        elif (
            "warning" in status_lower
            or "caution" in status_lower
            or "pending" in status_lower
        ):
            return self.colors.warn(status)
        elif (
            "error" in status_lower
            or "fail" in status_lower
            or "critical" in status_lower
        ):
            return self.colors.error(status)
        else:
            return self.colors.dim(status)

    def clear(self) -> None:
        """Clear the console screen"""
        self.console.clear()

    def print_rule(self, style: str = None) -> None:
        """Print a horizontal rule"""
        self.console.print(Rule(style=style or self.colors.MUTED))
