"""
File: src/dashboard/pages/04_strategy_inspector.py
Purpose: Render Strategy Inspector and Consensus Leaderboard for stock signals.

Dependencies:
    External:
        - streamlit==1.40.0: Render interactive web application components
        - pandas==2.2.3: Load and display data summaries
    Internal:
        - src.core.consensus_engine: Recalculate consensus scores
        - src.cli.reporter: Generate text-based quant narratives

Key Components:
    Classes:
        - None
    Functions:
        - None

Last Modified: 2026-06-17
Modified By: [Fortune]

Open Tasks:
    - [ ] [MEDIUM] Improve layout of strategy signal metrics

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

st.set_page_config(
    page_title="Strategy Inspector",
    page_icon="🔬",
    layout="wide",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
.hero { background:linear-gradient(90deg,#1a1d2e,#1e2130);border-bottom:2px solid #7c83fd;
        padding:16px 20px;border-radius:10px;margin-bottom:20px; }
.hero h2 { color:#f0f4ff;margin:0; }
.hero p  { color:#888;margin:4px 0 0; }

.card { background:linear-gradient(135deg,#1e2130,#252836);
        border:1px solid #2d3149;border-radius:10px;padding:14px 18px;margin:4px 0; }
.card h4 { color:#7c83fd;font-size:.78rem;text-transform:uppercase;margin:0 0 4px;letter-spacing:.08em; }
.card .val { font-size:1.4rem;font-weight:700;color:#f0f4ff; }

.signal-buy  { color:#00c27c;font-weight:700; }
.signal-sell { color:#ff5555;font-weight:700; }
.signal-hold { color:#888; }

.badge-buy  { background:#00c27c20;color:#00c27c;border:1px solid #00c27c40;border-radius:5px;padding:2px 9px;font-size:.75rem; }
.badge-sell { background:#ff555520;color:#ff5555;border:1px solid #ff555540;border-radius:5px;padding:2px 9px;font-size:.75rem; }
.badge-hold { background:#88888815;color:#888;border:1px solid #88888830;border-radius:5px;padding:2px 9px;font-size:.75rem; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <h2>🔬 Strategy Inspector & Consensus Leaderboard</h2>
  <p>All 13 strategy signals per stock · color-coded badges · AI narrative · consensus rankings</p>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
processed_dir = "data/processed"
analyzed_files = sorted(
    glob.glob(os.path.join(processed_dir, "top_250_analyzed_*.csv"))
)

if not analyzed_files:
    st.error(
        "❌ No analyzed data found. Run the Technical Screener (CLI option 4) first."
    )
    st.stop()

selected_file = st.sidebar.selectbox(
    "📂 Dataset",
    [os.path.basename(f) for f in analyzed_files],
    index=len(analyzed_files) - 1,
)
df = pd.read_csv(
    next(f for f in analyzed_files if os.path.basename(f) == selected_file)
)

# Add/recalculate consensus & decision support if missing
if (
    "CONSENSUS_SCORE" not in df.columns
    or "WEIGHTED_BULL_SCORE" not in df.columns
    or "MARKET_STATE" not in df.columns
):
    try:
        from src.core.consensus_engine import add_consensus_score

        df = add_consensus_score(df)
    except Exception:
        df["CONSENSUS_SCORE"] = 0
        df["CONSENSUS_CALLOUT"] = "N/A"
        df["WEIGHTED_BULL_SCORE"] = 0.0
        df["WEIGHTED_BEAR_SCORE"] = 0.0
        df["MARKET_STATE"] = "SIDEWAYS"
        df["PORTFOLIO_ACTION"] = "NEUTRAL"
        df["CONFIDENCE_PCT"] = 50.0

st.sidebar.success(f"✅ {len(df)} stocks loaded")

# ---------------------------------------------------------------------------
# Buy / Sell signal sets (must match consensus_engine.py)
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
_SELL_VALS = {"Explosive Sell", "Lorentzian Sell"}

STRATEGY_MAP = {
    "Nifty Shop": "STR_NIFTY_SHOP_ACTION",
    "Buy Low Sell High": "STR_BUY_LOW_ACTION",
    "Turtle Trading": "STR_TURTLE_ACTION",
    "RDX": "STR_RDX_ACTION",
    "100 SMA Breakout": "STR_100SMA_ACTION",
    "ETF Shop": "STR_ETF_SHOP_ACTION",
    "Super BO": "STR_SUPER_BO_ACTION",
    "DMA Reverse": "STR_DMA_REV_ACTION",
    "DMA No-SL": "STR_DMA_NOSL_ACTION",
    "VCP (Minervini)": "STR_VCP_ACTION",
    "TTM Squeeze": "STR_TTM_ACTION",
    "Dual Supertrend": "STR_SUPERTREND_ACTION",
    "Lorentzian ML": "STR_LORENTZIAN_ACTION",
}

# ---------------------------------------------------------------------------
# Tabs: Leaderboard | Inspector
# ---------------------------------------------------------------------------
tab_lead, tab_insp = st.tabs(["⭐ Consensus Leaderboard", "🔬 Single-Stock Inspector"])

# ======================================================================
# TAB 1 — Consensus Leaderboard
# ======================================================================
with tab_lead:
    st.subheader("⭐ Stocks Ranked by Multi-Strategy Consensus")

    min_score = st.slider("Minimum Consensus Score", 0, 13, 1)

    ranked = df.copy()
    ranked["CONSENSUS_SCORE"] = pd.to_numeric(
        ranked.get("CONSENSUS_SCORE", 0), errors="coerce"
    ).fillna(0)
    ranked = ranked[ranked["CONSENSUS_SCORE"] >= min_score].sort_values(
        "CONSENSUS_SCORE", ascending=False
    )

    if ranked.empty:
        st.info("No stocks meet the minimum consensus score.")
    else:
        # Build display table
        strat_cols_present = [
            col for col in STRATEGY_MAP.values() if col in ranked.columns
        ]
        disp = ranked[
            ["SYMBOL"]
            + strat_cols_present
            + [
                c
                for c in [
                    "CONSENSUS_SCORE",
                    "WEIGHTED_BULL_SCORE",
                    "WEIGHTED_BEAR_SCORE",
                    "MARKET_STATE",
                    "PORTFOLIO_ACTION",
                    "CONFIDENCE_PCT",
                    "CMP",
                    "TREND_STATUS",
                    "RSI_14",
                    "TECH_SCORE",
                ]
                if c in ranked.columns
            ]
        ].head(50)

        # Color-code strategy action cells
        def _strat_color(val):
            if val in _BUY_VALS:
                return "background-color:#00c27c18;color:#00c27c;font-weight:600"
            if val in _SELL_VALS:
                return "background-color:#ff555518;color:#ff5555;font-weight:600"
            return "color:#555"

        styled = (
            disp.style.applymap(
                _strat_color,
                subset=[c for c in strat_cols_present if c in disp.columns],
            )
            .applymap(
                lambda v: "background-color:#00c27c20;color:#00c27c;font-weight:700"
                if isinstance(v, (int, float)) and v >= 4
                else "color:#7c83fd;font-weight:600"
                if isinstance(v, (int, float)) and v > 0
                else "color:#888",
                subset=["CONSENSUS_SCORE"] if "CONSENSUS_SCORE" in disp.columns else [],
            )
            .format(
                {
                    "CMP": "₹{:,.2f}",
                    "RSI_14": "{:.1f}",
                    "TECH_SCORE": "{:.1f}",
                    "CONSENSUS_SCORE": "{:.0f}",
                    "WEIGHTED_BULL_SCORE": "{:.1f}/10",
                    "WEIGHTED_BEAR_SCORE": "{:.1f}/10",
                    "CONFIDENCE_PCT": "{:.1f}%",
                },
                na_rep="—",
            )
        )

        st.dataframe(styled, use_container_width=True, height=500)

        # Bar chart: consensus score distribution
        st.markdown("---")
        st.subheader("📊 Consensus Score Distribution")
        score_dist = ranked["CONSENSUS_SCORE"].value_counts().sort_index()
        st.bar_chart(score_dist)

        # Optional export
        with st.expander("📤 Export Leaderboard"):
            if st.button("Download Leaderboard CSV"):
                st.download_button(
                    "⬇ Download",
                    data=ranked.to_csv(index=False),
                    file_name=f"leaderboard_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                )

# ======================================================================
# TAB 2 — Single-Stock Inspector
# ======================================================================
with tab_insp:
    st.subheader("🔬 Deep-Dive: All 13 Strategies for One Stock")

    symbols = sorted(df["SYMBOL"].dropna().unique().tolist())
    symbol = st.selectbox("Select Stock", symbols)

    row = (
        df[df["SYMBOL"] == symbol].iloc[0]
        if not df[df["SYMBOL"] == symbol].empty
        else None
    )
    if row is None:
        st.warning(f"Symbol '{symbol}' not found in dataset.")
        st.stop()

    # KPI row
    cmp_val = row.get("CMP", float("nan"))
    rsi_val = row.get("RSI_14", float("nan"))
    cons = row.get("CONSENSUS_SCORE", 0)
    tech = row.get("TECH_SCORE", float("nan"))
    trend = str(row.get("TREND_STATUS", "—"))

    st.markdown("#### 📋 Core Indicators")
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    dq_cov = row.get("DQ_COVERAGE_PCT", 100.0)
    dq_stat = str(row.get("DQ_HEALTH_STATUS", "HEALTHY"))
    dq_color = (
        "#00c27c"
        if dq_stat == "HEALTHY"
        else "#ffaa00"
        if dq_stat in ("LOW_COVERAGE", "ZERO_VOLUME", "ZERO_CLOSE")
        else "#ff5555"
    )

    for col, icon, label, val in [
        (k1, "💰", "CMP", f"₹{cmp_val:,.2f}" if pd.notna(cmp_val) else "—"),
        (k2, "📡", "RSI (14)", f"{rsi_val:.1f}" if pd.notna(rsi_val) else "—"),
        (k3, "⭐", "Consensus", str(int(cons)) + " / 13"),
        (k4, "📊", "TA Score", f"{float(tech):.1f}/10" if pd.notna(tech) else "—"),
        (k5, "📈", "Trend", trend),
        (k6, "📋", "Data Quality", f"{dq_cov:.1f}% ({dq_stat})"),
    ]:
        card_val_color = dq_color if label == "Data Quality" else "#f0f4ff"
        card_val_size = (
            "1.02rem" if label == "Data Quality" and len(val) > 12 else "1.4rem"
        )
        col.markdown(
            f"""
        <div class="card" style="border-bottom: 2px solid {dq_color if label == 'Data Quality' else 'transparent'}">
            <h4>{icon} {label}</h4>
            <div class="val" style="color: {card_val_color}; font-size: {card_val_size}">{val}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # 🤖 QUANT DECISION SUPPORT SYSTEM ROW
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🤖 Quant Decision Support System")

    # Extract decision fields
    m_state = row.get("MARKET_STATE", "SIDEWAYS")
    p_action = row.get("PORTFOLIO_ACTION", "NEUTRAL / SIDEWAYS")
    conf = row.get("CONFIDENCE_PCT", 50.0)
    w_bull = row.get("WEIGHTED_BULL_SCORE", 0.0)
    w_bear = row.get("WEIGHTED_BEAR_SCORE", 0.0)

    # Pricing for stops/targets
    stop_price = row.get("STOP_PRICE")
    target_20pct = row.get("GTT_TARGET_20PCT") or (
        cmp_val * 1.2 if pd.notna(cmp_val) else None
    )
    suggested_qty = row.get("SUGGESTED_QTY")

    stop_str = f"₹{stop_price:,.2f}" if pd.notna(stop_price) and stop_price > 0 else "—"
    target_str = (
        f"₹{target_20pct:,.2f}" if pd.notna(target_20pct) and target_20pct > 0 else "—"
    )
    qty_str = (
        str(int(suggested_qty))
        if pd.notna(suggested_qty) and suggested_qty > 0
        else "—"
    )

    # Dynamic colors for action
    action_color = (
        "#00c27c"
        if "BUY" in p_action
        else "#ff5555"
        if "EXIT" in p_action or "REDUCE" in p_action
        else "#888"
    )
    state_icon = (
        "📈"
        if m_state == "BULL RUN"
        else "🔄"
        if m_state == "RECOVERY"
        else "📉"
        if m_state == "BEAR TERRITORY"
        else "↕"
    )

    da1, da2, da3, da4 = st.columns(4)

    da1.markdown(
        f"""
    <div class="card" style="border-left: 5px solid {action_color}">
        <h4>🚦 Simulated Action</h4>
        <div class="val" style="color: {action_color}">{p_action}</div>
        <div style="font-size: 0.8rem; color: #888; margin-top: 4px;">Confidence: {conf}%</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    da2.markdown(
        f"""
    <div class="card">
        <h4>🏁 Market State</h4>
        <div class="val">{state_icon} {m_state}</div>
        <div style="font-size: 0.8rem; color: #888; margin-top: 4px;">Trend Classification</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    da3.markdown(
        f"""
    <div class="card">
        <h4>📊 Weighted Scores</h4>
        <div class="val">{w_bull:.1f} / 10 <span style="font-size:0.9rem; color:#888;">(Bull)</span></div>
        <div style="font-size: 0.8rem; color: #ff5555; margin-top: 4px;">Bear Score: {w_bear:.1f} / 10</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    da4.markdown(
        f"""
    <div class="card">
        <h4>🎯 Stops & Targets Advice</h4>
        <div class="val">{target_str} <span style="font-size:0.8rem; color:#888;">(Target)</span></div>
        <div style="font-size: 0.8rem; color: #888; margin-top: 4px;">Stop: {stop_str} | Qty: {qty_str} sh</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Strategy signals table
    st.subheader("📋 Strategy Signals Breakdown")
    strat_rows = []
    for name, col_key in STRATEGY_MAP.items():
        action_val = str(row.get(col_key, "N/A"))
        if action_val in _BUY_VALS:
            badge = '<span class="badge-buy">BUY ▲</span>'
            kind = "BUY"
        elif action_val in _SELL_VALS:
            badge = '<span class="badge-sell">SELL ▼</span>'
            kind = "SELL"
        else:
            badge = '<span class="badge-hold">HOLD</span>'
            kind = "HOLD"
        strat_rows.append(
            {"Strategy": name, "Action": action_val, "Signal": kind, "_badge": badge}
        )

    strat_df = pd.DataFrame(strat_rows)

    buy_n = (strat_df["Signal"] == "BUY").sum()
    sell_n = (strat_df["Signal"] == "SELL").sum()
    hold_n = (strat_df["Signal"] == "HOLD").sum()
    st.markdown(
        f"**Buy:** <span class='signal-buy'>{buy_n}</span>&nbsp;&nbsp;"
        f"**Sell:** <span class='signal-sell'>{sell_n}</span>&nbsp;&nbsp;"
        f"**Hold:** <span class='signal-hold'>{hold_n}</span>",
        unsafe_allow_html=True,
    )

    # Build display with colored cells
    def _mk_html_table(df_s):
        rows_html = ""
        for _, r in df_s.iterrows():
            cls = (
                "signal-buy"
                if r["Signal"] == "BUY"
                else "signal-sell"
                if r["Signal"] == "SELL"
                else "signal-hold"
            )
            rows_html += f"<tr><td>{r['Strategy']}</td><td class='{cls}'>{r['Action']}</td><td>{r['_badge']}</td></tr>"
        return f"""
        <table style="width:100%;border-collapse:collapse;font-size:.9rem">
          <thead><tr style="color:#7c83fd;font-size:.78rem;text-transform:uppercase">
            <th style="text-align:left;padding:6px">Strategy</th>
            <th style="text-align:left;padding:6px">Action</th>
            <th style="text-align:left;padding:6px">Signal</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """

    st.markdown(_mk_html_table(strat_df), unsafe_allow_html=True)

    # Divergences + Candlestick
    st.markdown("---")
    d1, d2, d3 = st.columns(3)

    rsi_div = str(row.get("RSI_DIVERGENCE", "None"))
    macd_div = str(row.get("MACD_DIVERGENCE", "None"))
    candle = str(row.get("STR_CANDLE_PATTERN", "None"))
    ttm_sq = bool(row.get("STR_TTM_SQUEEZE", False))

    def _div_badge(val):
        if "Bullish" in val:
            return f'<span class="badge-buy">{val}</span>'
        if "Bearish" in val:
            return f'<span class="badge-sell">{val}</span>'
        return f'<span class="badge-hold">{val}</span>'

    with d1:
        st.markdown("**📉 RSI Divergence**")
        st.markdown(_div_badge(rsi_div), unsafe_allow_html=True)
    with d2:
        st.markdown("**📉 MACD Divergence**")
        st.markdown(_div_badge(macd_div), unsafe_allow_html=True)
    with d3:
        st.markdown("**🕯 Candlestick**")
        candle_badge = (
            f'<span class="badge-buy">{candle}</span>'
            if candle not in ("None", "N/A", "")
            else '<span class="badge-hold">None</span>'
        )
        st.markdown(candle_badge, unsafe_allow_html=True)
        st.markdown(f"TTM Squeeze Active: **{'✅ Yes' if ttm_sq else '❌ No'}**")

    # Consensus callout
    callout = str(row.get("CONSENSUS_CALLOUT", ""))
    if callout and callout != "N/A":
        color = (
            "#00c27c"
            if "BUY" in callout
            else "#ff5555"
            if "SELL" in callout
            else "#888"
        )
        st.markdown(
            f"""
        <div style="background:#1e2130;border-left:4px solid {color};border-radius:6px;
                    padding:14px 18px;margin-top:16px;color:{color};font-weight:600">
            {callout}
        </div>
        """,
            unsafe_allow_html=True,
        )

    # AI Narrative
    st.markdown("---")
    st.subheader("🤖 Dynamic Quant Narrative")
    try:
        from src.cli.reporter import ScreenerReporter

        reporter = ScreenerReporter()
        narrative = reporter.generate_narrative(row)
        st.text(narrative)
    except Exception as e:
        st.warning(f"Narrative generation failed: {e}")
