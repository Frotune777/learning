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

from datetime import datetime

import pandas as pd
import streamlit as st

from src.scanners.unified_scanner import (
    SCANNER_GROUPS,
    compile_signals_to_dataframe,
    run_unified_scanner,
)

try:
    st.set_page_config(page_title="Unified Grouped Scanner", page_icon="📈", layout="wide")
except Exception:
    pass

# Custom CSS for dark-mode cards
st.markdown(
    """
<style>
.metric-card {
    background: linear-gradient(135deg, #1e2130 0%, #252836 100%);
    border: 1px solid #2d3149;
    border-radius: 12px;
    padding: 18px 22px;
    margin: 6px 0;
}
.metric-card h3 {
    color: #7c83fd;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 0 0 6px 0;
}
.metric-card .value {
    font-size: 2rem;
    font-weight: 700;
    color: #f0f4ff;
    line-height: 1.1;
}
.metric-card .subtext {
    font-size: 0.8rem;
    color: #888;
    margin-top: 4px;
}
</style>
""",
    unsafe_allow_html=True,
)

# Header
st.markdown(
    f"""
<div style="background:linear-gradient(90deg,#1a1d2e,#1e2130);border-bottom:2px solid #7c83fd;
            padding:16px 20px;border-radius:10px;margin-bottom:20px">
  <h2 style="color:#f0f4ff;margin:0">📈 Unified Grouped Scanner</h2>
  <p style="color:#888;margin:4px 0 0">{datetime.now().strftime('%A, %d %b %Y  %H:%M')} &nbsp;·&nbsp; Multi-Strategy Grouped Market Scanners</p>
</div>
""",
    unsafe_allow_html=True,
)

st.sidebar.subheader("🎛 Scanner Controls")

# Group Selection
group_options = ["All", "Bull Trend", "Momentum", "Mean Reversion", "Asset Allocation"]
selected_group = st.sidebar.selectbox("Select Scanner Group", group_options)

run_button = st.sidebar.button("🚀 Run Scanner", use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
**Group Descriptions:**
- **Bull Trend**: Stage 2 Uptrend + Darvas Box Breakouts.
- **Momentum**: Volatility squeezes on key index/sectors.
- **Mean Reversion**: RSI oversold (<35) + cointegration pair trades.
- **Asset Allocation**: liquid sector/commodity ETFs.
"""
)

# Initial execution or reload from file
cache_path = "data/screener_output/unified_signals.csv"
df = pd.DataFrame()

if run_button:
    with st.spinner(f"Running '{selected_group}' scanners (this may take a moment)..."):
        try:
            signals = run_unified_scanner(selected_group)
            df = compile_signals_to_dataframe(signals)
            if not df.empty:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                df.to_csv(cache_path, index=False)
                st.success(f"Successfully generated {len(df)} signals!")
            else:
                st.warning("No signals generated for this group selection.")
        except Exception as exc:
            st.error(f"Scanner Execution Failed: {exc}")
else:
    # Try to load cached results if they exist
    if os.path.exists(cache_path):
        try:
            df = pd.read_csv(cache_path)
            # Filter cached data by selected group
            if selected_group != "All" and not df.empty:
                df = df[df["Scanner Group"] == selected_group].reset_index(drop=True)
        except Exception:
            pass

# KPI Cards Row
c1, c2, c3, c4 = st.columns(4)

def _render_kpi(col, title, value, subtext):
    col.markdown(
        f"""
    <div class="metric-card">
        <h3>{title}</h3>
        <div class="value">{value}</div>
        <div class="subtext">{subtext}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

if not df.empty:
    counts = df.groupby("Scanner Group").size()
    bull_count = counts.get("Bull Trend", 0)
    mom_count = counts.get("Momentum", 0)
    mr_count = counts.get("Mean Reversion", 0)
    aa_count = counts.get("Asset Allocation", 0)
else:
    bull_count = mom_count = mr_count = aa_count = 0

_render_kpi(c1, "🐂 Bullish Signals", str(bull_count), "Stage 2 & Darvas breakouts")
_render_kpi(c2, "⚡ Momentum Squeezes", str(mom_count), "BB inside KC setups")
_render_kpi(c3, "🔄 Mean Reversion", str(mr_count), "RSI oversold & cointegrations")
_render_kpi(c4, "💰 Asset Allocation", str(aa_count), "Turnover-sorted liquid ETFs")

st.markdown("<br>", unsafe_allow_html=True)

# Main results table
st.subheader(f"📋 Scanner Output: {selected_group} Group ({len(df)} signals)")

if not df.empty:
    # Color-coded table style
    def _color_direction(val):
        if val == "BUY":
            return "background-color: #00c27c20; color: #00c27c; font-weight: bold;"
        if val == "SELL":
            return "background-color: #ff555520; color: #ff5555; font-weight: bold;"
        return "color: #888;"

    def _color_group(val):
        colors = {
            "Bull Trend": "color: #00c27c;",
            "Momentum": "color: #7c83fd;",
            "Mean Reversion": "color: #ffc107;",
            "Asset Allocation": "color: #e83e8c;"
        }
        return colors.get(val, "")

    styled = (
        df.style
        .applymap(_color_direction, subset=["Direction"])
        .applymap(_color_group, subset=["Scanner Group"])
    )
    st.dataframe(styled, use_container_width=True, height=450)

    # Export button
    csv_data = df.to_csv(index=False)
    st.download_button(
        "📤 Export Consolidated Signals as CSV",
        data=csv_data,
        file_name=f"unified_signals_{selected_group.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
else:
    st.info("📂 No scanner signals available. Click the **🚀 Run Scanner** button in the sidebar to run the scan.")
