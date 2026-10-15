"""
File: src/dashboard/pages/06_smc_calls.py
Purpose: Interactive SMC Analysis, Trading Decision Workspace, and CRUD UI.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.engine.smc import calculate_smc
from src.engine.smc_decision import generate_smc_call
from src.storage.smc_db import SMCDatabase

try:
    st.set_page_config(page_title="SMC Decision Hub", layout="wide")
except Exception:
    pass

db = SMCDatabase()

st.title("🎯 Smart Money Concepts (SMC) Decision Terminal")

# Top Metrics Row
calls_all = db.get_calls()
df_calls = pd.DataFrame(calls_all) if calls_all else pd.DataFrame()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Generated Setups", len(df_calls))
with col2:
    pending_count = len(df_calls[df_calls["status"] == "PENDING"]) if not df_calls.empty else 0
    st.metric("Pending Confirmations", pending_count)
with col3:
    active_count = len(df_calls[df_calls["status"] == "TRIGGERED"]) if not df_calls.empty else 0
    st.metric("Active Live Calls", active_count)
with col4:
    avg_rr = f"{df_calls['risk_reward'].mean():.2f}" if not df_calls.empty else "0.00"
    st.metric("Average R:R", avg_rr)

st.markdown("---")

left_col, center_col, right_col = st.columns([1, 2.2, 1.2])

# ===========================================================================
# 1. LEFT PANE: CALL QUEUE
# ===========================================================================
with left_col:
    st.subheader("Actionable Setups")
    status_filter = st.selectbox("Filter Status", ["ALL", "PENDING", "TRIGGERED", "STOPPED", "TARGET_HIT"])
    
    filtered_calls = db.get_calls(status=None if status_filter == "ALL" else status_filter)
    
    selected_call = None
    if filtered_calls:
        call_labels = [f"#{c['id']} {c['symbol']} ({c['direction']}) - {c['setup_type']}" for c in filtered_calls]
        selected_label = st.radio("Select Call to Inspect", call_labels, label_visibility="collapsed")
        selected_id = int(selected_label.split(" ")[0].replace("#", ""))
        selected_call = next(c for c in filtered_calls if c["id"] == selected_id)
    else:
        st.info("No calls in this status.")

# ===========================================================================
# 2. CENTER PANE: SMC CHART
# ===========================================================================
with center_col:
    st.subheader("SMC Price Geometry")
    if selected_call:
        sym = selected_call["symbol"]
        parquet_path = Path("data/historical/1d") / f"{sym}.parquet"
        
        if parquet_path.exists():
            df_hist = pd.read_parquet(parquet_path).tail(120)
            df_hist.columns = [c.lower() for c in df_hist.columns]
            
            # Run SMC overlay
            smc_res = calculate_smc(df_hist, swing_length=15, internal_length=5)

            # Optional LuxAlgo Overlays
            c_tog1, c_tog2 = st.columns(2)
            with c_tog1:
                show_nwe = st.checkbox("Overlay Nadaraya-Watson Envelope", value=True)
            with c_tog2:
                show_vp = st.checkbox("Overlay Volume Profile (POC/VAH/VAL)", value=True)

            fig = go.Figure(data=[go.Candlestick(
                x=df_hist.index,
                open=df_hist['open'],
                high=df_hist['high'],
                low=df_hist['low'],
                close=df_hist['close'],
                name=sym
            )])

            # 1. Nadaraya-Watson Envelope overlay
            if show_nwe:
                from src.engine.lux_nwe import calculate_nwe
                nwe_res = calculate_nwe(df_hist, bandwidth=8.0, multiplier=2.5)
                nwe_df = nwe_res.to_pandas()
                fig.add_trace(go.Scatter(x=df_hist.index, y=nwe_df['nwe_upper'], mode='lines', line=dict(color='rgba(242,54,69,0.7)', width=1), name='NWE Upper'))
                fig.add_trace(go.Scatter(x=df_hist.index, y=nwe_df['nwe_lower'], mode='lines', line=dict(color='rgba(8,153,129,0.7)', width=1), name='NWE Lower'))
                fig.add_trace(go.Scatter(x=df_hist.index, y=nwe_df['nwe'], mode='lines', line=dict(color='rgba(120,123,134,0.5)', width=1, dash='dot'), name='NWE Kernel'))

            # 2. Volume Profile Levels (POC, VAH, VAL)
            if show_vp:
                from src.engine.lux_volume_profile import calculate_volume_profile
                vp_res = calculate_volume_profile(df_hist, lookback=len(df_hist))
                fig.add_hline(y=vp_res.poc_price, line_dash="solid", line_color="#ff9800", annotation_text=f"POC {vp_res.poc_price}")
                fig.add_hline(y=vp_res.vah_price, line_dash="dot", line_color="#5b9cf6", annotation_text=f"VAH {vp_res.vah_price}")
                fig.add_hline(y=vp_res.val_price, line_dash="dot", line_color="#5b9cf6", annotation_text=f"VAL {vp_res.val_price}")

            # Entry / SL / TP markers
            fig.add_hline(y=selected_call['entry_price'], line_dash="dash", line_color="cyan", annotation_text="ENTRY")
            fig.add_hline(y=selected_call['stop_loss'], line_dash="dash", line_color="red", annotation_text="SL")
            fig.add_hline(y=selected_call['target_1'], line_dash="dash", line_color="green", annotation_text="TP1")

            # Premium / Discount zones
            if not pd.isna(smc_res.equilibrium_level):
                fig.add_hline(y=smc_res.equilibrium_level, line_dash="dot", line_color="grey", annotation_text="EQ (50%)")

            fig.update_layout(height=520, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No parquet found for {sym}")
    else:
        st.info("Select a trading call on the left to load chart geometry.")

# ===========================================================================
# 3. RIGHT PANE: TRADE EXECUTION & CRUD
# ===========================================================================
with right_col:
    st.subheader("Call Execution Card")
    if selected_call:
        cid = selected_call["id"]
        dir_color = "🟢" if selected_call["direction"] == "BUY" else "🔴"
        st.markdown(f"### {dir_color} {selected_call['symbol']} - {selected_call['direction']}")
        st.markdown(f"**Setup:** `{selected_call['setup_type']}`")
        st.markdown(f"**Entry:** ₹{selected_call['entry_price']:.2f}")
        st.markdown(f"**Stop Loss:** ₹{selected_call['stop_loss']:.2f}")
        st.markdown(f"**Target 1:** ₹{selected_call['target_1']:.2f} | **Target 2:** ₹{selected_call['target_2']:.2f}")
        st.markdown(f"**Risk/Reward:** `{selected_call['risk_reward']:.2f}`")
        
        # Position Sizing Helper
        st.markdown("#### Position Calculator")
        user_risk = st.number_input("Max Risk (INR)", min_value=500, max_value=100000, value=5000, step=500)
        risk_per_share = abs(selected_call['entry_price'] - selected_call['stop_loss'])
        calc_qty = int(user_risk / risk_per_share) if risk_per_share > 0 else 0
        st.info(f"**Allocated Quantity:** {calc_qty} shares (Capital Required: ₹{calc_qty * selected_call['entry_price']:,.2f})")
        
        st.markdown("#### Lifecycle CRUD")
        c_status = selected_call["status"]
        st.write(f"Current State: `{c_status}`")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Mark Triggered", use_container_width=True):
                db.update_status(cid, "TRIGGERED", "Manually triggered from GUI")
                st.rerun()
            if st.button("Hit Target 1", use_container_width=True):
                db.update_status(cid, "TARGET_HIT", "Target 1 reached, move SL to breakeven")
                st.rerun()
        with col_btn2:
            if st.button("Stopped Out", use_container_width=True):
                db.update_status(cid, "STOPPED", "Stop loss triggered")
                st.rerun()
            if st.button("Delete Call", use_container_width=True):
                db.delete_call(cid)
                st.rerun()
    else:
        st.info("Pick an opportunity to view execution parameters.")

# ===========================================================================
# 4. BOTTOM DRAWER: SQL DATABASE LEDGER
# ===========================================================================
st.markdown("---")
st.subheader("Transaction Ledger (`smc_calls.sqlite`)")
if not df_calls.empty:
    st.dataframe(df_calls, use_container_width=True, hide_index=True)
else:
    st.caption("No records present in the local database.")