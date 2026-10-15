"""
File: src/dashboard/app.py
Purpose: Sharegenius Quantitative Platform — Institutional Single-Page Dashboard.
Features:
  - Top Horizontal Header Navigation (No clumsy left sidebar).
  - Modern Glassmorphism Styling, Inter Typography & Dark Terminal Aesthetics.
  - Complete feature suite: SMC Studio, Multi-Strategy Screener, Portfolio Risk Manager,
    Strategy Backtesting, Quantitative Intelligence, and Fyers Broker Gateway.
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
        page_title="Sharegenius — Institutional Trading Terminal",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
except Exception:
    pass

from src.dashboard.theme import CSS_THEME, NAV_STYLES
from src.dashboard.views.smc_view import render_smc_view
from src.dashboard.views.screener_view import render_screener_view
from src.dashboard.views.portfolio_view import render_portfolio_view
from src.dashboard.views.backtest_view import render_backtest_view
from src.dashboard.views.quantitative_view import render_quantitative_view
from src.dashboard.views.fyers_view import render_fyers_view

# 1. Inject Premium Theme CSS
st.markdown(CSS_THEME, unsafe_allow_html=True)

# 2. Top Application Brand Bar
st.markdown("""
<div class="top-brand-bar">
    <div class="brand-title">
        <span>⚡ SHAREGENIUS</span>
        <span class="brand-badge">INSTITUTIONAL QUANT</span>
    </div>
    <div style="display:flex; align-items:center; gap:16px;">
        <span style="font-size:0.8rem; color:#94a3b8;"><span style="color:#10b981;">●</span> LIVE SYSTEM READY</span>
        <span style="font-size:0.8rem; color:#64748b; font-family:'JetBrains Mono', monospace;">NSE PIPELINE v3</span>
    </div>
</div>
""", unsafe_allow_html=True)

# 3. Top Horizontal Menu (Replacing Clumsy Sidebar)
selected_tab = option_menu(
    menu_title=None,
    options=[
        "SMC Studio",
        "Technical Screener",
        "Portfolio Risk",
        "Backtest Explorer",
        "Quantitative / Macro",
        "Data Sources & Gateway",
    ],
    icons=[
        "crosshair",
        "funnel",
        "briefcase",
        "graph-down",
        "pie-chart",
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
elif selected_tab == "Data Sources & Gateway":
    render_fyers_view()

