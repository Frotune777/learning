"""
File: src/classes/PaperTrading.py
Purpose: Simulate stock trades with hypothetical capital for training and strategy testing.

Dependencies:
External:
- None
Internal:
- None

Key Components:
Classes:
- PaperTrading: Manages hypothetical portfolio, positions, and trade history

Functions:
- None

Last Modified: 2026-02-19
Modified By: LLM

Open Tasks:
- [ ] [MEDIUM] Implement persistence for paper trading state
- [ ] [LOW] Add support for multiple concurrent portfolios
"""

from datetime import datetime
from typing import Any

from src.utils.SignalBus import SignalEmitter


class PaperTrading(SignalEmitter):
    """
    Simple paper trading engine for simulating buys and sells.

    Design Pattern: State Pattern - maintains the state of a hypothetical portfolio.

    Attributes:
        capital (float): Remaining hypothetical cash.
        positions (Dict): Open positions mapping symbol to shares and average price.
        trades (List): History of executed trades.
    """

    def __init__(self, initial_capital: float = 100000.0) -> None:
        """
        Initialize portfolio with starting capital.

        Args:
            initial_capital (float): Starting balance.
        """
        SignalEmitter.__init__(self)
        self.capital = initial_capital
        self.positions: dict[str, dict[str, Any]] = {}
        self.trades: list[dict[str, Any]] = []

    def buy(
        self,
        symbol: str,
        price: float,
        shares: int | None = None,
        value: float | None = None,
    ) -> tuple[bool, str]:
        """
        Execute a hypothetical buy order.

        Args:
            symbol (str): Stock symbol.
            price (float): Execution price.
            shares (int, optional): Number of shares to buy.
            value (float, optional): Total capital to allocate for this buy.

        Returns:
            Tuple[bool, str]: (Success, Message)
        """
        if shares is None and value is None:
            return False, "Must specify either shares or value"

        if shares is None:
            if value is None:
                return False, "Must specify either shares or value"
            shares = int(value / price)

        cost = shares * price
        if cost > self.capital:
            return (
                False,
                f"Insufficient funds (Needed: ₹{cost:,.2f}, Available: ₹{self.capital:,.2f})",
            )

        self.capital -= cost

        if symbol in self.positions:
            # Average up/down
            total_shares = self.positions[symbol]["shares"] + shares
            total_cost = (
                self.positions[symbol]["shares"] * self.positions[symbol]["entry"]
            ) + cost
            self.positions[symbol]["entry"] = total_cost / total_shares
            self.positions[symbol]["shares"] = total_shares
        else:
            self.positions[symbol] = {"shares": shares, "entry": price}

        trade = {
            "type": "BUY",
            "symbol": symbol,
            "shares": shares,
            "price": price,
            "total": cost,
        }
        self.trades.append(trade)

        # Emit trade event to analytics
        self.emit_trade(
            {
                "symbol": symbol,
                "entry_price": price,
                "position_size": shares,
                "entry_time": datetime.now().isoformat(),
            }
        )

        return True, f"✅ Bought {shares} shares of {symbol} at ₹{price:,.2f}"

    def sell(
        self, symbol: str, price: float, shares: int | None = None
    ) -> tuple[bool, str]:
        """
        Execute a hypothetical sell order.

        Args:
            symbol (str): Stock symbol.
            price (float): Execution price.
            shares (int, optional): Number of shares to sell (default all).

        Returns:
            Tuple[bool, str]: (Success, Message)
        """
        if symbol not in self.positions:
            return False, f"No open position in {symbol}"

        pos = self.positions[symbol]
        if shares is None:
            shares = pos["shares"]

        if shares > pos["shares"]:
            return (
                False,
                f"Not enough shares (Requested: {shares}, Owned: {pos['shares']})",
            )

        proceeds = shares * price
        pnl = (price - pos["entry"]) * shares
        self.capital += proceeds

        pos["shares"] -= shares
        if pos["shares"] == 0:
            del self.positions[symbol]

        trade = {
            "type": "SELL",
            "symbol": symbol,
            "shares": shares,
            "price": price,
            "total": proceeds,
            "pnl": pnl,
        }
        self.trades.append(trade)
        return (
            True,
            f"✅ Sold {shares} shares of {symbol} at ₹{price:,.2f}. P&L: ₹{pnl:,.2f}",
        )

    def get_summary(self) -> dict[str, Any]:
        """
        Get current portfolio summary.

        Returns:
            Dict: Summary including total value, P&L, and open positions.
        """
        return {
            "cash": self.capital,
            "positions_count": len(self.positions),
            "trades_count": len(self.trades),
            "positions": self.positions,
        }
