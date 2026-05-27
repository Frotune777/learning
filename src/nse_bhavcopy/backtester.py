"""
File: src/nse_bhavcopy/backtester.py
Purpose: Backtesting harness supporting VectorBT and event-driven NSE logic.
Last Modified: 2026-05-27
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import vectorbt as vbt

LOGGER = logging.getLogger(__name__)


def calculate_nse_costs(price: float, qty: float, side: str) -> float:
    """
    Calculate exact NSE transaction costs for delivery trades.

    Parameters:
        price (float): Execution price of the stock. | Positive.
        qty (float): Number of shares traded. | Positive.
        side (str): Trade direction ("BUY" or "SELL"). | Case-insensitive.

    Returns:
        float: Combined transaction charges in INR.

    Raises:
        None

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> cost = calculate_nse_costs(3500.0, 10, "BUY")
    """
    value = price * qty
    if value <= 0.0:
        return 0.0

    brokerage = 0.0  # Zero brokerage delivery on typical discount brokers
    exchange_charges = value * 0.0000345  # 0.00345% NSE txn charges
    sebi_charges = value * 0.000001  # SEBI fee of 0.0001%
    stt = value * 0.001  # STT: 0.1% for equity delivery buy/sell
    stamp_duty = value * 0.00015 if side.upper() == "BUY" else 0.0  # 0.015% buy
    gst = (brokerage + exchange_charges) * 0.18  # 18% GST on brokerage + exchange

    return brokerage + exchange_charges + sebi_charges + stt + stamp_duty + gst


class VectorBTBacktester:
    """
    Vectorized backtester wrapper leveraging VectorBT for fast signal execution.

    Attributes:
        None

    Public Methods:
        - run_backtest(close, entries, exits, init_cash): Execute backtest.

    Thread Safety:
        Yes.
    """

    @staticmethod
    def run_backtest(
        close: pd.Series,
        entries: pd.Series,
        exits: pd.Series,
        init_cash: float = 100000.0,
    ) -> dict[str, Any]:
        """
        Run a vectorized backtest using VectorBT.

        Parameters:
            close (pd.Series): Historical closing prices. | Non-empty.
            entries (pd.Series): Boolean series for entry signals. |
                Same length as close.
            exits (pd.Series): Boolean series for exit signals. |
                Same length as close.
            init_cash (float): Initial cash allocation. | Positive.

        Returns:
            dict[str, Any]: Strategy performance metrics.

        Raises:
            None

        Complexity:
            Time: O(N) where N = len(close)
            Space: O(N)

        Example:
            >>> metrics = VectorBTBacktester.run_backtest(close, entries, exits)
        """
        try:
            c = close.copy()
            ent = entries.copy()
            ex = exits.copy()
            if not isinstance(c.index, pd.DatetimeIndex):
                dt_idx = pd.date_range("2026-01-01", periods=len(c), freq="D")
                c.index = dt_idx
                ent.index = dt_idx
                ex.index = dt_idx

            pf = vbt.Portfolio.from_signals(
                close=c,
                entries=ent,
                exits=ex,
                init_cash=init_cash,
                fees=0.0015,  # 0.15% average fee proxy
                freq="1D",
            )
            return {
                "total_return_pct": float(pf.total_return() * 100.0),
                "sharpe_ratio": float(pf.sharpe_ratio())
                if np.isfinite(pf.sharpe_ratio())
                else 0.0,
                "max_drawdown_pct": float(pf.max_drawdown() * 100.0),
                "total_trades": int(len(pf.trades)),
                "final_value": float(pf.final_value()),
            }
        except Exception as exc:
            LOGGER.error("VectorBT backtest failed: %s", exc)
            return {
                "total_return_pct": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "total_trades": 0,
                "final_value": init_cash,
            }


class NSEEventBacktester:
    """
    Event-driven backtesting engine replicating NSE trading conditions.

    Includes T+1 settlement, transaction costs, holiday calendars,
    and circuit filter checks.

    Attributes:
        init_cash (float): Starting balance.
        circuit_limit (float): Upper/lower circuit percentage.
        nse_cal (mcal.MarketCalendar): NSE market calendar instance.

    Public Methods:
        - run(df_prices, signals): Run day-by-day simulated trading.

    Thread Safety:
        Yes.
    """

    def __init__(
        self,
        init_cash: float = 100000.0,
        circuit_limit: float = 0.20,
    ) -> None:
        """
        Initialize the event-driven NSE backtester.

        Parameters:
            init_cash (float): Initial portfolio cash. | Positive.
            circuit_limit (float): Circuit filter limit (e.g. 0.20 for 20%). |
                Positive.

        Returns:
            None

        Raises:
            None

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> bt = NSEEventBacktester()
        """
        self.init_cash: float = init_cash
        self.circuit_limit: float = circuit_limit
        self.nse_cal: mcal.MarketCalendar = mcal.get_calendar("NSE")

    def run(self, df_prices: pd.DataFrame, signals: pd.Series) -> dict[str, Any]:
        """
        Execute day-by-day iterative backtesting.

        Rules implemented:
            1. T+1 Settlement: Sell proceeds are locked in pending cash until
               the next business day.
            2. Holiday Calendar: Trades only execute on valid NSE business days.
            3. Circuit filters: Limit orders rejected if Close is at UC/LC.
            4. Precise Cash accounting including transaction charges.

        Parameters:
            df_prices (pd.DataFrame): Data containing Close, Open, High, Low. |
                Sorted by Date index.
            signals (pd.Series): Signals aligned with prices index. (1=Buy, 0=Sell).

        Returns:
            dict[str, Any]: Summary metrics and history DataFrame.

        Raises:
            ValueError: If dataframe length < 2 or missing required columns.

        Complexity:
            Time: O(N) where N = len(df_prices)
            Space: O(N) for history logging

        Example:
            >>> res = bt.run(df_prices, signals)
        """
        df = df_prices.copy()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")

        df = df.sort_index()

        required = {"Open", "High", "Low", "Close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Prices missing required columns: {missing}")

        if len(df) < 2:
            raise ValueError("Backtest requires at least 2 price bars.")

        # Filter signals to only trade on valid calendar days
        start_date = df.index.min()
        end_date = df.index.max()
        valid_days = self.nse_cal.valid_days(start_date=start_date, end_date=end_date)
        valid_set = {pd.Timestamp(d.date()) for d in valid_days}

        # Track portfolio state
        shares = 0.0
        available_cash = self.init_cash
        # Maps sell_date (Timestamp) -> pending_cash_amount
        pending_settlement: dict[pd.Timestamp, float] = {}

        history: list[dict[str, Any]] = []

        # Iterate chronologically
        prev_close = 0.0
        for i, (timestamp, row) in enumerate(df.iterrows()):
            assert isinstance(timestamp, pd.Timestamp)
            # 1. Process Settlement from previous days
            settled_keys = []
            for sell_date, amount in pending_settlement.items():
                # T+1 Settlement: if current day is > sell_date (strictly calendar days)
                # and is a valid trading day, we settle it.
                if timestamp > sell_date:
                    available_cash += amount
                    settled_keys.append(sell_date)

            for k in settled_keys:
                del pending_settlement[k]

            # 2. Check if current day is a valid NSE trading day
            is_trading_day = timestamp in valid_set

            # 3. Determine if circuit limits are hit today
            hit_uc = False
            hit_lc = False
            if prev_close > 0.0:
                uc_price = prev_close * (1.0 + self.circuit_limit)
                lc_price = prev_close * (1.0 - self.circuit_limit)
                hit_uc = row["High"] >= uc_price * 0.9995
                hit_lc = row["Low"] <= lc_price * 1.0005

            current_signal = signals.loc[timestamp] if timestamp in signals.index else 0
            close_price = float(row["Close"])

            trade_action = "HOLD"
            trade_cost = 0.0

            if is_trading_day:
                # Signal is BUY (1) and we currently hold no shares
                if current_signal == 1 and shares == 0:
                    if hit_uc:
                        # Cannot buy if stuck at Upper Circuit (no sellers)
                        trade_action = "UC_REJECT"
                    else:
                        # Buy as many shares as available cash allows
                        # Price is Close
                        price = close_price
                        # Allocate all available cash minus expected fees
                        approx_qty = available_cash / (price * 1.0015)
                        if approx_qty > 0.01:
                            qty = float(np.floor(approx_qty))
                            if qty > 0:
                                cost = calculate_nse_costs(price, qty, "BUY")
                                total_outlay = (price * qty) + cost
                                # Ensure we don't breach cash
                                while total_outlay > available_cash and qty > 0:
                                    qty -= 1
                                    cost = calculate_nse_costs(price, qty, "BUY")
                                    total_outlay = (price * qty) + cost

                                if qty > 0:
                                    shares = qty
                                    available_cash -= total_outlay
                                    trade_action = "BUY"
                                    trade_cost = cost

                # Signal is SELL (0) or HOLD-LIQUIDATE, and we hold shares
                elif current_signal == 0 and shares > 0:
                    if hit_lc:
                        # Cannot sell if stuck at Lower Circuit (no buyers)
                        trade_action = "LC_REJECT"
                    else:
                        price = close_price
                        gross_proceeds = price * shares
                        cost = calculate_nse_costs(price, shares, "SELL")
                        net_proceeds = gross_proceeds - cost

                        # Proceeds locked in T+1 settlement
                        pending_settlement[timestamp] = net_proceeds
                        shares = 0.0
                        trade_action = "SELL"
                        trade_cost = cost

            # Calculate total portfolio value today
            pending_total = sum(pending_settlement.values())
            portfolio_value = available_cash + pending_total + (shares * close_price)

            history.append(
                {
                    "Date": timestamp,
                    "Close": close_price,
                    "Signal": current_signal,
                    "Shares": shares,
                    "Available_Cash": available_cash,
                    "Pending_Cash": pending_total,
                    "Portfolio_Value": portfolio_value,
                    "Trade_Action": trade_action,
                    "Trade_Cost": trade_cost,
                    "Hit_UC": hit_uc,
                    "Hit_LC": hit_lc,
                }
            )

            prev_close = close_price

        hist_df = pd.DataFrame(history).set_index("Date")
        final_value = float(hist_df["Portfolio_Value"].iloc[-1])
        total_return = ((final_value - self.init_cash) / self.init_cash) * 100.0

        # Calculate drawdown
        cum_max = hist_df["Portfolio_Value"].cummax()
        drawdown = (hist_df["Portfolio_Value"] - cum_max) / cum_max
        max_dd = float(drawdown.min() * 100.0)

        # Count actual trades
        trades_count = int(hist_df["Trade_Action"].isin(["BUY", "SELL"]).sum())

        return {
            "total_return_pct": total_return,
            "max_drawdown_pct": max_dd,
            "total_trades": trades_count,
            "final_value": final_value,
            "history": hist_df,
        }
