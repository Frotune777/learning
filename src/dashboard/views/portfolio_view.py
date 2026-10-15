"""
File: src/dashboard/views/portfolio_view.py
Purpose: Simulated Portfolio manager, exposure gauges & position sizing calculator.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.portfolio.portfolio_engine import Portfolio


def render_portfolio_view():
    st.markdown("""
    <div>
        <h2 style="margin:0; font-weight:800; color:#f8fafc;">💼 Portfolio Risk & Capital Management</h2>
        <p style="margin:4px 0 16px; color:#94a3b8; font-size:0.9rem;">
            Real-time simulated position sizing, sector limits, and capital exposure control.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if "portfolio_cash" not in st.session_state:
        st.session_state["portfolio_cash"] = 500_000.0
    if "portfolio_positions" not in st.session_state:
        st.session_state["portfolio_positions"] = []

    positions = st.session_state["portfolio_positions"]
    pos_df = pd.DataFrame(positions) if positions else pd.DataFrame()

    total_pos_val = (pos_df["qty"] * pos_df["current_price"]).sum() if not pos_df.empty else 0.0
    cash = st.session_state["portfolio_cash"]
    nav = cash + total_pos_val

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Total Portfolio Value (NAV)</div>
            <div class="pro-card-value">₹{nav:,.2f}</div>
            <div class="pro-card-sub">Cash + Open Value</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Available Cash</div>
            <div class="pro-card-value" style="color:#10b981;">₹{cash:,.2f}</div>
            <div class="pro-card-sub">Deployable liquidity</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Invested Capital</div>
            <div class="pro-card-value" style="color:#38bdf8;">₹{total_pos_val:,.2f}</div>
            <div class="pro-card-sub">{len(positions)} active allocations</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        exposure_pct = (total_pos_val / nav * 100) if nav > 0 else 0.0
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Capital Exposure</div>
            <div class="pro-card-value" style="color:#f59e0b;">{exposure_pct:.1f}%</div>
            <div class="pro-card-sub">Cap limit: 80%</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    col_tbl, col_add = st.columns([2.2, 1.2])
    with col_tbl:
        st.markdown("#### Open Portfolio Positions")
        if not pos_df.empty:
            st.dataframe(pos_df, use_container_width=True)
        else:
            st.info("No open simulated positions. Add positions using the Trade Panel on the right.")

    with col_add:
        st.markdown("#### Quick Allocation Entry")
        sym_input = st.text_input("Symbol", "RELIANCE")
        entry_p = st.number_input("Entry Price (₹)", value=2500.0, step=10.0)
        atr_input = st.number_input("ATR (₹)", value=40.0, step=1.0)
        risk_pct = st.slider("Risk Per Trade %", 0.5, 3.0, 1.0)

        risk_amt = nav * (risk_pct / 100.0)
        stop_dist = 1.5 * atr_input
        calc_qty = max(1, int(risk_amt / stop_dist))
        st.caption(f"Suggested Qty (1.5x ATR Stop): **{calc_qty} shares** (Required: ₹{calc_qty * entry_p:,.2f})")

        if st.button("Add to Simulated Portfolio", use_container_width=True, type="primary"):
            cost = calc_qty * entry_p
            if cost > cash:
                st.error("Insufficient cash in simulated account.")
            else:
                st.session_state["portfolio_cash"] -= cost
                st.session_state["portfolio_positions"].append({
                    "symbol": sym_input.upper(),
                    "qty": calc_qty,
                    "entry_price": entry_p,
                    "current_price": entry_p,
                    "stop_loss": round(entry_p - stop_dist, 2),
                    "target": round(entry_p + 3.0 * atr_input, 2),
                    "unrealized_pnl": 0.0
                })
                st.success(f"Added {calc_qty} shares of {sym_input.upper()}!")
                st.rerun()
