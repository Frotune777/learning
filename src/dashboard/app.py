"""
File: src/dashboard/app.py
Purpose: Sharegenius Quantitative Platform — Institutional Single-Page Dashboard.
Features:
  - Top Horizontal Header Navigation (No clumsy left sidebar).
  - Modern Glassmorphism Styling, Inter Typography & Dark Terminal Aesthetics.
  - Complete feature suite: SMC Studio, Multi-Strategy Screener, Portfolio Risk Manager,
    Strategy Backtesting, Quantitative Intelligence, Data Quality Gate, LLM Dossier,
    and Fyers Broker Gateway.
"""

from __future__ import annotations

import os
import sys

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
from streamlit_option_menu import option_menu

try:
    st.set_page_config(
        page_title="Fortune Analytical Decision-Support System",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
except Exception:
    pass

from src.core.config import get_stored_data_info
from src.dashboard.theme import CSS_THEME, NAV_STYLES
from src.dashboard.views.backtest_view import render_backtest_view
from src.dashboard.views.dossier_view import render_dossier_view
from src.dashboard.views.dq_view import render_dq_view
from src.dashboard.views.fyers_view import render_fyers_view
from src.dashboard.views.portfolio_view import render_portfolio_view
from src.dashboard.views.quantitative_view import render_quantitative_view
from src.dashboard.views.screener_view import render_screener_view
from src.dashboard.views.smc_view import render_smc_view

# 1. Inject Premium Theme CSS
st.markdown(CSS_THEME, unsafe_allow_html=True)

# 2. Check Local Data Lake Status
data_info = get_stored_data_info("data/historical/1d")
stored_date = data_info.get("latest_date") or "None"
n_symbols = data_info.get("symbol_count", 0)
days_behind = data_info.get("days_behind", 0)

# Initialize Session State Mode
if "data_mode" not in st.session_state:
    st.session_state["data_mode"] = "OFFLINE"

# 3. Top Application Brand Bar
st.markdown(f"""
<div class="top-brand-bar">
    <div class="brand-title">
        <span>⚡ FORTUNE ADSS</span>
        <span class="brand-badge">DECISION-SUPPORT</span>
    </div>
    <div style="display:flex; align-items:center; gap:16px;">
        <span style="font-size:0.8rem; color:#94a3b8;">
            <span style="color:#10b981;">●</span> MODE: <strong>{st.session_state['data_mode']}</strong> · Stored Through: <strong>{stored_date}</strong> ({n_symbols} symbols)
        </span>
        <span style="font-size:0.8rem; color:#64748b; font-family:'JetBrains Mono', monospace;">FORTUNE v3.2</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Mode & Data Refresh Control Sub-bar
col_ctl1, col_ctl2, col_spacer = st.columns([1.5, 1.5, 5])
with col_ctl1:
    mode_toggle = st.segmented_control(
        "Operating Mode",
        options=["📁 Stored Data (Offline)", "🔴 Live Data"],
        default="📁 Stored Data (Offline)",
        label_visibility="collapsed",
    )
    st.session_state["data_mode"] = "OFFLINE" if "Offline" in (mode_toggle or "") else "LIVE"

with col_ctl2:
    if st.button("🔄 Pull New Data (Cascade)", help="1st YFinance → 2nd Fyers → 3rd NSE Charting"):
        with st.spinner("Initiating 3-tier sync fallback..."):
            from src.storage.historical_sync import HistoricalSync
            hs = HistoricalSync(timeframe="1d")
            st.info("Sync started. You can also run full batch sync via CLI: `python main.py sync-history`.")


# 3. Top Horizontal Menu (Replacing Clumsy Sidebar)
selected_tab = option_menu(
    menu_title=None,
    options=[
        "SMC Studio",
        "Technical Screener",
        "Portfolio Risk",
        "Backtest Explorer",
        "Quantitative / Macro",
        "Data Quality",
        "LLM Dossier",
        "Data Sources & Gateway",
    ],
    icons=[
        "crosshair",
        "funnel",
        "briefcase",
        "graph-down",
        "pie-chart",
        "shield-check",
        "file-text",
        "database-gear",
    ],
    menu_icon="cast",
    default_index=0,
    orientation="horizontal",
    styles=NAV_STYLES,
)

# 4. View Router
if selected_tab == "SMC Studio":
    render_smc_view()
elif selected_tab == "Technical Screener":
    render_screener_view()
elif selected_tab == "Portfolio Risk":
    render_portfolio_view()
elif selected_tab == "Backtest Explorer":
    render_backtest_view()
elif selected_tab == "Quantitative / Macro":
    render_quantitative_view()
elif selected_tab == "Data Quality":
    render_dq_view()
elif selected_tab == "LLM Dossier":
    render_dossier_view()
elif selected_tab == "Data Sources & Gateway":
    render_fyers_view()
