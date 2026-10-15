"""
File: src/dashboard/views/fyers_view.py
Purpose: Data Sources Configuration, Switching, and Live Broker Gateway.
"""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

from src.core.data_sources import DATA_SOURCES, DataSourceManager
from src.nse_bhavcopy.fyers_fetcher import FyersFetcher, exchange_auth_code


def render_fyers_view():
    st.markdown("""
    <div>
        <h2 style="margin:0; font-weight:800; color:#f8fafc;">🔌 Data Sources & Broker Gateway</h2>
        <p style="margin:4px 0 16px; color:#94a3b8; font-size:0.9rem;">
            Configure and toggle active data providers (Fyers, Bhavcopy, Yahoo Finance, NSE Direct) for Historical Sync and Live Streaming.
        </p>
    </div>
    """, unsafe_allow_html=True)

    dsm = DataSourceManager()
    summary = dsm.get_status_summary()

    # Top Status KPI Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Active Historical Source</div>
            <div class="pro-card-value" style="color:#38bdf8; font-size:1.3rem;">{DATA_SOURCES[summary['historical_active']].name}</div>
            <div class="pro-card-sub">Used for parquets & sync</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Active Live Source</div>
            <div class="pro-card-value" style="color:#10b981; font-size:1.3rem;">{DATA_SOURCES[summary['live_active']].name}</div>
            <div class="pro-card-sub">Real-time quotes & ticks</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        fyers_auth = summary["fyers"]["authenticated"]
        f_color = "#10b981" if fyers_auth else "#ef4444"
        f_text = "AUTHENTICATED" if fyers_auth else "NO ACTIVE TOKEN"
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Fyers API Session</div>
            <div class="pro-card-value" style="color:{f_color}; font-size:1.2rem;">{f_text}</div>
            <div class="pro-card-sub">REST v3 Token</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Local Synced Parquets</div>
            <div class="pro-card-value" style="color:#a855f7; font-size:1.3rem;">{summary['parquet_cache']['synced_symbols']} Symbols</div>
            <div class="pro-card-sub">In data/historical/1d/</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    tab_switcher, tab_fyers, tab_live = st.tabs([
        "⚙️ Source Selector & Preferences",
        "🔑 Fyers Broker Login & Token",
        "📡 Live Quotes & Option Chain Probe",
    ])

    with tab_switcher:
        st.markdown("#### Select Active Providers")
        st.caption("Change which provider feeds data without touching code or restarting the app.")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.markdown("##### 📥 Historical Data Source")
            hist_options = [k for k, v in DATA_SOURCES.items() if v.supports_historical]
            curr_hist = summary["historical_active"]
            sel_hist = st.radio(
                "Historical Provider",
                hist_options,
                index=hist_options.index(curr_hist) if curr_hist in hist_options else 0,
                format_func=lambda x: f"{DATA_SOURCES[x].name} — {DATA_SOURCES[x].description[:60]}...",
            )
            if sel_hist != curr_hist:
                dsm.active_historical_source = sel_hist
                st.success(f"Switched active historical data source to **{DATA_SOURCES[sel_hist].name}**!")
                st.rerun()

        with col_s2:
            st.markdown("##### ⚡ Live Market / Quotes Source")
            live_options = [k for k, v in DATA_SOURCES.items() if v.supports_live]
            curr_live = summary["live_active"]
            sel_live = st.radio(
                "Live Provider",
                live_options,
                index=live_options.index(curr_live) if curr_live in live_options else 0,
                format_func=lambda x: f"{DATA_SOURCES[x].name} — {DATA_SOURCES[x].description[:60]}...",
            )
            if sel_live != curr_live:
                dsm.active_live_source = sel_live
                st.success(f"Switched active live source to **{DATA_SOURCES[sel_live].name}**!")
                st.rerun()

        st.markdown("---")
        st.markdown("##### Comparison Matrix")
        matrix_rows = []
        for k, spec in DATA_SOURCES.items():
            matrix_rows.append({
                "Source ID": spec.id,
                "Name": spec.name,
                "Category": spec.category.upper(),
                "Historical OHLCV": "✅ Yes" if spec.supports_historical else "❌ No",
                "Live Streaming": "✅ Yes" if spec.supports_live else "❌ No",
                "Requires Account": "⚠️ Yes (API Key)" if spec.requires_auth else "🟢 Free / Public",
                "Description": spec.description,
            })
        st.dataframe(pd.DataFrame(matrix_rows), use_container_width=True, hide_index=True)

    with tab_fyers:
        fetcher = FyersFetcher()
        app_id = os.getenv("BROKER_API_KEY") or os.getenv("FYERS_API_KEY")
        app_secret = os.getenv("BROKER_API_SECRET") or os.getenv("FYERS_API_SECRET")
        redirect_uri = os.getenv("FYERS_REDIRECT_URI", "https://trade.fyers.in/api-login/redirect-uri/index.html")

        token_valid = False
        profile_data: dict = {}

        if fetcher.access_token and app_id:
            headers = {"Authorization": f"{app_id}:{fetcher.access_token}"}
            try:
                resp = requests.get("https://api-t1.fyers.in/api/v3/profile", headers=headers, timeout=5)
                if resp.status_code == 200:
                    res_json = resp.json()
                    if res_json.get("s") == "ok":
                        token_valid = True
                        profile_data = res_json.get("data", {})
            except Exception:
                pass

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### Step 1: Open Broker Login")
            st.write("Fyers requires a fresh auth session each morning.")
            if app_id:
                st.link_button("🌐 Open Fyers Daily Login Portal", fetcher.login_url(redirect_uri=redirect_uri), use_container_width=True)
                st.info("Log in with your Mobile & PIN. Copy the `auth_code=...` parameter from the redirected URL.")
            else:
                st.error("Missing BROKER_API_KEY / FYERS_API_KEY in .env")

        with col_r:
            st.markdown("#### Step 2: Exchange Auth Code")
            code_in = st.text_input("Paste Auth Code", type="password", placeholder="Paste code from address bar...")
            if st.button("Exchange & Save Token", use_container_width=True, type="primary"):
                if code_in.strip() and app_id and app_secret:
                    token = exchange_auth_code(code_in.strip(), app_id, app_secret)
                    if token:
                        fetcher.set_token(token)
                        st.success("Fyers session successfully activated!")
                        st.rerun()
                    else:
                        st.error("Exchange failed. Auth code may be expired.")

        if token_valid:
            st.success(f"Logged in as **{profile_data.get('name', 'User')}** (`{profile_data.get('fy_id', '')}`) | Email: `{profile_data.get('email_id', '')}`")

    with tab_live:
        st.markdown("#### Live Market Probing")
        fetcher = dsm.get_price_fetcher()
        t1, t2 = st.tabs(["Option Chain (Fyers)", "Real-Time Equity Quotes"])
        with t1:
            if isinstance(fetcher, FyersFetcher) and fetcher.access_token:
                sym_in = st.text_input("Index / Equity Symbol", value="NSE:NIFTY50-INDEX")
                if st.button("Query Option Chain", use_container_width=True):
                    data = fetcher.get_option_chain(symbol=sym_in, strike_count=8)
                    if data and "optionsChain" in data:
                        raw = [x for x in data["optionsChain"] if x.get("strike_price", -1) > 0]
                        st.dataframe(pd.DataFrame(raw)[["symbol", "strike_price", "option_type", "ltp", "oi", "volume"]], use_container_width=True)
            else:
                st.info("Option chain requires active Fyers broker session. Configure in 'Fyers Broker Login & Token' tab.")

        with t2:
            stocks = st.text_input("Tickers (comma separated)", value="RELIANCE, TCS, INFY, HDFCBANK")
            if st.button("Fetch Real-Time Quotes"):
                syms = [s.strip().upper() for s in stocks.split(",") if s.strip()]
                if hasattr(fetcher, "get_quotes"):
                    st.json(fetcher.get_quotes(syms))
                else:
                    st.info(f"Quotes fetcher for {fetcher.__class__.__name__} streaming simulation.")
