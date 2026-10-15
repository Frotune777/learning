"""
File: src/dashboard/views/smc_view.py
Purpose: Professional Smart Money Concepts (SMC) & Institutional Setup Studio.
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.storage.smc_db import SMCDatabase
from src.engine.smc import calculate_smc
from src.engine.smc_decision import generate_smc_call
from src.engine.lux_nwe import calculate_nwe
from src.engine.lux_volume_profile import calculate_volume_profile
from src.engine.lux_model_2022 import calculate_model_2022
from src.engine.lux_ifvg_sweeps import calculate_sweeps_ifvgs
from src.engine.lux_savgol import calculate_savgol


def render_smc_view():
    db = SMCDatabase()

    st.markdown("""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <div>
            <h2 style="margin:0; font-weight:800; color:#f8fafc;">🎯 Smart Money Concepts & Decision Terminal</h2>
            <p style="margin:4px 0 0; color:#94a3b8; font-size:0.9rem;">
                Live BOS, CHoCH, Order Blocks, Imbalances (FVG), Nadaraya-Watson Kernel & Volume Profile.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    calls_all = db.get_calls()
    df_calls = pd.DataFrame(calls_all) if calls_all else pd.DataFrame()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Logged SMC Setups</div>
            <div class="pro-card-value">{len(df_calls)}</div>
            <div class="pro-card-sub">All-time identified setups</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        p_count = len(df_calls[df_calls["status"] == "PENDING"]) if not df_calls.empty else 0
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Pending Confirmations</div>
            <div class="pro-card-value" style="color:#38bdf8;">{p_count}</div>
            <div class="pro-card-sub">Awaiting trigger entry</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        act_count = len(df_calls[df_calls["status"] == "TRIGGERED"]) if not df_calls.empty else 0
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Active Live Calls</div>
            <div class="pro-card-value" style="color:#10b981;">{act_count}</div>
            <div class="pro-card-sub">In-progress trades</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        avg_rr = f"{df_calls['risk_reward'].mean():.2f}" if not df_calls.empty else "0.00"
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Average Setup R:R</div>
            <div class="pro-card-value" style="color:#a855f7;">{avg_rr}R</div>
            <div class="pro-card-sub">Strict min 1.8R filter</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # 3-Column Studio Layout
    left_col, center_col, right_col = st.columns([1.1, 2.5, 1.2])

    with left_col:
        st.markdown("#### Setup Queue")
        status_filter = st.selectbox("Status Filter", ["ALL", "PENDING", "TRIGGERED", "STOPPED", "TARGET_HIT"], label_visibility="collapsed")
        filtered_calls = db.get_calls(status=None if status_filter == "ALL" else status_filter)

        selected_call = None
        if filtered_calls:
            options = {f"#{c['id']} {c['symbol']} ({c['direction']}) · {c['setup_type']}": c for c in filtered_calls}
            selected_label = st.radio("Select Call", list(options.keys()), label_visibility="collapsed")
            selected_call = options[selected_label]
        else:
            st.info("No calls found in this status category.")

        st.markdown("---")
        st.markdown("#### Scan Specific Stock")
        target_dir = Path("data/historical/1d")
        all_syms = sorted([f.stem for f in target_dir.glob("*.parquet")]) if target_dir.exists() else []
        if all_syms:
            custom_sym = st.selectbox("Direct Symbol Analysis", all_syms, index=all_syms.index("RELIANCE") if "RELIANCE" in all_syms else 0)
            if st.button("Run SMC Scan on Symbol", use_container_width=True):
                df_custom = pd.read_parquet(target_dir / f"{custom_sym}.parquet")
                df_custom.columns = [c.lower() for c in df_custom.columns]
                smc_res = calculate_smc(df_custom, swing_length=20, internal_length=5)
                new_call = generate_smc_call(custom_sym, smc_res, df_custom)
                if new_call:
                    db.create_call(new_call)
                    st.success(f"Triggered setup logged for {custom_sym}!")
                    st.rerun()
                else:
                    st.info(f"No qualified setup found for {custom_sym} right now.")

    with center_col:
        st.markdown("#### Institutional Price Geometry")
        if selected_call:
            sym = selected_call["symbol"]
            p_path = Path("data/historical/1d") / f"{sym}.parquet"

            if p_path.exists():
                df_hist = pd.read_parquet(p_path).tail(130)
                df_hist.columns = [c.lower() for c in df_hist.columns]

                smc_res = calculate_smc(df_hist, swing_length=15, internal_length=5)

                col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                with col_t1:
                    show_nwe = st.toggle("NWE Envelope", value=True)
                with col_t2:
                    show_vp = st.toggle("Volume Profile", value=True)
                with col_t3:
                    show_sweeps = st.toggle("Sweeps & iFVGs", value=True)
                with col_t4:
                    show_sg = st.toggle("Savitzky-Golay", value=False)

                fig = go.Figure(data=[go.Candlestick(
                    x=df_hist.index,
                    open=df_hist['open'],
                    high=df_hist['high'],
                    low=df_hist['low'],
                    close=df_hist['close'],
                    name=sym,
                    increasing_line_color='#10b981',
                    decreasing_line_color='#ef4444'
                )])

                if show_nwe:
                    nwe_res = calculate_nwe(df_hist, bandwidth=8.0, multiplier=2.5)
                    nwe_df = nwe_res.to_pandas()
                    fig.add_trace(go.Scatter(x=df_hist.index, y=nwe_df['nwe_upper'], mode='lines', line=dict(color='rgba(239,68,68,0.7)', width=1.2), name='NWE Upper'))
                    fig.add_trace(go.Scatter(x=df_hist.index, y=nwe_df['nwe_lower'], mode='lines', line=dict(color='rgba(16,185,129,0.7)', width=1.2), name='NWE Lower'))
                    fig.add_trace(go.Scatter(x=df_hist.index, y=nwe_df['nwe'], mode='lines', line=dict(color='rgba(148,163,184,0.5)', width=1, dash='dot'), name='NWE Kernel'))

                if show_sg:
                    sg_res = calculate_savgol(df_hist, half_width=10, poly_order=2)
                    sg_df = sg_res.to_pandas()
                    fig.add_trace(go.Scatter(x=df_hist.index, y=sg_df['sg_filter'], mode='lines', line=dict(color='#a855f7', width=1.8), name='Savitzky-Golay'))

                if show_sweeps:
                    sw_res = calculate_sweeps_ifvgs(df_hist, swing_len=4)
                    sw_df = sw_res.to_pandas()
                    high_sweeps = sw_df[sw_df['sweep_high']]
                    low_sweeps = sw_df[sw_df['sweep_low']]
                    if not high_sweeps.empty:
                        fig.add_trace(go.Scatter(
                            x=high_sweeps.index,
                            y=high_sweeps['high'] * 1.002,
                            mode='markers',
                            marker=dict(symbol='triangle-down', size=9, color='#f59e0b'),
                            name='Bearish Sweep'
                        ))
                    if not low_sweeps.empty:
                        fig.add_trace(go.Scatter(
                            x=low_sweeps.index,
                            y=low_sweeps['low'] * 0.998,
                            mode='markers',
                            marker=dict(symbol='triangle-up', size=9, color='#06b6d4'),
                            name='Bullish Sweep'
                        ))

                if show_vp:
                    vp_res = calculate_volume_profile(df_hist, lookback=len(df_hist))
                    fig.add_hline(y=vp_res.poc_price, line_dash="solid", line_color="#f59e0b", annotation_text=f"POC ₹{vp_res.poc_price}")
                    fig.add_hline(y=vp_res.vah_price, line_dash="dot", line_color="#38bdf8", annotation_text=f"VAH ₹{vp_res.vah_price}")
                    fig.add_hline(y=vp_res.val_price, line_dash="dot", line_color="#38bdf8", annotation_text=f"VAL ₹{vp_res.val_price}")


                fig.add_hline(y=selected_call['entry_price'], line_dash="dash", line_color="#38bdf8", annotation_text=f"ENTRY ₹{selected_call['entry_price']}")
                fig.add_hline(y=selected_call['stop_loss'], line_dash="dash", line_color="#ef4444", annotation_text=f"SL ₹{selected_call['stop_loss']}")
                fig.add_hline(y=selected_call['target_1'], line_dash="dash", line_color="#10b981", annotation_text=f"TP1 ₹{selected_call['target_1']}")

                if not pd.isna(smc_res.equilibrium_level):
                    fig.add_hline(y=smc_res.equilibrium_level, line_dash="dot", line_color="#64748b", annotation_text="EQ (50%)")

                fig.update_layout(
                    height=530,
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(15,23,42,0.6)',
                    margin=dict(l=10, r=10, t=25, b=10),
                    xaxis_rangeslider_visible=False,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"No parquet found for {sym}")
        else:
            st.info("Select a trading call to load interactive chart geometry.")

    with right_col:
        st.markdown("#### Execution Parameters")
        if selected_call:
            cid = selected_call["id"]
            d_class = "badge-bull" if selected_call["direction"] == "BUY" else "badge-bear"
            st.markdown(f"""
            <div style="margin-bottom:12px;">
                <span style="font-size:1.3rem; font-weight:800; color:#f8fafc;">{selected_call['symbol']}</span>
                <span class="{d_class}" style="margin-left:8px;">{selected_call['direction']}</span>
            </div>
            """, unsafe_allow_html=True)

            st.write(f"**Setup Type:** `{selected_call['setup_type']}`")
            st.write(f"**Entry Price:** ₹{selected_call['entry_price']:,.2f}")
            st.write(f"**Stop Loss:** ₹{selected_call['stop_loss']:,.2f}")
            st.write(f"**Target 1:** ₹{selected_call['target_1']:,.2f}")
            st.write(f"**Target 2:** ₹{selected_call['target_2']:,.2f}")
            st.write(f"**Risk/Reward:** `{selected_call['risk_reward']:.2f}R`")

            st.markdown("---")
            st.markdown("##### Position Calculator")
            user_risk = st.number_input("Max Risk Allowed (₹)", min_value=500, max_value=200000, value=5000, step=500)
            risk_per_share = abs(selected_call['entry_price'] - selected_call['stop_loss'])
            qty = int(user_risk / risk_per_share) if risk_per_share > 0 else 0
            st.markdown(f"""
            <div style="background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.3); border-radius:10px; padding:10px 14px; margin-bottom:14px;">
                <div style="font-size:0.8rem; color:#94a3b8;">Allocated Shares</div>
                <div style="font-size:1.4rem; font-weight:800; color:#38bdf8;">{qty} units</div>
                <div style="font-size:0.75rem; color:#64748b;">Capital: ₹{qty * selected_call['entry_price']:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("##### LLM Quantitative Dossier")
            from src.engine.llm_report import generate_symbol_llm_dossier
            if st.button("📋 Generate LLM Dossier", use_container_width=True):
                st.session_state[f"llm_dossier_{sym}"] = generate_symbol_llm_dossier(sym)

            if f"llm_dossier_{sym}" in st.session_state:
                with st.expander("📄 View & Copy LLM Dossier", expanded=True):
                    st.text_area("Prompt / Dossier Content", st.session_state[f"llm_dossier_{sym}"], height=240)
                    st.download_button(
                        label="⬇️ Download Markdown",
                        data=st.session_state[f"llm_dossier_{sym}"],
                        file_name=f"{sym}_LLM_DOSSIER.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
        else:
            st.info("Pick a call from the queue.")


    st.markdown("<div class='section-hdr'><h3>Active Calls Ledger (`smc_calls.sqlite`)</h3><div class='line'></div></div>", unsafe_allow_html=True)
    if not df_calls.empty:
        st.dataframe(df_calls, use_container_width=True, hide_index=True)
    else:
        st.caption("No historical records in database.")
