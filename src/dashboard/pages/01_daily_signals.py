"""
File: src/dashboard/pages/01_daily_signals.py
Purpose: Render daily trading signals with multi-factor scoring and ranking.

Dependencies:
    External:
        - streamlit==1.40.0: Render interactive web application components
        - pandas==2.2.3: Load and display data summaries
        - numpy==1.26.4: Perform vector operations
    Internal:
        - src.scoring.scoring_engine: Score stock records
        - src.portfolio.portfolio_engine: Handle simulated positions

Key Components:
    Classes:
        - None
    Functions:
        - None

Last Modified: 2026-06-17
Modified By: [Fortune]

Open Tasks:
    - [ ] [MEDIUM] Add filters for more strategy options

Related Files:
    - src/dashboard/app.py: Main landing page dashboard view
"""

import os
import sys

# Force project root into sys.path to resolve ModuleNotFoundError
root_dir = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../.."
        if os.path.basename(os.path.dirname(__file__)) == "dashboard"
        else "../../..",
    )
)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import glob
from datetime import datetime

import pandas as pd
import streamlit as st

from src.portfolio.portfolio_engine import Portfolio
from src.scoring.scoring_engine import ScoringEngine

st.set_page_config(page_title="Daily Signals", page_icon="🔍", layout="wide")

# ---------------------------------------------------------------------------
# CSS — shared premium styling
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.signal-buy  { color:#00c27c; font-weight:700; }
.signal-sell { color:#ff5555; font-weight:700; }
.signal-hold { color:#888; }
.card {
    background:linear-gradient(135deg,#1e2130 0%,#252836 100%);
    border:1px solid #2d3149; border-radius:10px; padding:14px 18px; margin:4px 0;
}
.card h4 { color:#7c83fd; font-size:0.78rem; text-transform:uppercase; margin:0 0 4px; letter-spacing:.08em; }
.card .val { font-size:1.5rem; font-weight:700; color:#f0f4ff; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div style="background:linear-gradient(90deg,#1a1d2e,#1e2130);border-bottom:2px solid #7c83fd;
            padding:16px 20px;border-radius:10px;margin-bottom:20px">
  <h2 style="color:#f0f4ff;margin:0">🔍 Daily Trading Signals</h2>
  <p style="color:#888;margin:4px 0 0">{datetime.now().strftime('%A, %d %b %Y  %H:%M')} &nbsp;·&nbsp; 13-Strategy Consensus Engine</p>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
st.session_state.setdefault("portfolio_cash", 500_000.0)
st.session_state.setdefault("portfolio_positions", {})

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
processed_dir = "data/processed"
analyzed_files = sorted(
    glob.glob(os.path.join(processed_dir, "top_250_analyzed_*.csv"))
)
enriched_files = sorted(
    glob.glob(os.path.join(processed_dir, "top_250_enriched_*.csv"))
)
target_files = analyzed_files if analyzed_files else enriched_files

if not target_files:
    st.error(
        "❌ No screening output found. Run the Technical Screener (CLI option 4) first."
    )
    st.stop()

# File selector
selected_file = st.sidebar.selectbox(
    "📂 Select Dataset",
    options=[os.path.basename(f) for f in target_files],
    index=len(target_files) - 1,
)
latest_file = next(f for f in target_files if os.path.basename(f) == selected_file)
df = pd.read_csv(latest_file)
st.sidebar.success(f"✅ {len(df)} stocks loaded")

# Compute composite + consensus if missing
if "COMPOSITE_SCORE" not in df.columns:
    scorer = ScoringEngine()
    df = scorer.score(df)

if "CONSENSUS_SCORE" not in df.columns:
    try:
        from src.core.consensus_engine import add_consensus_score

        df = add_consensus_score(df)
    except Exception:
        df["CONSENSUS_SCORE"] = 0
        df["CONSENSUS_CALLOUT"] = "N/A"

# ---------------------------------------------------------------------------
# Sidebar Filters
# ---------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("🎛 Filters")

# Strategy filter including new ones
strategy_options = [
    "All",
    "In Bull Run",
    "Start GTT",
    "STR_NIFTY_SHOP",
    "STR_BUY_LOW",
    "STR_TURTLE",
    "STR_RDX",
    "STR_100SMA",
    "STR_ETF_SHOP",
    "STR_SUPER_BO",
    "STR_VCP",
    "STR_TTM",
    "STR_SUPERTREND",
    "STR_LORENTZIAN",
]
selected_strat = st.sidebar.selectbox("Filter by Setup", strategy_options)

min_consensus = st.sidebar.slider(
    "Min Consensus Score", min_value=0, max_value=13, value=0
)

sectors = ["All"]
if "Sector" in df.columns:
    sectors += sorted(df["Sector"].dropna().unique().tolist())
selected_sector = st.sidebar.selectbox("Filter by Sector", sectors)

# ---------------------------------------------------------------------------
# Apply Filters
# ---------------------------------------------------------------------------
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
filtered = df.copy()

if selected_strat != "All":
    if selected_strat == "In Bull Run":
        filtered = filtered[filtered["TREND_STATUS"] == "In Bull Run"]
    elif selected_strat == "Start GTT":
        filtered = filtered[
            filtered["BOTTOM_OUT_STATUS"].isin(["Start GTT", "Start GTT (Basic)"])
        ]
    else:
        col_action = f"{selected_strat}_ACTION"
        if col_action in filtered.columns:
            filtered = filtered[filtered[col_action].isin(_BUY_VALS)]

if min_consensus > 0 and "CONSENSUS_SCORE" in filtered.columns:
    filtered = filtered[
        pd.to_numeric(filtered["CONSENSUS_SCORE"], errors="coerce").fillna(0)
        >= min_consensus
    ]

if selected_sector != "All" and "Sector" in filtered.columns:
    filtered = filtered[filtered["Sector"] == selected_sector]

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------
bull_count = (
    int((df["TREND_STATUS"] == "In Bull Run").sum())
    if "TREND_STATUS" in df.columns
    else 0
)
high_conv = int(
    (pd.to_numeric(df.get("CONSENSUS_SCORE", pd.Series()), errors="coerce") >= 4).sum()
)
gtt_count = (
    int(df["BOTTOM_OUT_STATUS"].isin(["Start GTT", "Start GTT (Basic)"]).sum())
    if "BOTTOM_OUT_STATUS" in df.columns
    else 0
)
new_strat_hits = 0
for col in [
    "STR_VCP_ACTION",
    "STR_TTM_ACTION",
    "STR_SUPERTREND_ACTION",
    "STR_LORENTZIAN_ACTION",
]:
    if col in df.columns:
        new_strat_hits += int(df[col].isin(_BUY_VALS).sum())

k1, k2, k3, k4 = st.columns(4)
for col, icon, label, val, delta in [
    (k1, "🐂", "In Bull Run", bull_count, f"{bull_count/len(df)*100:.1f}% of universe"),
    (k2, "⭐", "High Conviction (≥4)", high_conv, "multi-strategy agree"),
    (k3, "🎯", "GTT Setups", gtt_count, "20D low bounce"),
    (k4, "🆕", "New Strategy Hits", new_strat_hits, "VCP+TTM+ST+ML"),
]:
    col.markdown(
        f"""
    <div class="card">
        <h4>{icon} {label}</h4>
        <div class="val">{val}</div>
        <small style="color:#888">{delta}</small>
    </div>
    """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Main Results Table
# ---------------------------------------------------------------------------
st.subheader(f"📋 Ranked Opportunities — {len(filtered)} stocks")

DISPLAY_COLS_PRIORITY = [
    "SYMBOL",
    "CMP",
    "TREND_STATUS",
    "CAR_RATING",
    "CONSENSUS_SCORE",
    "CONSENSUS_CALLOUT",
    "TECH_SCORE",
    "RSI_14",
    "ATR_14",
    "DELIV_PCT",
    "STR_VCP_ACTION",
    "STR_TTM_ACTION",
    "STR_SUPERTREND_ACTION",
    "STR_LORENTZIAN_ACTION",
    "RSI_DIVERGENCE",
    "MACD_DIVERGENCE",
    "STR_CANDLE_PATTERN",
    "Corp Action",
    "Insider Score",
]
display_cols = [c for c in DISPLAY_COLS_PRIORITY if c in filtered.columns]

if not filtered.empty:
    sort_col = "CONSENSUS_SCORE" if "CONSENSUS_SCORE" in filtered.columns else "CMP"
    filtered_sorted = filtered.sort_values(
        by=sort_col,
        ascending=False,
        key=lambda s: pd.to_numeric(s, errors="coerce").fillna(0),
    )

    def _color_consensus(val):
        try:
            v = int(val)
            if v >= 4:
                return "background-color:#00c27c20; color:#00c27c; font-weight:700"
            if v > 0:
                return "color:#7c83fd"
            if v < 0:
                return "color:#ff5555"
        except Exception:
            pass
        return "color:#888"

    def _color_trend(val):
        if "Bull" in str(val):
            return "color:#00c27c"
        if "Bear" in str(val):
            return "color:#ff5555"
        return ""

    styled = (
        filtered_sorted[display_cols]
        .style.applymap(
            _color_consensus,
            subset=["CONSENSUS_SCORE"] if "CONSENSUS_SCORE" in display_cols else [],
        )
        .applymap(
            _color_trend,
            subset=["TREND_STATUS"] if "TREND_STATUS" in display_cols else [],
        )
        .format(
            {
                "CMP": "₹{:,.2f}",
                "RSI_14": "{:.1f}",
                "ATR_14": "{:.2f}",
                "DELIV_PCT": "{:.1f}%",
                "TECH_SCORE": "{:.1f}",
            },
            na_rep="—",
        )
    )
    st.dataframe(styled, use_container_width=True, height=420)
else:
    st.info("No stocks matched the selected filters.")

# ---------------------------------------------------------------------------
# Optional Export
# ---------------------------------------------------------------------------
with st.expander("📤 Export Results"):
    if st.button("Download Filtered Results as CSV"):
        csv_data = filtered[display_cols].to_csv(index=False)
        st.download_button(
            "⬇ Download CSV",
            data=csv_data,
            file_name=f"signals_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Strategy Heatmap (new section)
# ---------------------------------------------------------------------------
with st.expander("🔥 Strategy Signals Heatmap", expanded=True):
    strat_action_cols = [
        c for c in df.columns if c.startswith("STR_") and c.endswith("_ACTION")
    ]
    if strat_action_cols and not filtered.empty:
        heat_df = filtered[["SYMBOL"] + strat_action_cols].set_index("SYMBOL").head(30)

        # Convert to numeric: 1 = buy, -1 = sell, 0 = neutral
        def _to_num(val):
            if val in _BUY_VALS:
                return 1
            if val in {"Explosive Sell", "Lorentzian Sell"}:
                return -1
            return 0

        heat_num = heat_df.applymap(_to_num)
        heat_num.columns = [
            c.replace("STR_", "").replace("_ACTION", "").replace("_", " ").title()
            for c in heat_num.columns
        ]
        st.dataframe(
            heat_num.style.background_gradient(cmap="RdYlGn", vmin=-1, vmax=1),
            use_container_width=True,
            height=350,
        )
    else:
        st.info("No strategy columns found or no filtered stocks.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Simulated Order Entry
# ---------------------------------------------------------------------------
if not filtered.empty:
    st.subheader("🛒 Simulated Order Entry")
    col1, col2, col3 = st.columns(3)

    with col1:
        buy_sym = st.selectbox("Select Symbol", filtered["SYMBOL"].unique())
        stock_row = filtered[filtered["SYMBOL"] == buy_sym].iloc[0]

    with col2:
        entry_price = float(stock_row.get("CMP", 0.0))
        atr = float(stock_row.get("ATR_14", entry_price * 0.02) or entry_price * 0.02)
        stop_price = round(entry_price - 1.5 * atr, 2)
        target_price = round(entry_price + 3.0 * atr, 2)
        risk_per_trade = st.session_state["portfolio_cash"] * 0.01
        sug_qty = max(1, int(risk_per_trade / max(entry_price - stop_price, 1)))
        qty = st.number_input("Quantity", min_value=1, value=sug_qty)
        st.write(f"**CMP:** ₹{entry_price:,.2f}  ·  **ATR:** ₹{atr:.2f}")

    with col3:
        st.write(f"**Stop Loss:** ₹{stop_price:,.2f}")
        st.write(f"**Target:** ₹{target_price:,.2f}")
        st.write(f"**Order Cost:** ₹{qty*entry_price:,.2f}")
        if "CONSENSUS_CALLOUT" in stock_row.index:
            callout = str(stock_row.get("CONSENSUS_CALLOUT", ""))
            if callout:
                st.caption(f"📊 {callout[:80]}")
        if st.button("Place Simulated BUY"):
            port = Portfolio(initial_cash=st.session_state["portfolio_cash"])
            port.positions = st.session_state["portfolio_positions"]
            sector_name = str(stock_row.get("Sector", "Other"))
            if port.add_position(
                buy_sym, qty, entry_price, stop_price, target_price, sector=sector_name
            ):
                st.session_state["portfolio_cash"] = port.cash
                st.session_state["portfolio_positions"] = port.positions
                st.success(f"✅ Simulated BUY on {buy_sym} placed successfully!")
            else:
                st.error("❌ Insufficient cash or exposure limit breached.")
