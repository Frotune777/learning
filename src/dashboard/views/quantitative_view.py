"""
File: src/dashboard/views/quantitative_view.py
Purpose: Quantitative market analytics: Sector Rotation (JdK), Correlation Matrix & Market Mood Index (MMI).
"""

from __future__ import annotations

import glob
import os

import pandas as pd
import plotly.express as px
import streamlit as st


def render_quantitative_view():
    st.markdown("""
    <div>
        <h2 style="margin:0; font-weight:800; color:#f8fafc;">📊 Quantitative & Macro Intelligence</h2>
        <p style="margin:4px 0 16px; color:#94a3b8; font-size:0.9rem;">
            Cross-asset correlation matrix, sector rotation quadrant, and Market Mood Index (MMI).
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab_corr, tab_mmi, tab_weinstein, tab_vsa = st.tabs([
        "Asset Correlation Matrix",
        "Market Mood & Sentiment",
        "Weinstein 4-Stage Regime",
        "VSA (No-Demand / No-Supply)",
    ])

    with tab_corr:
        hist_dir = "data/historical/1d"
        files = sorted(glob.glob(os.path.join(hist_dir, "*.parquet")))
        if len(files) >= 4:
            syms = [os.path.basename(f).replace(".parquet", "") for f in files]
            default_picks = [s for s in ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "LT", "ITC"] if s in syms]
            selected = st.multiselect("Select Assets for Correlation", syms, default=default_picks or syms[:6])

            if len(selected) >= 2:
                series_map = {}
                for s in selected:
                    df = pd.read_parquet(os.path.join(hist_dir, f"{s}.parquet")).tail(120)
                    df.columns = [c.lower() for c in df.columns]
                    series_map[s] = df["close"].pct_change()
                corr_df = pd.DataFrame(series_map).dropna().corr()

                fig = px.imshow(
                    corr_df,
                    text_auto=".2f",
                    color_continuous_scale="RdBu_r",
                    zmin=-1,
                    zmax=1,
                    template="plotly_dark",
                )
                fig.update_layout(height=480, margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Insufficient historical parquets to compute cross-correlation.")

    with tab_mmi:
        st.markdown("#### Market Mood Index (MMI)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("""
            <div class="pro-card">
                <div class="pro-card-title">Sentiment Regime</div>
                <div class="pro-card-value" style="color:#10b981;">GREED</div>
                <div class="pro-card-sub">Score: 64.2 / 100</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown("""
            <div class="pro-card">
                <div class="pro-card-title">Advance / Decline</div>
                <div class="pro-card-value" style="color:#38bdf8;">1.42</div>
                <div class="pro-card-sub">Bulls leading market breadth</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown("""
            <div class="pro-card">
                <div class="pro-card-title">India VIX Level</div>
                <div class="pro-card-value" style="color:#f59e0b;">14.71</div>
                <div class="pro-card-sub">Normal Volatility Regime</div>
            </div>
            """, unsafe_allow_html=True)

    with tab_weinstein:
        st.markdown("#### Stan Weinstein 4-Stage Macro Screener & Classifier")
        st.caption("Classifies macro cycles: Stage 1 (Basing), Stage 2 (Advancing Markup), Stage 3 (Topping), Stage 4 (Declining Markdown).")
        
        hist_dir = "data/historical/1d"
        files = sorted(glob.glob(os.path.join(hist_dir, "*.parquet")))
        if files:
            from src.engine.lux_weinstein import calculate_weinstein_stage
            weinstein_rows = []
            for f in files[:30]:
                sym = os.path.basename(f).replace(".parquet", "")
                try:
                    df = pd.read_parquet(f)
                    df.columns = [c.lower() for c in df.columns]
                    if len(df) >= 60:
                        w_res = calculate_weinstein_stage(df, ma_weeks=10, slope_weeks=2, is_daily=True)
                        weinstein_rows.append({
                            "Symbol": sym,
                            "Stage": w_res.stage_name,
                            "30W MA": f"₹{w_res.ma_value:,.2f}",
                            "MA Slope %": f"{w_res.ma_slope_pct:+.2f}%",
                            "Vol Ratio": f"{w_res.volume_ratio:.2f}x",
                            "Breakout": "🚀 YES" if w_res.is_breakout else "—",
                            "Breakdown": "⚠️ YES" if w_res.is_breakdown else "—",
                        })
                except Exception:
                    continue
            if weinstein_rows:
                st.dataframe(pd.DataFrame(weinstein_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No symbol data long enough for Weinstein analysis.")

    with tab_vsa:
        st.markdown("#### Volume Spread Analysis (VSA) Diagnostic")
        st.caption("Identifies institutional testing: No-Demand Bars (low volume rallies) and No-Supply Bars (low volume sell-offs).")
        hist_dir = "data/historical/1d"
        files = sorted(glob.glob(os.path.join(hist_dir, "*.parquet")))
        if files:
            from src.engine.lux_vsa import calculate_vsa_bars
            syms = [os.path.basename(f).replace(".parquet", "") for f in files]
            pick = st.selectbox("Select Asset for VSA Audit", syms, index=0)
            df = pd.read_parquet(os.path.join(hist_dir, f"{pick}.parquet"))
            df.columns = [c.lower() for c in df.columns]
            vsa_res = calculate_vsa_bars(df)
            vdf = vsa_res.to_pandas().tail(20)
            
            vc1, vc2, vc3 = st.columns(3)
            with vc1:
                st.metric("Latest Relative Spread", f"{vsa_res.relative_spread:.2f}x")
            with vc2:
                st.metric("Latest Relative Volume", f"{vsa_res.relative_volume:.2f}x")
            with vc3:
                status = "🛑 No-Demand" if vsa_res.latest_no_demand else ("🟢 No-Supply" if vsa_res.latest_no_supply else "Neutral Volume")
                st.metric("VSA Signature", status)
                
            st.dataframe(
                vdf[["date" if "date" in vdf.columns else "close", "close", "vsa_no_demand", "vsa_no_supply", "vsa_spread_ratio", "vsa_vol_ratio"]],
                use_container_width=True,
                hide_index=True
            )

