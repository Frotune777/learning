"""
File: src/dashboard/views/portfolio_view.py
Purpose: Simulated Portfolio manager, exposure gauges, sector allocation charts & position sizing calculator.
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

    st.session_state.setdefault("portfolio_cash", 500_000.0)
    # Ensure canonical dict schema: {SYMBOL: {pos_details}}
    if not isinstance(st.session_state.get("portfolio_positions"), dict):
        st.session_state["portfolio_positions"] = {}

    cash = float(st.session_state["portfolio_cash"])
    port = Portfolio(initial_cash=cash)
    port.cash = cash
    port.positions = st.session_state["portfolio_positions"]

    pos_df = port.to_dataframe()
    nav = port.get_total_value()
    total_pos_val = nav - port.cash

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Total Portfolio Value (NAV)</div>
            <div class="pro-card-value">₹{nav:,.2f}</div>
            <div class="pro-card-sub">Cash + Open Market Value</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Available Cash</div>
            <div class="pro-card-value" style="color:#10b981;">₹{port.cash:,.2f}</div>
            <div class="pro-card-sub">Deployable liquidity</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Invested Capital</div>
            <div class="pro-card-value" style="color:#38bdf8;">₹{total_pos_val:,.2f}</div>
            <div class="pro-card-sub">{len(port.positions)} active allocations</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        exposure_pct = (total_pos_val / nav * 100) if nav > 0 else 0.0
        heat_pct = port.get_heat() * 100
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Capital Exposure / Heat</div>
            <div class="pro-card-value" style="color:#f59e0b;">{exposure_pct:.1f}%</div>
            <div class="pro-card-sub">Risk Heat: {heat_pct:.1f}% (Cap: 80%)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    col_tbl, col_add = st.columns([2.2, 1.2])
    with col_tbl:
        st.markdown("#### Open Portfolio Positions")
        if not pos_df.empty:
            st.dataframe(pos_df, use_container_width=True)

            # Exit Position controls
            st.markdown("---")
            st.markdown("#### Exit / Liquidate Position")
            col_ex_sym, col_ex_p, col_ex_btn = st.columns([1.5, 1.5, 1])
            with col_ex_sym:
                exit_sym = st.selectbox("Select Position to Exit", list(port.positions.keys()))
            with col_ex_p:
                curr_price = float(port.positions[exit_sym].get("current_price", 0.0))
                exit_price = st.number_input("Exit Price (₹)", value=curr_price, step=10.0)
            with col_ex_btn:
                st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
                if st.button("Execute Sell", use_container_width=True):
                    port.exit_position(exit_sym, exit_price)
                    st.session_state["portfolio_cash"] = port.cash
                    st.session_state["portfolio_positions"] = port.positions
                    st.success(f"Successfully closed position in {exit_sym}!")
                    st.rerun()
        else:
            st.info("No open simulated positions. Add positions using the Trade Panel on the right or from the Screener view.")

    with col_add:
        st.markdown("#### Quick Allocation Entry")
        sym_input = st.text_input("Symbol", "RELIANCE")
        sector_input = st.text_input("Sector", "Energy")
        entry_p = st.number_input("Entry Price (₹)", value=2500.0, step=10.0)
        atr_input = st.number_input("ATR (₹)", value=40.0, step=1.0)
        risk_pct = st.slider("Risk Per Trade %", 0.5, 3.0, 1.0)

        risk_amt = nav * (risk_pct / 100.0)
        stop_dist = 1.5 * atr_input
        calc_qty = max(1, int(risk_amt / stop_dist)) if stop_dist > 0 else 1
        stop_price = round(entry_p - stop_dist, 2)
        target_price = round(entry_p + 3.0 * atr_input, 2)
        st.caption(f"Suggested Qty (1.5x ATR Stop): **{calc_qty} shares** (Required: ₹{calc_qty * entry_p:,.2f})")

        if st.button("Add to Simulated Portfolio", use_container_width=True, type="primary"):
            sym = sym_input.strip().upper()
            val = calc_qty * entry_p
            ok, reason = port.can_add(sym, sector_input.strip() or "Other", entry_p, val)
            if not ok:
                st.error(f"Cannot add position: {reason}")
            else:
                added = port.add_position(
                    symbol=sym,
                    qty=float(calc_qty),
                    price=entry_p,
                    stop_price=stop_price,
                    target_price=target_price,
                    sector=sector_input.strip() or "Other",
                    date_str=pd.Timestamp.now().strftime("%Y-%m-%d"),
                )
                if added:
                    st.session_state["portfolio_cash"] = port.cash
                    st.session_state["portfolio_positions"] = port.positions
                    st.success(f"Added {calc_qty} shares of {sym}!")
                    st.rerun()
                else:
                    st.error("Failed to add position.")

    # Sector Allocation Visualization (Migrated from 02_portfolio)
    st.markdown("---")
    st.markdown("<div class='section-hdr'><h3>Sector Exposure & Risk Allocation</h3><div class='line'></div></div>", unsafe_allow_html=True)
    sectors = port.get_sector_exposure_percentages()
    if sectors:
        sec_df = pd.DataFrame(list(sectors.items()), columns=["Sector", "Allocation %"])
        sec_df["Allocation %"] = sec_df["Allocation %"] * 100.0

        col_chart, col_limits = st.columns(2)
        with col_chart:
            st.bar_chart(sec_df.set_index("Sector"))
        with col_limits:
            st.markdown("##### Allocation Policy Controls")
            st.write(f"- Maximum exposure per sector: **{port.max_sector_exposure_pct:.1%}**")
            st.write(f"- Maximum allocation per position: **{port.max_single_position_pct:.1%}**")
            st.write(f"- Maximum simultaneous positions: **{port.max_positions}**")
            for sect, val in sectors.items():
                if val > port.max_sector_exposure_pct:
                    st.error(f"⚠️ Sector **{sect}** ({val:.1%}) breaches the {port.max_sector_exposure_pct:.1%} exposure limit!")
                else:
                    st.success(f"✔ Sector **{sect}** ({val:.1%}) is within safety limits.")
    else:
        st.info("No active allocations to display sector breakdown.")
