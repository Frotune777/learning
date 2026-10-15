"""
File: src/dashboard/pages/07_fyers_auth.py
Purpose: GUI for Fyers authentication, token generation, live API testing, and status.
"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from src.nse_bhavcopy.fyers_fetcher import FyersFetcher, exchange_auth_code

load_dotenv()

try:
    st.set_page_config(
    page_title="Fyers Account & Auth — Sharegenius",
    page_icon="🔑",
    layout="wide",
)
except Exception:
    pass

st.title("🔑 Fyers Broker Gateway & Authentication")
st.caption("Manage your daily Fyers API v3 token lifecycle, test live connections, and stream options & quotes.")

fetcher = FyersFetcher()

app_id = os.getenv("BROKER_API_KEY") or os.getenv("FYERS_API_KEY")
app_secret = os.getenv("BROKER_API_SECRET") or os.getenv("FYERS_API_SECRET")
redirect_uri = os.getenv("FYERS_REDIRECT_URI", "https://trade.fyers.in/api-login/redirect-uri/index.html")

# ---------------------------------------------------------------------------
# Section 1: Connection Health & Profile
# ---------------------------------------------------------------------------
st.subheader("1. Connection Health")

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
    except Exception as exc:
        st.warning(f"Error checking profile: {exc}")

col1, col2, col3, col4 = st.columns(4)
with col1:
    if token_valid:
        st.success("🟢 Active & Connected")
    else:
        st.error("🔴 Expired / Disconnected")

with col2:
    st.metric("Client ID", profile_data.get("fy_id", "Not Logged In"))

with col3:
    st.metric("Name", profile_data.get("name", "N/A"))

with col4:
    cache_path = "data/cache/fyers_token.txt"
    if os.path.exists(cache_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(cache_path)).strftime("%Y-%m-%d %H:%M")
        st.metric("Token Cached At", mtime)
    else:
        st.metric("Token Cache", "No File")

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 2: Daily Login & Token Exchange GUI
# ---------------------------------------------------------------------------
left_col, right_col = st.columns(2)

with left_col:
    st.subheader("2. Step A: Generate Login URL")
    st.write("Fyers requires a daily login to issue a fresh access token.")
    
    if app_id:
        login_url = fetcher.login_url(redirect_uri=redirect_uri)
        st.link_button("🌐 Open Fyers Login Portal", login_url, use_container_width=True)
        st.info(
            "1. Click the button above to login.\n"
            "2. Complete Mobile OTP / PIN verification.\n"
            "3. You will be redirected to a page showing `?auth_code=...` in your address bar."
        )
    else:
        st.error("Missing `BROKER_API_KEY` in `.env` file.")

with right_col:
    st.subheader("3. Step B: Paste Auth Code or Direct Token")
    
    tab_code, tab_direct = st.tabs(["Exchange Auth Code", "Direct Token Paste"])
    
    with tab_code:
        auth_code_input = st.text_input(
            "Paste `auth_code` from redirect URL:",
            placeholder="eyJ0eXAiOiJKV1QiLC...",
            type="password",
        )
        if st.button("🚀 Exchange & Save Token", use_container_width=True, type="primary"):
            if not auth_code_input:
                st.warning("Please paste the auth code.")
            elif not app_id or not app_secret:
                st.error("Missing BROKER_API_KEY or BROKER_API_SECRET in .env")
            else:
                with st.spinner("Exchanging auth code with Fyers..."):
                    token = exchange_auth_code(auth_code_input.strip(), app_id, app_secret)
                    if token:
                        fetcher.set_token(token)
                        st.success("✅ Fyers Access Token acquired and saved to cache!")
                        st.rerun()
                    else:
                        st.error("Failed to exchange code. Verify the auth code hasn't expired.")
                        
    with tab_direct:
        manual_token = st.text_area(
            "Or paste full Access Token directly:",
            placeholder="eyJhbGciOiJIUzI1NiIs...",
            height=100,
        )
        if st.button("💾 Save Direct Token", use_container_width=True):
            if manual_token.strip():
                fetcher.set_token(manual_token.strip())
                st.success("Token saved!")
                st.rerun()

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 3: Live Data Probe (Zero MCP)
# ---------------------------------------------------------------------------
st.subheader("4. Live Data Probe (Verify without MCP)")

if token_valid:
    test_tab1, test_tab2 = st.tabs(["Option Chain Probe", "Live Equity Quotes"])
    
    with test_tab1:
        c_sym, c_strikes, c_btn = st.columns([2, 1, 1])
        with c_sym:
            opt_symbol = st.text_input("Underlying Symbol", value="NSE:NIFTY50-INDEX")
        with c_strikes:
            strikes = st.number_input("Strike Count", min_value=2, max_value=25, value=5)
        with c_btn:
            st.write("")
            st.write("")
            probe_opt = st.button("Fetch Live Option Chain")

        if probe_opt:
            with st.spinner("Fetching option chain from Fyers..."):
                oc = fetcher.get_option_chain(symbol=opt_symbol, strike_count=strikes)
                if oc and "optionsChain" in oc:
                    st.success("Data fetched successfully!")
                    raw_chain = [x for x in oc["optionsChain"] if x.get("strike_price", -1) > 0]
                    df_oc = pd.DataFrame(raw_chain)[["symbol", "strike_price", "option_type", "ltp", "oi", "volume"]]
                    st.dataframe(df_oc, use_container_width=True)
                else:
                    st.warning("No data returned or error response from Fyers.")
                    
    with test_tab2:
        stocks_input = st.text_input("Test Stocks (comma-separated)", value="RELIANCE, TCS, INFY, HDFCBANK")
        if st.button("Fetch Live Quotes"):
            syms = [s.strip().upper() for s in stocks_input.split(",") if s.strip()]
            quotes = fetcher.get_quotes(syms)
            st.json(quotes)
else:
    st.info("Log in above to test live option chains and equity quotes directly in Streamlit.")
