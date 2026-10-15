"""
File: src/dashboard/views/backtest_view.py
Purpose: Event-driven & VectorBT strategy backtesting workbench.
"""

from __future__ import annotations
import os
import glob
import pandas as pd
import streamlit as st
import plotly.express as px

from src.nse_bhavcopy.backtester import NSEEventBacktester, VectorBTBacktester
from src.nse_bhavcopy.ta_indicators import add_ta_indicators


def render_backtest_view():
    st.markdown("""
    <div>
        <h2 style="margin:0; font-weight:800; color:#f8fafc;">📉 Strategy Backtesting & Quantitative Validation</h2>
        <p style="margin:4px 0 16px; color:#94a3b8; font-size:0.9rem;">
            Simulate historical trade executions, win-rates, Sharpe ratios, and max drawdown curves using realistic NSE T+1 settlement and transaction costs.
        </p>
    </div>
    """, unsafe_allow_html=True)

    hist_dir = "data/historical/1d"
    parquet_files = sorted(glob.glob(os.path.join(hist_dir, "*.parquet")))

    if not parquet_files:
        st.error("No historical Parquet files found in data/historical/1d.")
        return

    symbols = [os.path.basename(f).replace(".parquet", "") for f in parquet_files]

    c_sym, c_strat, c_capital = st.columns(3)
    with c_sym:
        sel_symbol = st.selectbox("Ticker Symbol", symbols, index=symbols.index("RELIANCE") if "RELIANCE" in symbols else 0)
    with c_strat:
        sel_strat = st.selectbox(
            "Strategy Rule",
            [
                "Turtle Trading (55D Breakout)",
                "100 SMA Breakout",
                "RDX (ADX + DI + RSI)",
                "Nifty Shop (RSI Ladder)",
                "DMADMA Reverse (CMP > 200 > 150)",
            ]
        )
    with c_capital:
        initial_cap = st.number_input("Starting Capital (₹)", value=100000.0, step=10000.0)

    if st.button("Run Quantitative Backtest", use_container_width=True, type="primary"):
        p_path = os.path.join(hist_dir, f"{sel_symbol}.parquet")
        df = pd.read_parquet(p_path)

        # Standardize columns to capitalized Open, High, Low, Close, Volume if needed
        cols_map = {}
        for c in df.columns:
            cl = c.lower()
            if cl == "open":
                cols_map[c] = "Open"
            elif cl == "high":
                cols_map[c] = "High"
            elif cl == "low":
                cols_map[c] = "Low"
            elif cl == "close":
                cols_map[c] = "Close"
            elif cl == "volume":
                cols_map[c] = "Volume"
        if cols_map:
            df = df.rename(columns=cols_map)

        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")

        df = df.sort_index()

        # Compute TA indicators required for strategies
        df = add_ta_indicators(df)

        # Generate signals series (1 = Buy/Hold, 0 = Sell/Flat)
        signals = pd.Series(0, index=df.index)
        entries = pd.Series(False, index=df.index)
        exits = pd.Series(False, index=df.index)
        position = 0

        if sel_strat == "Turtle Trading (55D Breakout)":
            high_55_prev = df["55D_HIGH"].shift(1)
            low_20 = df["20D_LOW"]
            for idx, row in df.iterrows():
                close = row["Close"]
                prev_high = high_55_prev.loc[idx]
                if position == 0 and not pd.isna(prev_high) and close >= prev_high:
                    position = 1
                    entries.loc[idx] = True
                elif position == 1 and close <= low_20.loc[idx]:
                    position = 0
                    exits.loc[idx] = True
                signals.loc[idx] = position

        elif sel_strat == "100 SMA Breakout":
            sma_100 = df["SMA_100"]
            for idx, row in df.iterrows():
                close = row["Close"]
                if position == 0 and close > sma_100.loc[idx]:
                    position = 1
                    entries.loc[idx] = True
                elif position == 1 and close < sma_100.loc[idx]:
                    position = 0
                    exits.loc[idx] = True
                signals.loc[idx] = position

        elif sel_strat == "RDX (ADX + DI + RSI)":
            adx = df["ADX_14"]
            plus_di = df["PLUS_DI_14"]
            minus_di = df["MINUS_DI_14"]
            rsi = df["RSI_14"]
            for idx, row in df.iterrows():
                if (
                    position == 0
                    and adx.loc[idx] > 25.0
                    and plus_di.loc[idx] > minus_di.loc[idx]
                    and rsi.loc[idx] > 60.0
                ):
                    position = 1
                    entries.loc[idx] = True
                elif position == 1 and (
                    plus_di.loc[idx] < minus_di.loc[idx] or rsi.loc[idx] < 45.0
                ):
                    position = 0
                    exits.loc[idx] = True
                signals.loc[idx] = position

        elif sel_strat == "Nifty Shop (RSI Ladder)":
            rsi = df["RSI_14"]
            for idx, row in df.iterrows():
                if position == 0 and rsi.loc[idx] < 30.0:
                    position = 1
                    entries.loc[idx] = True
                elif position == 1 and rsi.loc[idx] > 50.0:
                    position = 0
                    exits.loc[idx] = True
                signals.loc[idx] = position

        elif sel_strat == "DMADMA Reverse (CMP > 200 > 150)":
            sma_150 = df["SMA_150"]
            sma_200 = df["SMA_200"]
            for idx, row in df.iterrows():
                close = row["Close"]
                if (
                    position == 0
                    and close > sma_200.loc[idx]
                    and sma_200.loc[idx] > sma_150.loc[idx]
                ):
                    position = 1
                    entries.loc[idx] = True
                elif position == 1 and close < sma_200.loc[idx]:
                    position = 0
                    exits.loc[idx] = True
                signals.loc[idx] = position

        # Run Backtest with correct argument `init_cash`
        backtester = NSEEventBacktester(init_cash=float(initial_cap))
        try:
            res_event = backtester.run(df, signals)

            st.markdown("<div class='section-hdr'><h3>Backtest Performance Scorecard</h3><div class='line'></div></div>", unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Total Return", f"{res_event['total_return_pct']:+.2f}%")
            with m2:
                st.metric("Max Drawdown", f"{res_event['max_drawdown_pct']:.2f}%")
            with m3:
                st.metric("Executed Trades", res_event["total_trades"])
            with m4:
                st.metric("Final Value", f"₹{res_event['final_value']:,.2f}")

            # Plot interactive equity curve
            hist_df = res_event["history"]
            if not hist_df.empty:
                st.markdown("#### Portfolio Equity Curve (NSE Simulation)")
                fig = px.line(
                    hist_df,
                    y="Portfolio_Value",
                    title=f"{sel_strat} Equity Curve on {sel_symbol}",
                    template="plotly_dark",
                )
                fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("#### Trade & Settlement Ledger")
                trades_only = hist_df[hist_df["Trade_Action"].isin(["BUY", "SELL", "LC_REJECT", "UC_REJECT"])]
                if not trades_only.empty:
                    st.dataframe(trades_only[["Close", "Trade_Action", "Shares", "Trade_Cost", "Available_Cash", "Portfolio_Value"]], use_container_width=True)
                else:
                    st.info("No trades triggered over this timeframe.")
        except Exception as e:
            st.error(f"Backtest execution failed: {e}")
