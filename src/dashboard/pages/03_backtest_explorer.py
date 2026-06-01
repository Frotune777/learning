import sys
import os
# Force project root into sys.path to resolve ModuleNotFoundError
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.." if os.path.basename(os.path.dirname(__file__)) == "dashboard" else "../../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

"""
File: src/dashboard/pages/03_backtest_explorer.py
Purpose: Streamlit dashboard page to configure and explore backtests on strategies.
Last Modified: 2026-06-01
"""

import glob
import os
import streamlit as st
import pandas as pd
import numpy as np

from src.nse_bhavcopy.ta_indicators import add_ta_indicators
from src.nse_bhavcopy.backtester import VectorBTBacktester, NSEEventBacktester

st.set_page_config(page_title="Backtest Explorer", page_icon="📉", layout="wide")

st.title("📉 Strategy Backtest Explorer")
st.markdown("---")

# 1. Discover historical data files
hist_dir = "data/historical/1d"
parquet_files = sorted(glob.glob(os.path.join(hist_dir, "*.parquet")))

if not parquet_files:
    st.error("No historical Parquet files found. Run sync-history or bhavcopy-sync in the CLI first.")
else:
    symbols = [os.path.basename(f).replace(".parquet", "") for f in parquet_files]

    # Sidebar parameters
    st.sidebar.subheader("Backtest Settings")
    symbol = st.sidebar.selectbox("Select Ticker Symbol", symbols)
    strategy = st.sidebar.selectbox("Select Strategy", [
        "Turtle Trading (55D Breakout)",
        "100 SMA Breakout",
        "RDX (ADX + DI + RSI)",
        "Nifty Shop (RSI Ladder)",
        "DMADMA Reverse (CMP > 200 > 150)"
    ])
    
    init_cash = st.sidebar.number_input("Initial Capital (INR)", min_value=1000.0, value=100000.0, step=10000.0)
    
    # Load and process price data
    p_path = os.path.join(hist_dir, f"{symbol}.parquet")
    df = pd.read_parquet(p_path)
    
    # Add TA indicators
    df = add_ta_indicators(df)
    
    st.subheader(f"Strategy Performance: {strategy} on {symbol}")
    
    # 2. Generate signals series (1 = Buy/Hold, 0 = Sell/Flat)
    signals = pd.Series(0, index=df.index)
    entries = pd.Series(False, index=df.index)
    exits = pd.Series(False, index=df.index)
    
    position = 0 # 0 = flat, 1 = long
    
    if strategy == "Turtle Trading (55D Breakout)":
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
            
    elif strategy == "100 SMA Breakout":
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
            
    elif strategy == "RDX (ADX + DI + RSI)":
        adx = df["ADX_14"]
        plus_di = df["PLUS_DI_14"]
        minus_di = df["MINUS_DI_14"]
        rsi = df["RSI_14"]
        
        for idx, row in df.iterrows():
            if position == 0 and adx.loc[idx] > 25.0 and plus_di.loc[idx] > minus_di.loc[idx] and rsi.loc[idx] > 60.0:
                position = 1
                entries.loc[idx] = True
            elif position == 1 and (plus_di.loc[idx] < minus_di.loc[idx] or rsi.loc[idx] < 45.0):
                position = 0
                exits.loc[idx] = True
            signals.loc[idx] = position
            
    elif strategy == "Nifty Shop (RSI Ladder)":
        rsi = df["RSI_14"]
        
        for idx, row in df.iterrows():
            if position == 0 and rsi.loc[idx] < 30.0:
                position = 1
                entries.loc[idx] = True
            elif position == 1 and rsi.loc[idx] > 50.0:
                position = 0
                exits.loc[idx] = True
            signals.loc[idx] = position
            
    elif strategy == "DMADMA Reverse (CMP > 200 > 150)":
        sma_150 = df["SMA_150"]
        sma_200 = df["SMA_200"]
        
        for idx, row in df.iterrows():
            close = row["Close"]
            if position == 0 and close > sma_200.loc[idx] and sma_200.loc[idx] > sma_150.loc[idx]:
                position = 1
                entries.loc[idx] = True
            elif position == 1 and close < sma_200.loc[idx]:
                position = 0
                exits.loc[idx] = True
            signals.loc[idx] = position

    # Run Backtests
    col_bt1, col_bt2 = st.columns(2)
    
    with col_bt1:
        st.subheader("🛒 Event-driven Backtest (NSE Rules)")
        event_tester = NSEEventBacktester(init_cash=init_cash)
        try:
            res_event = event_tester.run(df, signals)
            
            st.metric("Total Return", f"{res_event['total_return_pct']:.2f}%")
            st.metric("Max Drawdown", f"{res_event['max_drawdown_pct']:.2f}%")
            st.metric("Executed Trades", res_event["total_trades"])
            st.metric("Final Value", f"₹{res_event['final_value']:,.2f}")
            
            # Plot equity curve
            st.line_chart(res_event["history"]["Portfolio_Value"])
        except Exception as e:
            st.error(f"Event backtester failed: {e}")
            
    with col_bt2:
        st.subheader("⚡ Vectorized Backtest (VectorBT)")
        try:
            res_vbt = VectorBTBacktester.run_backtest(df["Close"], entries, exits, init_cash=init_cash)
            
            st.metric("Total Return", f"{res_vbt['total_return_pct']:.2f}%")
            st.metric("Max Drawdown", f"{res_vbt['max_drawdown_pct']:.2f}%")
            st.metric("Executed Trades", res_vbt["total_trades"])
            st.metric("Final Value", f"₹{res_vbt['final_value']:,.2f}")
        except Exception as e:
            st.error(f"VectorBT backtester failed: {e}")
