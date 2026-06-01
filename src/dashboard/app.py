import sys
import os
# Force project root into sys.path to resolve ModuleNotFoundError
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.." if os.path.basename(os.path.dirname(__file__)) == "dashboard" else "../../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

"""
File: src/dashboard/app.py
Purpose: Main landing page — Sharegenius Quantitative Platform.
         Upgraded to screeni-py-level GUI with dark-mode metrics, system status,
         live data cards, and premium layout.
Last Modified: 2026-06-01
"""

import glob
import os
import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Sharegenius — NSE Quantitative Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — dark-mode premium styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Dark-mode card panels */
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
.metric-card .delta {
    font-size: 0.8rem;
    margin-top: 4px;
}
.delta-positive { color: #00c27c; }
.delta-negative { color: #ff5555; }
.delta-neutral  { color: #888; }

/* Status badges */
.badge-ok   { background:#00c27c20; color:#00c27c; border:1px solid #00c27c40; border-radius:6px; padding:3px 10px; font-size:0.78rem; }
.badge-warn { background:#ffc10720; color:#ffc107; border:1px solid #ffc10740; border-radius:6px; padding:3px 10px; font-size:0.78rem; }
.badge-err  { background:#ff555520; color:#ff5555; border:1px solid #ff555540; border-radius:6px; padding:3px 10px; font-size:0.78rem; }

/* Header bar */
.hero-header {
    background: linear-gradient(90deg, #1a1d2e 0%, #1e2130 60%, #181c2d 100%);
    border-bottom: 2px solid #7c83fd;
    padding: 20px 24px;
    border-radius: 12px;
    margin-bottom: 24px;
}
.hero-title { font-size:1.8rem; font-weight:800; color:#f0f4ff; margin:0; }
.hero-sub   { font-size:0.9rem; color:#888; margin:4px 0 0 0; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Hero Header
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="hero-header">
  <p class="hero-title">📈 Sharegenius Quantitative Platform</p>
  <p class="hero-sub">NSE Equity Screener · 13-Strategy Engine · Consensus Scoring · Parquet Data Lake · {datetime.now().strftime('%A, %d %b %Y  %H:%M')}</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# System Status — data discovery
# ---------------------------------------------------------------------------
hist_dir     = "data/historical/1d"
processed_dir = "data/processed"

parquets      = glob.glob(os.path.join(hist_dir, "*.parquet"))
bhavs         = sorted(glob.glob(os.path.join(processed_dir, "top_250_*.csv")))
analyzed      = sorted(glob.glob(os.path.join(processed_dir, "top_250_analyzed_*.csv")))

latest_bhav    = os.path.basename(bhavs[-1]).replace("top_250_","").replace(".csv","") if bhavs else "—"
latest_analyzed = os.path.basename(analyzed[-1]) if analyzed else "—"

st.session_state.setdefault("portfolio_cash", 500_000.0)
st.session_state.setdefault("portfolio_positions", {})

# ---------------------------------------------------------------------------
# Metric Cards Row
# ---------------------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)

def _card(col, icon, label, value, delta_html=""):
    col.markdown(f"""
    <div class="metric-card">
        <h3>{icon} {label}</h3>
        <div class="value">{value}</div>
        {f'<div class="delta">{delta_html}</div>' if delta_html else ''}
    </div>
    """, unsafe_allow_html=True)

_card(c1, "🗄", "Synced Symbols",   str(len(parquets)))
_card(c2, "📅", "Latest Bhavcopy",  latest_bhav)
_card(c3, "🔍", "Last Analysis",    latest_analyzed[:12] if latest_analyzed != "—" else "—")
_card(c4, "💼", "Active Positions",  str(len(st.session_state["portfolio_positions"])))
_card(c5, "💰", "Portfolio Cash",   f"₹{st.session_state['portfolio_cash']:,.0f}")

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Two-column layout
# ---------------------------------------------------------------------------
left, right = st.columns([3, 2])

with left:
    st.subheader("🧠 Platform Overview")
    st.markdown("""
    This platform integrates **official NSE Bhavcopy ZIP feeds** and **Fyers historical API**
    with a 13-strategy technical engine, ML-powered Lorentzian classifier, and multi-factor
    consensus scoring.

    | Layer | Details |
    |---|---|
    | **Data Source** | NSE Bhavcopy ZIPs + Fyers API |
    | **Universe** | Top 250 by turnover (daily) |
    | **Strategies** | 13 (VCP, TTM, Supertrend, Lorentzian ML, RDX, +8 more) |
    | **Scoring** | Consensus vote across all 13 strategies |
    | **Output** | Analyzed CSV + Rich CLI tables + this dashboard |
    """)

    # Strategy Signals Preview (from latest analyzed)
    if analyzed:
        st.subheader("📊 Latest Strategy Signal Summary")
        df = pd.read_csv(analyzed[-1])
        strat_cols = [c for c in df.columns if c.startswith("STR_") and c.endswith("_ACTION")]
        if strat_cols:
            buy_counts = {}
            for col in strat_cols:
                name = col.replace("STR_", "").replace("_ACTION", "").replace("_", " ").title()
                buy_counts[name] = (df[col].isin([
                    "Buy","Breakout Buy","Explosive Buy","Level 1 Buy","Level 2 Buy","Level 3 Buy",
                    "150 DMA Breakout | CMP > 200 DMA","50 DMA Breakout | CMP > 200 DMA",
                    "Super BO Buy","Buy on Support / Demand Level","Buy (55D Breakout)",
                    "VCP Tightening","Squeeze Active (Bullish)","Long Entry","Lorentzian Buy",
                ])).sum()
            bar_df = pd.DataFrame.from_dict(buy_counts, orient="index", columns=["Buy Signals"])
            bar_df = bar_df.sort_values("Buy Signals", ascending=False)
            st.bar_chart(bar_df)
    else:
        st.info("📂 No analyzed data found yet. Run `uv run main.py` → option **4** to screen stocks.")

with right:
    st.subheader("🚦 System Status")

    def _status_row(label, ok, detail=""):
        badge = '<span class="badge-ok">✅ OK</span>' if ok else '<span class="badge-err">❌ MISSING</span>'
        st.markdown(f"**{label}** {badge}  \n<small style='color:#888'>{detail}</small>", unsafe_allow_html=True)

    _status_row("Historical Parquets",   len(parquets) > 0, f"{len(parquets)} symbols cached")
    _status_row("Bhavcopy CSVs",         len(bhavs) > 0,    f"{len(bhavs)} files found")
    _status_row("Analyzed Output",       len(analyzed) > 0,  latest_analyzed)
    _status_row("Portfolio State",       True, f"{len(st.session_state['portfolio_positions'])} positions")

    st.markdown("---")
    st.subheader("⚡ Quick Start")
    st.markdown("""
```bash
# 1. Sync latest Bhavcopy (21 option)
uv run main.py

# 2. Run screener (option 4)
uv run main.py screen

# 3. Launch dashboard
uv run streamlit run src/dashboard/app.py
```
    """)

    st.warning("⚠️ **Simulation Only** — No real orders placed. Fyers used for data only.")
