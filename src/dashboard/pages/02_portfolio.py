import sys
import os
# Force project root into sys.path to resolve ModuleNotFoundError
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.." if os.path.basename(os.path.dirname(__file__)) == "dashboard" else "../../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

"""
File: src/dashboard/pages/02_portfolio.py
Purpose: Renders simulated active holdings, cash metrics, and risk exposures.
Last Modified: 2026-06-01
"""

import streamlit as st
import pandas as pd
import numpy as np

from src.portfolio.portfolio_engine import Portfolio

st.set_page_config(page_title="Simulated Portfolio", page_icon="💼", layout="wide")

st.title("💼 Simulated Portfolio Manager")
st.markdown("---")

# Initialise state
if "portfolio_cash" not in st.session_state:
    st.session_state["portfolio_cash"] = 500_000.0
if "portfolio_positions" not in st.session_state:
    st.session_state["portfolio_positions"] = {}

# Load portfolio engine wrapper
port = Portfolio(initial_cash=st.session_state["portfolio_cash"])
port.positions = st.session_state["portfolio_positions"]

# Summary cards
total_val = port.get_total_value()
pnl_tot = total_val - port.initial_cash
pnl_pct = (pnl_tot / port.initial_cash) * 100.0 if port.initial_cash > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Account Value", f"₹{total_val:,.2f}")
col2.metric("Available Cash", f"₹{port.cash:,.2f}")
col3.metric("Total Profit / Loss", f"₹{pnl_tot:,.2f}", f"{pnl_pct:+.2f}%")
col4.metric("Risk Heat (VAR)", f"{port.get_heat():.2%}")

st.markdown("---")

# Holdings Table
st.subheader("📦 Active Positions")
pos_df = port.to_dataframe()

if pos_df.empty:
    st.info("No active simulated holdings. Visit the Daily Signals page to buy stocks.")
else:
    # Display table
    st.dataframe(pos_df, use_container_width=True)
    
    # Sell/Close positions
    st.subheader("Exit Position")
    exit_col1, exit_col2 = st.columns(2)
    with exit_col1:
        exit_sym = st.selectbox("Select Position to Exit", list(port.positions.keys()))
    with exit_col2:
        curr_pos = port.positions[exit_sym]
        exit_price = st.number_input("Exit Price (INR)", value=float(curr_pos["current_price"]))
        if st.button("Execute Sell"):
            port.exit_position(exit_sym, exit_price)
            # Update session state
            st.session_state["portfolio_cash"] = port.cash
            st.session_state["portfolio_positions"] = port.positions
            st.success(f"Successfully closed position in {exit_sym}!")
            st.rerun()

# Sector allocation visualization
st.markdown("---")
st.subheader("🍕 Sector Allocation Limits")

sectors = port.get_sector_exposure_percentages()
if sectors:
    # Convert dict to DataFrame for plotting
    sec_df = pd.DataFrame(list(sectors.items()), columns=["Sector", "Allocation %"])
    sec_df["Allocation %"] = sec_df["Allocation %"] * 100.0
    
    col_chart, col_limits = st.columns(2)
    with col_chart:
        st.bar_chart(sec_df.set_index("Sector"))
    with col_limits:
        st.write("**Exposure Guidelines:**")
        st.write("- Maximum exposure per sector: **25.0%**")
        st.write("- Maximum allocation per position: **10.0%**")
        for sect, val in sectors.items():
            if val > port.max_sector_exposure_pct:
                st.error(f"⚠️ Sector **{sect}** ({val:.1%}) breaches the 25% exposure limit!")
            else:
                st.success(f"✔ Sector **{sect}** ({val:.1%}) is within safety limits.")
else:
    st.info("No allocations to show. Buy assets to display sector breakdowns.")
