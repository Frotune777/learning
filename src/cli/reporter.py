"""
File: src/cli/reporter.py
Purpose: ScreenerReporter — formats and displays screener results using VisualUI.
         Mirrors screeni-py's ReportingService, adapted for learning's 13-strategy schema.

         Key behaviors:
         - Print results to screen first (always)
         - Offer optional export to CSV (user prompt)
         - Generate narrative reasoning from 13 strategies + divergences + TA score
         - Strategy Inspector view for individual stock deep-dive

Dependencies:
    External:
    - pandas>=2.2.3: DataFrame handling
    - rich: Console output
    Internal:
    - src.cli.visual: VisualUI rendering engine
    - src.core.consensus_engine: add_consensus_score

Last Modified: 2026-06-01
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import pandas as pd
from rich.console import Console

from src.cli.visual import VisualUI

console = Console()


class ScreenerReporter:
    """
    Formats and displays screener results for the NSE pipeline.

    Design Pattern: Service Object — delegates all rendering to VisualUI,
    applies consensus scoring, generates narratives, and handles optional export.

    Public Methods:
        print_summary_table(df, title)        — color-coded Rich table, then ask to export
        print_strategy_inspector(symbol, df)  — full 13-strategy panel for one stock
        print_consensus_leaderboard(df)       — top stocks ranked by CONSENSUS_SCORE
        generate_narrative(row)               — human-readable buy/sell reasoning
        export_csv(df, path)                  — write CSV with all columns
    """

    def __init__(self) -> None:
        self.ui = VisualUI()

    # =========================================================================
    # Public: Summary Table
    # =========================================================================

    def print_summary_table(
        self,
        df: pd.DataFrame,
        title: str = "SCREENER RESULTS",
        max_rows: int = 50,
    ) -> None:
        """
        Print color-coded screener summary on screen, then ask user if they
        want to export to CSV. Export is never mandatory.

        Parameters:
            df       : Analyzed screener DataFrame (must have SYMBOL, CMP etc.)
            title    : Table title string
            max_rows : Max rows to show on screen (all rows exported if chosen)
        """
        if df.empty:
            console.print("[yellow]No results to display.[/yellow]")
            return

        # Enrich with consensus if not already present
        df = self._ensure_consensus(df)

        self.ui.render_results_table(df, title=title, max_rows=max_rows)
        self._offer_export(df, title)

    # =========================================================================
    # Public: Strategy Inspector
    # =========================================================================

    def print_strategy_inspector(self, symbol: str, df: pd.DataFrame) -> None:
        """
        Show all 13 strategy signals for a single stock.

        Parameters:
            symbol : NSE symbol string (e.g. 'TCS')
            df     : Analyzed DataFrame (from screener output)
        """
        df = self._ensure_consensus(df)
        row_match = df[df["SYMBOL"].astype(str).str.upper() == symbol.upper()]
        if row_match.empty:
            console.print(f"[red]Symbol '{symbol}' not found in results.[/red]")
            return

        row = row_match.iloc[0]
        self.ui.render_strategy_inspector(symbol, row)

    # =========================================================================
    # Public: Consensus Leaderboard
    # =========================================================================

    def print_consensus_leaderboard(self, df: pd.DataFrame, top_n: int = 20) -> None:
        """
        Show stocks ranked by CONSENSUS_SCORE (highest first).

        Parameters:
            df    : Analyzed DataFrame
            top_n : Number of top stocks to display
        """
        df = self._ensure_consensus(df)
        self.ui.render_header(
            "CONSENSUS LEADERBOARD",
            f"Top {top_n} stocks by multi-strategy agreement · {datetime.now().strftime('%Y-%m-%d')}",
        )
        self.ui.render_consensus_leaderboard(df, top_n=top_n)
        self._offer_export(df, "consensus_leaderboard")

    # =========================================================================
    # Public: Narrative Generator
    # =========================================================================

    def generate_narrative(self, row: pd.Series | dict[str, Any]) -> str:
        """
        Generate a highly professional, structured dynamic quantitative narrative.
        Combines 13 strategy votes, divergences, moving averages, and quant indicators.

        Parameters:
            row : Single row from analyzed DataFrame (pd.Series or dict)

        Returns:
            str : Dynamic structured quantitative explanation
        """
        cmp_val = row.get("CMP")
        cmp_str = f"₹{cmp_val:,.2f}" if pd.notna(cmp_val) else "N/A"

        # Overall Ratings & States
        market_state = str(row.get("MARKET_STATE", "SIDEWAYS"))
        action = str(row.get("PORTFOLIO_ACTION", "NEUTRAL / SIDEWAYS"))
        confidence = row.get("CONFIDENCE_PCT", 50.0)

        bull_score = row.get("WEIGHTED_BULL_SCORE", 0.0)
        bear_score = row.get("WEIGHTED_BEAR_SCORE", 0.0)

        # Dynamic Stop Loss and Targets
        stop_price = row.get("STOP_PRICE")
        suggested_qty = row.get("SUGGESTED_QTY")
        target_20pct = row.get("GTT_TARGET_20PCT") or (
            cmp_val * 1.2 if pd.notna(cmp_val) else None
        )

        stop_str = (
            f"₹{stop_price:,.2f}" if pd.notna(stop_price) and stop_price > 0 else "N/A"
        )
        target_str = (
            f"₹{target_20pct:,.2f}"
            if pd.notna(target_20pct) and target_20pct > 0
            else "N/A"
        )
        qty_str = (
            str(int(suggested_qty))
            if pd.notna(suggested_qty) and suggested_qty > 0
            else "N/A"
        )

        # Signal categorization
        buy_drivers: list[str] = []
        cautions: list[str] = []

        _BUY = {
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
        _SELL = {
            "Explosive Sell",
            "Lorentzian Sell",
            "Squeeze Active (Bearish)",
            "Close Long",
        }

        strategy_labels = {
            "STR_NIFTY_SHOP_ACTION": "Nifty Shop",
            "STR_BUY_LOW_ACTION": "Buy Low Sell High",
            "STR_TURTLE_ACTION": "Turtle (55D Breakout)",
            "STR_RDX_ACTION": "RDX Momentum",
            "STR_100SMA_ACTION": "100 SMA Breakout",
            "STR_ETF_SHOP_ACTION": "ETF Shop",
            "STR_SUPER_BO_ACTION": "Super BO Breakout",
            "STR_DMA_REV_ACTION": "DMA Reverse",
            "STR_DMA_NOSL_ACTION": "DMA No-SL",
            "STR_VCP_ACTION": "Volatility Contraction Pattern (VCP)",
            "STR_TTM_ACTION": "TTM Squeeze",
            "STR_SUPERTREND_ACTION": "Dual Supertrend",
            "STR_LORENTZIAN_ACTION": "Lorentzian ML Classification",
        }

        # Scan columns
        for col, label in strategy_labels.items():
            val = str(row.get(col, ""))
            if val in _BUY:
                buy_drivers.append(f"{label} ({val})")
            elif val in _SELL:
                cautions.append(f"{label} ({val})")

        # Divergences
        rsi_div = str(row.get("RSI_DIVERGENCE", "None"))
        macd_div = str(row.get("MACD_DIVERGENCE", "None"))
        if "Bullish" in rsi_div:
            buy_drivers.append(f"RSI Bullish Divergence ({rsi_div})")
        elif "Bearish" in rsi_div:
            cautions.append(f"RSI Bearish Divergence ({rsi_div})")
        if "Bullish" in macd_div:
            buy_drivers.append(f"MACD Bullish Divergence ({macd_div})")
        elif "Bearish" in macd_div:
            cautions.append(f"MACD Bearish Divergence ({macd_div})")

        # Candlestick
        candle = str(row.get("STR_CANDLE_PATTERN", "None"))
        if candle not in ("None", "N/A", ""):
            buy_drivers.append(f"Candlestick: {candle}")

        # Narrative composition
        score_int = int(row.get("CONSENSUS_SCORE", 0))

        header = (
            f"OVERALL QUANT RATING\n"
            f"═══════════════════════════════════════════\n"
            f"  CMP            : {cmp_str}\n"
            f"  Market State   : {market_state}\n"
            f"  Bull Score     : {bull_score:.1f}/10\n"
            f"  Bear Score     : {bear_score:.1f}/10\n"
            f"  Sim Action     : {action}\n"
            f"  Confidence     : {confidence}%\n"
            f"  Rec Stop Loss  : {stop_str}\n"
            f"  Target Price   : {target_str} (20% Target)\n"
            f"  Position Size  : {qty_str} shares (₹5L Capital, 1% Risk)\n"
            f"═══════════════════════════════════════════\n\n"
        )

        bullets = []

        # Technical Summary
        if market_state == "BULL RUN":
            bullets.append(
                "• Primary Trend: Strongly Bullish. Price remains above long-term moving averages (50 DMA and 200 DMA)."
            )
        elif market_state == "RECOVERY":
            bullets.append(
                "• Primary Trend: In Recovery. Trading above 50 DMA but currently below major 200 DMA overhead resistance."
            )
        elif market_state == "BEAR TERRITORY":
            bullets.append(
                "• Primary Trend: Bear Territory. Key long-term moving averages are sloping down and trading above CMP."
            )
        else:
            bullets.append(
                "• Primary Trend: Sideways Consolidation. Price within historical range near major moving averages."
            )

        # Buy catalysts
        if buy_drivers:
            bullets.append(
                "• Positive Catalysts:\n  - " + "\n  - ".join(buy_drivers[:4])
            )
        else:
            bullets.append(
                "• Positive Catalysts: No active strategy buy setups or bullish indicators triggered."
            )

        # Sell indicators / risks
        if cautions:
            bullets.append(
                "• Risk Factors & Cautions:\n  - " + "\n  - ".join(cautions[:3])
            )
        else:
            bullets.append(
                "• Risk Factors & Cautions: No active strategy sell triggers or bearish divergences."
            )

        # Actionable Advice
        advice = ""
        if action == "STRONG BUY":
            advice = (
                f"• Verdict: High Conviction Setup. Multiple momentum breakout systems and ML models are aligned. "
                f"Enter long at {cmp_str} or on minor dips. Setup dynamic stop-loss below {stop_str} and target {target_str}."
            )
        elif action == "HOLD / ADD ON DIPS":
            # Wockpharma case: 4+ buys, but some missing
            trend_only = all(
                "Breakout" in d
                or "Trend" in d
                or "DMA" in d
                or "Turtle" in d
                or "RDX" in d
                for d in buy_drivers[:3]
            )
            if trend_only and len(buy_drivers) >= 3:
                advice = (
                    f"• Verdict: Moderately Bullish. Independent trend-following systems (such as Turtle, DMA, or RDX) are confirming, "
                    f"but conviction remains moderate because VCP, TTM Squeeze, or ML classifiers are inactive. "
                    f"Hold existing holdings and consider adding selectively on price dips. Maintain trailing stop below {stop_str}."
                )
            else:
                advice = (
                    f"• Verdict: Bullish bias active. Select setups have fired. "
                    f"Hold active simulated exposure, trail stops to {stop_str}, and target {target_str}."
                )
        elif action == "EXIT / REDUCE" or action == "REDUCE / MONITOR":
            advice = (
                "• Verdict: Bearish Setup / Exit Signal. Active strategy exits or ML sell triggers have triggered. "
                "Protect capital: reduce position size or exit fully. Avoid averaging down."
            )
        else:
            advice = (
                "• Verdict: Sideways / Neutral consolidation. Conflicting or absent indicators. "
                "Monitor key breakout ranges before establishing new active exposure."
            )
        bullets.append(advice)

        return header + "\n".join(bullets)

    # =========================================================================
    # Public: Export
    # =========================================================================

    def export_csv(self, df: pd.DataFrame, path: str) -> str:
        """
        Write the full DataFrame to CSV. Does not add narrative by default
        (caller can enrich first).

        Returns:
            str : Absolute path to the written file
        """
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        df.to_csv(path, index=False)
        console.print(f"[green]✔  Exported {len(df)} rows → {path}[/green]")
        return path

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _ensure_consensus(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add CONSENSUS_SCORE / CONSENSUS_CALLOUT columns if not already present."""
        if "CONSENSUS_SCORE" not in df.columns:
            try:
                from src.core.consensus_engine import add_consensus_score

                df = add_consensus_score(df)
            except Exception:
                df["CONSENSUS_SCORE"] = 0
                df["CONSENSUS_CALLOUT"] = "N/A"
        return df

    def _offer_export(self, df: pd.DataFrame, label: str) -> None:
        """
        Ask the user if they want to export to CSV.
        Export is OPTIONAL — never mandated.
        """
        console.print()
        try:
            ans = input("  Export results to CSV? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return

        if ans != "y":
            console.print("[dim]  Skipped export.[/dim]")
            return

        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        safe_label = label.lower().replace(" ", "_")
        default_path = os.path.join("data", "processed", f"{safe_label}_{date_str}.csv")

        try:
            custom = input(f"  Save path [{default_path}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            custom = ""

        path = custom if custom else default_path
        self.export_csv(df, path)
