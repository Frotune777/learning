"""
File: src/dashboard/views/screener_view.py
Purpose: High-speed multi-strategy technical screening & consensus scanner view.
"""

from __future__ import annotations
import glob
import os
from pathlib import Path
import pandas as pd
import streamlit as st

from src.core.config import SCREENER_STRATEGIES


def render_screener_view():
    st.markdown("""
    <div>
        <h2 style="margin:0; font-weight:800; color:#f8fafc;">⚡ Multi-Strategy Technical Screener & Scanners</h2>
        <p style="margin:4px 0 16px; color:#94a3b8; font-size:0.9rem;">
            Filter screened stocks by strategy signals, volume bursts, Minervini VCP, and consensus score.
        </p>
    </div>
    """, unsafe_allow_html=True)

    processed_dir = "data/processed"
    csv_files = sorted(glob.glob(os.path.join(processed_dir, "screen_stocks_*.csv")), reverse=True)

    if not csv_files:
        st.info("No screened CSVs found in data/processed/. Run `uv run main.py screen` to populate.")
        return

    # File selection & overview
    col_f, col_cat = st.columns([2, 1])
    with col_f:
        selected_csv = st.selectbox("Processed Scan File", csv_files, format_func=lambda x: os.path.basename(x))
    with col_cat:
        strategy_filter = st.selectbox("Filter by Strategy", ["ALL"] + [s["name"] for s in SCREENER_STRATEGIES])

    df = pd.read_csv(selected_csv)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Total Stocks Screened</div>
            <div class="pro-card-value">{len(df)}</div>
            <div class="pro-card-sub">In selected run</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        top_picks = len(df[df["CAR_Category"].isin(["Buy", "Breakout Buy"])]) if "CAR_Category" in df.columns else 0
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">CAR Buy Rated</div>
            <div class="pro-card-value" style="color:#10b981;">{top_picks}</div>
            <div class="pro-card-sub">Textbook setups</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        vol_spikes = len(df[df["Volume_Spike_10d"] == True]) if "Volume_Spike_10d" in df.columns else 0
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Volume Spikes</div>
            <div class="pro-card-value" style="color:#f59e0b;">{vol_spikes}</div>
            <div class="pro-card-sub">>2x 10d volume burst</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        avg_score = f"{df['Composite_Score'].mean():.1f}" if "Composite_Score" in df.columns else "N/A"
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Avg Composite Score</div>
            <div class="pro-card-value" style="color:#a855f7;">{avg_score}</div>
            <div class="pro-card-sub">Multi-factor rating</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    # Filter dataframe
    display_df = df.copy()
    if strategy_filter != "ALL":
        strat_col = next((s["col"] for s in SCREENER_STRATEGIES if s["name"] == strategy_filter), None)
        if strat_col and strat_col in display_df.columns:
            display_df = display_df[display_df[strat_col].astype(str).str.contains("Buy|Breakout|Long", case=False, na=False)]

    # Quick Search
    search_q = st.text_input("Filter by Symbol or Sector:", placeholder="Type e.g. TATA, RELIANCE, Nifty IT...")
    if search_q.strip():
        q = search_q.strip().upper()
        display_df = display_df[display_df["SYMBOL"].astype(str).str.contains(q, case=False, na=False)]

    st.dataframe(display_df, use_container_width=True, height=520)
