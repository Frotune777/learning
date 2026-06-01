"""
File: src/portfolio/portfolio_engine.py
Purpose: Simulated portfolio engine tracking capital allocation, risk limits, and orders.
Last Modified: 2026-06-01
"""

import logging
import os
from typing import Any

import numpy as np
import pandas as pd

from src.nse_bhavcopy.position_sizer import calculate_position_size

LOGGER = logging.getLogger(__name__)


class Portfolio:
    """
    Simulated portfolio tracker.
    Tracks cash, open positions, total valuation, and exposure limits.
    """

    def __init__(
        self,
        initial_cash: float = 500_000.0,
        max_positions: int = 15,
        max_sector_exposure_pct: float = 0.25,
        max_single_position_pct: float = 0.10,
    ) -> None:
        self.initial_cash: float = initial_cash
        self.cash: float = initial_cash
        self.max_positions: int = max_positions
        self.max_sector_exposure_pct: float = max_sector_exposure_pct
        self.max_single_position_pct: float = max_single_position_pct
        self.positions: dict[str, dict[str, Any]] = {}  # Symbol -> Position details

    def get_total_value(self) -> float:
        """Calculate current total portfolio value (cash + market value of open positions)."""
        pos_val = sum(pos["qty"] * pos["current_price"] for pos in self.positions.values())
        return self.cash + pos_val

    def get_sector_exposures(self) -> dict[str, float]:
        """Calculate absolute allocation in INR per sector."""
        exposures: dict[str, float] = {}
        for pos in self.positions.values():
            sect = pos.get("sector", "Other") or "Other"
            val = pos["qty"] * pos["current_price"]
            exposures[sect] = exposures.get(sect, 0.0) + val
        return exposures

    def get_sector_exposure_percentages(self) -> dict[str, float]:
        """Calculate sector exposure as percentage of total portfolio value."""
        total = self.get_total_value()
        if total <= 0:
            return {}
        exps = self.get_sector_exposures()
        return {sect: val / total for sect, val in exps.items()}

    def can_add(self, symbol: str, sector: str, price: float, value: float) -> tuple[bool, str]:
        """Check if we can add a new position without breaching constraints."""
        symbol = symbol.strip().upper()
        if symbol in self.positions:
            return False, "Position already exists"

        if len(self.positions) >= self.max_positions:
            return False, f"Breaches max position limit of {self.max_positions}"

        if value > self.cash:
            return False, f"Insufficient cash: Needs ₹{value:,.2f}, has ₹{self.cash:,.2f}"

        total_val = self.get_total_value()
        
        # Check single position limit
        pct_single = value / total_val
        if pct_single > self.max_single_position_pct:
            return False, f"Single position allocation ({pct_single:.1%}) exceeds limit ({self.max_single_position_pct:.1%})"

        # Check sector exposure limit
        sector = sector or "Other"
        sector_allocations = self.get_sector_exposures()
        new_sector_val = sector_allocations.get(sector, 0.0) + value
        pct_sector = new_sector_val / total_val
        if pct_sector > self.max_sector_exposure_pct:
            return False, f"Sector {sector} allocation ({pct_sector:.1%}) exceeds limit ({self.max_sector_exposure_pct:.1%})"

        return True, "Approved"

    def add_position(
        self,
        symbol: str,
        qty: float,
        price: float,
        stop_price: float,
        target_price: float,
        sector: str | None = None,
        date_str: str | None = None,
    ) -> bool:
        """Add a position after applying validation checks."""
        symbol = symbol.strip().upper()
        val = qty * price
        ok, reason = self.can_add(symbol, sector or "Other", price, val)
        if not ok:
            LOGGER.warning("Cannot add position in %s: %s", symbol, reason)
            return False

        self.cash -= val
        self.positions[symbol] = {
            "symbol": symbol,
            "qty": qty,
            "entry_price": price,
            "current_price": price,
            "stop_price": stop_price,
            "target_price": target_price,
            "sector": sector or "Other",
            "entry_date": date_str or "",
            "risk_amount": (price - stop_price) * qty if price > stop_price else 0.0
        }
        LOGGER.info("Added position %s: %d shares @ ₹%.2f", symbol, qty, price)
        return True

    def exit_position(self, symbol: str, exit_price: float) -> None:
        """Exit an open position and realize proceeds."""
        symbol = symbol.strip().upper()
        if symbol not in self.positions:
            return

        pos = self.positions.pop(symbol)
        proceeds = pos["qty"] * exit_price
        self.cash += proceeds
        LOGGER.info("Exited position %s @ ₹%.2f. Realised proceeds: ₹%.2f", symbol, exit_price, proceeds)

    def get_heat(self) -> float:
        """Calculate total cash at risk across all open positions (Portfolio Heat)."""
        tot_risk = sum(pos.get("risk_amount", 0.0) for pos in self.positions.values())
        total_val = self.get_total_value()
        return tot_risk / total_val if total_val > 0 else 0.0

    def update_prices(self, quotes: dict[str, float]) -> None:
        """Update current market price for all open positions."""
        for sym, pos in self.positions.items():
            if sym in quotes:
                pos["current_price"] = quotes[sym]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert current positions to a formatted pandas DataFrame."""
        if not self.positions:
            return pd.DataFrame(columns=[
                "Symbol", "Qty", "Entry Price", "Current Price", "Stop Price", 
                "Target Price", "Sector", "Entry Date", "Current Value", "P&L", "P&L %"
            ])
        rows = []
        for pos in self.positions.values():
            qty = pos["qty"]
            entry = pos["entry_price"]
            curr = pos["current_price"]
            val = qty * curr
            pnl = val - (qty * entry)
            pnl_pct = (pnl / (qty * entry)) * 100.0 if entry > 0 else 0.0
            rows.append({
                "Symbol": pos["symbol"],
                "Qty": qty,
                "Entry Price": entry,
                "Current Price": curr,
                "Stop Price": pos["stop_price"],
                "Target Price": pos["target_price"],
                "Sector": pos["sector"],
                "Entry Date": pos["entry_date"],
                "Current Value": round(val, 2),
                "P&L": round(pnl, 2),
                "P&L %": round(pnl_pct, 2),
            })
        return pd.DataFrame(rows)


class PortfolioEngine:
    """
    Portfolio Engine coordinating allocation, correlation controls, and order routing.
    """

    def __init__(
        self,
        daily_dir: str = "data/historical/1d",
        correlation_lookback: int = 30,
        correlation_threshold: float = 0.8,
    ) -> None:
        self.daily_dir = daily_dir
        self.correlation_lookback = correlation_lookback
        self.correlation_threshold = correlation_threshold

    def calculate_correlations(self, candidate_symbols: list[str], active_symbols: list[str]) -> pd.DataFrame:
        """Calculate correlation matrix of candidates with active positions."""
        if not active_symbols:
            return pd.DataFrame(0.0, index=candidate_symbols, columns=candidate_symbols)

        series_dict = {}
        all_syms = list(set(candidate_symbols + active_symbols))
        for sym in all_syms:
            p_path = os.path.join(self.daily_dir, f"{sym.upper()}.parquet")
            if os.path.exists(p_path):
                try:
                    df = pd.read_parquet(p_path)
                    if "Close" in df.columns and len(df) >= self.correlation_lookback:
                        # Fetch last N daily returns
                        returns = df["Close"].pct_change().tail(self.correlation_lookback)
                        series_dict[sym] = returns
                except Exception:
                    pass
        if len(series_dict) < 2:
            return pd.DataFrame(0.0, index=all_syms, columns=all_syms)

        df_returns = pd.DataFrame(series_dict)
        return df_returns.corr()

    def allocate(
        self,
        signals_df: pd.DataFrame,
        portfolio: Portfolio,
        date_str: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Allocate capital to buy/sell/hold based on daily signals, correlation checks, and portfolio limits.
        
        Parameters:
            signals_df (pd.DataFrame): Output from StockScreener after scoring (must have COMPOSITE_SCORE, RANK).
            portfolio (Portfolio): Portfolio instance tracking current holdings.
            date_str (str): Target trade date.
            
        Returns:
            list[dict[str, Any]]: List of recommended trade order dicts.
        """
        if signals_df.empty:
            return []

        orders = []

        # 1. Handle Exits first: check open positions against stop-loss or profit targets
        # Or if the trend status turns bad
        active_positions = list(portfolio.positions.keys())
        for sym in active_positions:
            pos = portfolio.positions[sym]
            quotes = signals_df[signals_df["SYMBOL"] == sym]
            if not quotes.empty:
                cmp = float(quotes["CMP"].values[0])
                if cmp <= pos["stop_price"]:
                    orders.append({
                        "symbol": sym,
                        "action": "SELL",
                        "qty": pos["qty"],
                        "price": cmp,
                        "reason": f"Stop Loss Triggered (Stop ₹{pos['stop_price']:.2f}, CMP ₹{cmp:.2f})"
                    })
                elif cmp >= pos["target_price"]:
                    orders.append({
                        "symbol": sym,
                        "action": "SELL",
                        "qty": pos["qty"],
                        "price": cmp,
                        "reason": f"Target Reached (Target ₹{pos['target_price']:.2f}, CMP ₹{cmp:.2f})"
                    })

        # Process exits on portfolio first
        for o in orders:
            if o["action"] == "SELL":
                portfolio.exit_position(o["symbol"], o["price"])

        # 2. Process Entries: Look at Buy recommendations sorted by Rank
        # Filters: must have buy recommendation (e.g. BOTTOM_OUT_STATUS == "Start GTT" or consensus buy)
        buy_signals = signals_df[
            (signals_df["BOTTOM_OUT_STATUS"].isin(["Start GTT", "Start GTT (Basic)"])) |
            (signals_df["TREND_STATUS"] == "In Bull Run")
        ].copy()

        if buy_signals.empty:
            return orders

        # Sort by Rank / Score descending
        if "COMPOSITE_SCORE" in buy_signals.columns:
            buy_signals = buy_signals.sort_values("COMPOSITE_SCORE", ascending=False)
        elif "RANK" in buy_signals.columns:
            buy_signals = buy_signals.sort_values("RANK", ascending=True)

        candidate_symbols = buy_signals["SYMBOL"].dropna().unique().tolist()
        current_active = list(portfolio.positions.keys())

        # Compute correlation mapping
        corr_matrix = self.calculate_correlations(candidate_symbols, current_active)

        for _, row in buy_signals.iterrows():
            sym = str(row["SYMBOL"])
            if sym in portfolio.positions:
                continue

            cmp = float(row.get("CMP", np.nan))
            atr = float(row.get("ATR_14", np.nan))
            sector = str(row.get("Sector", "Other"))

            if pd.isna(cmp) or pd.isna(atr) or cmp <= 0 or atr <= 0:
                continue

            # Apply correlation filter
            highly_correlated = False
            if sym in corr_matrix.columns:
                for active_sym in portfolio.positions:
                    if active_sym in corr_matrix.columns:
                        corr_val = corr_matrix.loc[sym, active_sym]
                        if corr_val > self.correlation_threshold:
                            highly_correlated = True
                            LOGGER.info("Skipping candidate %s: high correlation (%f) with active position %s", sym, corr_val, active_sym)
                            break

            if highly_correlated:
                continue

            # Calculate ATR sizing
            sizes = calculate_position_size(
                cmp=cmp,
                atr=atr,
                portfolio_size=portfolio.get_total_value(),
                risk_pct=0.01,  # 1% per trade risk
            )
            qty = sizes["suggested_qty"]
            value = qty * cmp

            if qty <= 0:
                continue

            # Check if portfolio constraints approve adding
            can_buy, reason = portfolio.can_add(sym, sector, cmp, value)
            if can_buy:
                target_price = sizes["risk_reward_target"]
                stop_price = sizes["stop_price"]
                
                portfolio.add_position(
                    symbol=sym,
                    qty=qty,
                    price=cmp,
                    stop_price=stop_price,
                    target_price=target_price,
                    sector=sector,
                    date_str=date_str,
                )
                orders.append({
                    "symbol": sym,
                    "action": "BUY",
                    "qty": qty,
                    "price": cmp,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "reason": f"Signal Approved: composite rank setup on {date_str}"
                })
            else:
                LOGGER.debug("Position %s rejected by portfolio: %s", sym, reason)

        return orders
