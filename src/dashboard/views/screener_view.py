"""
File: src/dashboard/views/screener_view.py
Purpose: High-speed multi-strategy technical screening, consensus leaderboard, and strategy heatmap view.
"""

from __future__ import annotations

import glob
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from src.core.config import SCREENER_STRATEGIES
from src.portfolio.portfolio_engine import Portfolio

_BUY_VALS = {
    "Buy",
    "Breakout Buy",
    "Explosive Buy",
    "Level 1 Buy",
    "Level 2 Buy",
    "Level 3 Buy",
    "150 DMA Breakout | CMP > 200 DMA",
    "50 DMA Breakout | CMP > 200 DMA",
    "Super BO Buy",
    "Buy on Support / Demand Level",
    "Buy (55D Breakout)",
    "VCP Tightening",
    "Squeeze Active (Bullish)",
    "Long Entry",
    "Lorentzian Buy",
}


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
    col_f, col_cat, col_cons, col_sec = st.columns([1.5, 1.2, 1.0, 1.0])
    with col_f:
        selected_csv = st.selectbox("Processed Scan File", csv_files, format_func=lambda x: os.path.basename(x))
    
    df = pd.read_csv(selected_csv)

    with col_cat:
        strategy_options = (
            ["ALL", "In Bull Run", "Start GTT"]
            + [s["name"] for s in SCREENER_STRATEGIES]
            + ["Minervini VCP", "TTM Squeeze", "SuperTrend", "Lorentzian Classification"]
        )
        # Deduplicate preserving order
        seen_strats = set()
        dedup_strats = []
        for s in strategy_options:
            if s not in seen_strats:
                seen_strats.add(s)
                dedup_strats.append(s)
        strategy_filter = st.selectbox("Filter by Strategy", dedup_strats)

    with col_cons:
        max_cons = 13 if "CONSENSUS_SCORE" in df.columns else 1
        min_consensus = st.slider("Min Consensus Score", min_value=0, max_value=max_cons, value=0)

    with col_sec:
        sectors = ["ALL"]
        sec_col = "Sector" if "Sector" in df.columns else ("SECTOR" if "SECTOR" in df.columns else None)
        if sec_col:
            sectors += sorted(df[sec_col].dropna().unique().tolist())
        selected_sector = st.selectbox("Filter by Sector", sectors)

    # Filter dataframe
    display_df = df.copy()

    if strategy_filter != "ALL":
        if strategy_filter == "In Bull Run" and "TREND_STATUS" in display_df.columns:
            display_df = display_df[display_df["TREND_STATUS"] == "In Bull Run"]
        elif strategy_filter == "Start GTT" and "BOTTOM_OUT_STATUS" in display_df.columns:
            display_df = display_df[display_df["BOTTOM_OUT_STATUS"].isin(["Start GTT", "Start GTT (Basic)"])]
        else:
            action_col = _get_strategy_action_column(strategy_filter, list(display_df.columns))
            if action_col and action_col in display_df.columns:
                display_df = display_df[display_df[action_col].isin(_BUY_VALS)]

    if min_consensus > 0 and "CONSENSUS_SCORE" in display_df.columns:
        display_df = display_df[
            pd.to_numeric(display_df["CONSENSUS_SCORE"], errors="coerce").fillna(0) >= min_consensus
        ]

    if selected_sector != "ALL" and sec_col:
        display_df = display_df[display_df[sec_col] == selected_sector]

    # Quick Search by Symbol
    search_q = st.text_input("Filter by Symbol:", placeholder="Type e.g. TATA, RELIANCE, INFY...")
    if search_q.strip():
        q = search_q.strip().upper()
        sym_col = "SYMBOL" if "SYMBOL" in display_df.columns else ("Symbol" if "Symbol" in display_df.columns else None)
        if sym_col:
            display_df = display_df[display_df[sym_col].astype(str).str.contains(q, case=False, na=False)]

    # KPI Summary Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Stocks Filtered / Screened</div>
            <div class="pro-card-value">{len(display_df)} <span style="font-size:1rem; color:#94a3b8;">/ {len(df)}</span></div>
            <div class="pro-card-sub">In selected run</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        car_col = "CAR_RATING" if "CAR_RATING" in display_df.columns else ("CAR_Category" if "CAR_Category" in display_df.columns else None)
        top_picks = len(display_df[display_df[car_col].astype(str).str.contains("Buy", case=False, na=False)]) if car_col else 0
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">CAR Buy Rated</div>
            <div class="pro-card-value" style="color:#10b981;">{top_picks}</div>
            <div class="pro-card-sub">Textbook setups</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        vol_col = "VOL_SPIKE" if "VOL_SPIKE" in display_df.columns else ("Volume_Spike_10d" if "Volume_Spike_10d" in display_df.columns else None)
        if vol_col:
            if pd.api.types.is_numeric_dtype(display_df[vol_col]):
                vol_spikes = int((display_df[vol_col] >= 2.0).sum())
            else:
                vol_spikes = int((display_df[vol_col] == True).sum())
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
        comp_col = "COMPOSITE_SCORE" if "COMPOSITE_SCORE" in display_df.columns else ("Composite_Score" if "Composite_Score" in display_df.columns else None)
        avg_score = f"{display_df[comp_col].mean():.1f}" if comp_col and not display_df[comp_col].empty and pd.api.types.is_numeric_dtype(display_df[comp_col]) else "N/A"
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Avg Composite Score</div>
            <div class="pro-card-value" style="color:#a855f7;">{avg_score}</div>
            <div class="pro-card-sub">Multi-factor rating</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    # Priority columns ordering
    DISPLAY_COLS_PRIORITY = [
        "SYMBOL",
        "CMP",
        "TREND_STATUS",
        "CAR_RATING",
        "CONSENSUS_SCORE",
        "CONSENSUS_CALLOUT",
        "COMPOSITE_SCORE",
        "RANK",
        "VOL_SPIKE",
        "TECH_SCORE",
        "RSI_14",
        "ATR_14",
        "DELIV_PCT",
        "STR_VCP_ACTION",
        "STR_TTM_ACTION",
        "STR_SUPERTREND_ACTION",
        "STR_LORENTZIAN_ACTION",
    ]
    disp_cols = [c for c in DISPLAY_COLS_PRIORITY if c in display_df.columns]
    # Add any remaining columns
    other_cols = [c for c in display_df.columns if c not in disp_cols]
    final_cols = disp_cols + other_cols

    st.dataframe(display_df[final_cols], use_container_width=True, height=450)

    # Strategy Heatmap Section (Migrated from 01_daily_signals)
    strat_action_cols = [c for c in df.columns if c.startswith("STR_") and c.endswith("_ACTION")]
    if strat_action_cols and not display_df.empty:
        with st.expander("🔥 Strategy Signals Heatmap", expanded=False):
            heat_df = display_df[["SYMBOL"] + strat_action_cols].set_index("SYMBOL").head(40)

            def _to_num(val):
                if val in _BUY_VALS:
                    return 1
                if str(val) in {"Explosive Sell", "Lorentzian Sell"}:
                    return -1
                return 0

            heat_num = heat_df.apply(lambda col: col.map(_to_num))
            heat_num.columns = [
                c.replace("STR_", "").replace("_ACTION", "").replace("_", " ").title()
                for c in heat_num.columns
            ]
            st.dataframe(
                heat_num.style.background_gradient(cmap="RdYlGn", vmin=-1, vmax=1),
                use_container_width=True,
                height=320,
            )

    # Simulated Order Entry Section (Migrated from 01_daily_signals)
    if not display_df.empty and "SYMBOL" in display_df.columns:
        with st.expander("🛒 Simulated Order Entry", expanded=False):
            symbols = display_df["SYMBOL"].dropna().unique().tolist()
            if symbols:
                col1, col2, col3 = st.columns(3)
                with col1:
                    buy_sym = st.selectbox("Select Symbol for Simulated Allocation", symbols)
                    stock_row = display_df[display_df["SYMBOL"] == buy_sym].iloc[0]

                with col2:
                    raw_cmp = stock_row.get("CMP", 0.0)
                    entry_price = float(raw_cmp) if pd.notna(raw_cmp) and raw_cmp > 0 else 1.0
                    raw_atr = stock_row.get("ATR_14")
                    atr = float(raw_atr) if pd.notna(raw_atr) and float(raw_atr) > 0 else entry_price * 0.02
                    stop_price = round(entry_price - 1.5 * atr, 2)
                    target_price = round(entry_price + 3.0 * atr, 2)
                    cash_val = float(st.session_state.get("portfolio_cash", 500_000.0))
                    risk_per_trade = cash_val * 0.01
                    diff = max(entry_price - stop_price, 1.0)
                    sug_qty = max(1, int(risk_per_trade / diff)) if pd.notna(diff) and diff > 0 else 1
                    qty = st.number_input("Quantity", min_value=1, value=sug_qty, key=f"sim_qty_{buy_sym}")
                    st.write(f"**CMP:** ₹{entry_price:,.2f}  ·  **ATR:** ₹{atr:.2f}")

                with col3:
                    st.write(f"**Stop Loss:** ₹{stop_price:,.2f}")
                    st.write(f"**Target:** ₹{target_price:,.2f}")
                    st.write(f"**Order Cost:** ₹{qty * entry_price:,.2f}")
                    callout = str(stock_row.get("CONSENSUS_CALLOUT", ""))
                    if callout:
                        st.caption(f"📊 {callout[:80]}")

                    if st.button("Place Simulated BUY", use_container_width=True, type="primary"):
                        if "portfolio_positions" not in st.session_state or not isinstance(st.session_state["portfolio_positions"], dict):
                            st.session_state["portfolio_positions"] = {}
                        port = Portfolio(initial_cash=float(st.session_state.get("portfolio_cash", 500_000.0)))
                        port.positions = st.session_state["portfolio_positions"]
                        sector_name = str(stock_row.get("Sector", stock_row.get("SECTOR", "Other")))
                        if port.add_position(
                            buy_sym, qty, entry_price, stop_price, target_price, sector=sector_name
                        ):
                            st.session_state["portfolio_cash"] = port.cash
                            st.session_state["portfolio_positions"] = port.positions
                            st.success(f"✅ Simulated BUY on {buy_sym} ({qty} shares @ ₹{entry_price:,.2f}) added to portfolio!")
                            st.rerun()
                        else:
                            st.error("❌ Insufficient cash or exposure limit breached.")

    # Export Section
    with st.expander("📤 Export Filtered Results", expanded=False):
        csv_data = display_df.to_csv(index=False)
        st.download_button(
            "⬇ Download Filtered CSV",
            data=csv_data,
            file_name=f"screener_signals_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )
