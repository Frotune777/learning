"""
File: src/dashboard/views/screener_view.py
Purpose: High-speed multi-strategy technical screening & consensus scanner view.
"""

from __future__ import annotations

import glob
import os

import pandas as pd
import streamlit as st

from src.core.config import SCREENER_STRATEGIES


def get_screener_csvs(hist_dir: str = "data/historical") -> list[str]:
    """Discover screener CSV output files in priority order."""
    enriched = sorted(glob.glob(os.path.join(hist_dir, "top_250_enriched_*.csv")), reverse=True)
    analyzed = sorted(glob.glob(os.path.join(hist_dir, "top_250_analyzed_*.csv")), reverse=True)
    other = sorted(
        glob.glob(os.path.join(hist_dir, "final_list_*.csv"))
        + glob.glob(os.path.join(hist_dir, "swing_list_*.csv"))
        + glob.glob(os.path.join(hist_dir, "super_list_*.csv")),
        reverse=True,
    )
    return enriched + analyzed + other


def _get_strategy_action_column(strategy_name: str, available_cols: list[str]) -> str | None:
    """Map strategy display name or config key to actual action column in DataFrame."""
    known_map = {
        "Nifty Shop (Single Leg)": "STR_NIFTY_SHOP_ACTION",
        "Buy Low Sell High": "STR_BUY_LOW_ACTION",
        "Turtle Trading": "STR_TURTLE_ACTION",
        "RDX Indicator": "STR_RDX_ACTION",
        "100 SMA Breakout": "STR_100SMA_ACTION",
        "ETF Shop Method": "STR_ETF_SHOP_ACTION",
        "Super BO Stocks": "STR_SUPER_BO_ACTION",
        "DMADMA (Reverse)": "STR_DMA_REV_ACTION",
        "DMADMA (No SL)": "STR_DMA_NOSL_ACTION",
        "Minervini VCP": "STR_VCP_ACTION",
        "TTM Squeeze": "STR_TTM_ACTION",
        "SuperTrend": "STR_SUPERTREND_ACTION",
        "Lorentzian Classification": "STR_LORENTZIAN_ACTION",
    }
    if strategy_name in known_map and known_map[strategy_name] in available_cols:
        return known_map[strategy_name]

    strat = next((s for s in SCREENER_STRATEGIES if s.get("name") == strategy_name), None)
    if strat:
        pfx = strat.get("file_prefix", "").replace("strategy_", "").upper()
        cand = f"STR_{pfx}_ACTION"
        if cand in available_cols:
            return cand
        for c in available_cols:
            if c.startswith("STR_") and c.endswith("_ACTION") and pfx in c:
                return c
    return None


def render_screener_view(data_dir: str = "data/historical"):
    st.markdown("""
    <div>
        <h2 style="margin:0; font-weight:800; color:#f8fafc;">⚡ Multi-Strategy Technical Screener & Scanners</h2>
        <p style="margin:4px 0 16px; color:#94a3b8; font-size:0.9rem;">
            Filter screened stocks by strategy signals, volume bursts, Minervini VCP, and composite score.
        </p>
    </div>
    """, unsafe_allow_html=True)

    csv_files = get_screener_csvs(data_dir)

    if not csv_files:
        st.info(f"No screened CSVs found in {data_dir}. Run `uv run main.py screen` to populate.")
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
        car_col = "CAR_RATING" if "CAR_RATING" in df.columns else ("CAR_Category" if "CAR_Category" in df.columns else None)
        top_picks = len(df[df[car_col].astype(str).str.contains("Buy", case=False, na=False)]) if car_col else 0
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">CAR Buy Rated</div>
            <div class="pro-card-value" style="color:#10b981;">{top_picks}</div>
            <div class="pro-card-sub">Textbook setups</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        vol_col = "VOL_SPIKE" if "VOL_SPIKE" in df.columns else ("Volume_Spike_10d" if "Volume_Spike_10d" in df.columns else None)
        if vol_col:
            if pd.api.types.is_numeric_dtype(df[vol_col]):
                vol_spikes = int((df[vol_col] >= 2.0).sum())
            else:
                vol_spikes = int((df[vol_col] == True).sum())
        else:
            vol_spikes = 0
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Volume Spikes</div>
            <div class="pro-card-value" style="color:#f59e0b;">{vol_spikes}</div>
            <div class="pro-card-sub">&ge;2.0x volume burst</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        comp_col = "COMPOSITE_SCORE" if "COMPOSITE_SCORE" in df.columns else ("Composite_Score" if "Composite_Score" in df.columns else None)
        avg_score = f"{df[comp_col].mean():.1f}" if comp_col and not df[comp_col].empty and pd.api.types.is_numeric_dtype(df[comp_col]) else "N/A"
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
        action_col = _get_strategy_action_column(strategy_filter, list(display_df.columns))
        if action_col and action_col in display_df.columns:
            display_df = display_df[display_df[action_col].astype(str).str.contains("Buy|Breakout|Long|Explosive|Level", case=False, na=False)]

    # Quick Search by Symbol
    search_q = st.text_input("Filter by Symbol or Sector:", placeholder="Type e.g. TATA, RELIANCE, Nifty IT...")
    if search_q.strip():
        q = search_q.strip().upper()
        sym_col = "SYMBOL" if "SYMBOL" in display_df.columns else ("Symbol" if "Symbol" in display_df.columns else None)
        if sym_col:
            display_df = display_df[display_df[sym_col].astype(str).str.contains(q, case=False, na=False)]

    st.dataframe(display_df, use_container_width=True, height=520)
