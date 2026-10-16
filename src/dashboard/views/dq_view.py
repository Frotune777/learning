"""
File: src/dashboard/views/dq_view.py
Purpose: Data Quality Gate status, bucket breakdown, run history, and triage ledger.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st


# NSE equity universe is ~2700; anything below 1000 is a partial run
MIN_MEANINGFUL_UNIVERSE = 1000


def _select_latest_run(runs: list[dict]) -> dict | None:
    if not runs:
        return None

    meaningful = [
        r for r in runs
        if r.get("total_symbols", 0) >= MIN_MEANINGFUL_UNIVERSE
        and (
            r.get("stage") == "cli.dq-check"
            or r.get("stage") in {"bhavcopy_incremental.run", "historical_sync.sync"}
        )
    ]
    candidates = meaningful if meaningful else runs
    return sorted(candidates, key=lambda r: str(r.get("timestamp", "")), reverse=True)[0]


def render_dq_view():
    st.markdown("""
    <div>
        <h2 style="margin:0; font-weight:800; color:#f8fafc;">🛡️ Data Quality Gate & Audit Ledger</h2>
        <p style="margin:4px 0 16px; color:#94a3b8; font-size:0.9rem;">
            Automated enforcement of disk integrity, recency, historical coverage, and TA indicator presence.
        </p>
    </div>
    """, unsafe_allow_html=True)

    runs_path = Path("logs/dq/runs.jsonl")
    if not runs_path.exists() or runs_path.stat().st_size == 0:
        st.info("No DQ runs recorded yet. Run `./scripts/dq_gate.sh` to generate the first run.")
        return

    # Parse runs from runs.jsonl
    runs = []
    with open(runs_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    runs.append(json.loads(line))
                except Exception:
                    pass

    latest_run = _select_latest_run(runs)
    if not latest_run:
        st.info("No DQ runs recorded yet. Run `./scripts/dq_gate.sh` to generate the first run.")
        return

    # Load threshold from config
    cfg_threshold = 0.08
    cfg_path = Path("config/dq_config.json")
    if cfg_path.exists():
        try:
            with open(cfg_path, encoding="utf-8") as cf:
                cfg_threshold = json.load(cf).get("halt_if_failure_pct", 0.08)
        except Exception:
            pass

    # Top KPI Row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        halt = latest_run.get("halt_triggered", False)
        status_color = "#ef4444" if halt else "#10b981"
        status_text = "HALT" if halt else "PASSED"
        status_sub = latest_run.get("halt_reason") or "Within normal operating bounds"
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Latest Run Status</div>
            <div class="pro-card-value" style="color:{status_color};">{status_text}</div>
            <div class="pro-card-sub">{status_sub[:38]}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        fail_pct = latest_run.get("failure_pct", 0.0)
        rate_color = "#ef4444" if fail_pct > cfg_threshold else "#10b981"
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Failure Rate vs Threshold</div>
            <div class="pro-card-value" style="color:{rate_color};">{fail_pct:.2%}</div>
            <div class="pro-card-sub">Halt Threshold: {cfg_threshold:.1%}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        total_syms = latest_run.get("total_symbols", 0)
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Total Symbols Inspected</div>
            <div class="pro-card-value" style="color:#38bdf8;">{total_syms:,}</div>
            <div class="pro-card-sub">Stage: {latest_run.get('stage', 'cli.dq-check')}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        raw_ts = latest_run.get("timestamp", "")
        try:
            hum_ts = pd.to_datetime(raw_ts).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            hum_ts = raw_ts[:19]
        st.markdown(f"""
        <div class="pro-card">
            <div class="pro-card-title">Last Checked</div>
            <div class="pro-card-value" style="color:#a855f7; font-size:1.25rem;">{hum_ts.split(' ')[0]}</div>
            <div class="pro-card-sub">{hum_ts.split(' ')[1] if ' ' in hum_ts else ''} UTC</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    # Bucket Breakdown Row
    st.markdown("<div class='section-hdr'><h3>Universe Health Breakdown</h3><div class='line'></div></div>", unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        h_cnt = latest_run.get("passed_count", 0)
        st.markdown(f"""
        <div class="pro-card" style="border-left: 3px solid #10b981;">
            <div class="pro-card-title" style="color:#10b981;">● Healthy Symbols</div>
            <div class="pro-card-value">{h_cnt:,}</div>
            <div class="pro-card-sub">Recent, valid OHLCV & TA</div>
        </div>
        """, unsafe_allow_html=True)
    with b2:
        i_cnt = latest_run.get("inactive_count", 0)
        st.markdown(f"""
        <div class="pro-card" style="border-left: 3px solid #94a3b8;">
            <div class="pro-card-title" style="color:#94a3b8;">● Inactive / Delisted</div>
            <div class="pro-card-value">{i_cnt:,}</div>
            <div class="pro-card-sub">&ge;90 days since last trade</div>
        </div>
        """, unsafe_allow_html=True)
    with b3:
        s_cnt = latest_run.get("stale_count", 0)
        st.markdown(f"""
        <div class="pro-card" style="border-left: 3px solid #f59e0b;">
            <div class="pro-card-title" style="color:#f59e0b;">● Stale Trading</div>
            <div class="pro-card-value">{s_cnt:,}</div>
            <div class="pro-card-sub">Actionable &lt;90d gap</div>
        </div>
        """, unsafe_allow_html=True)
    with b4:
        c_cnt = latest_run.get("low_coverage_count", 0)
        st.markdown(f"""
        <div class="pro-card" style="border-left: 3px solid #f97316;">
            <div class="pro-card-title" style="color:#f97316;">● Low Coverage</div>
            <div class="pro-card-value">{c_cnt:,}</div>
            <div class="pro-card-sub">&lt;85% trading days</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

    # 1. Actionable Stale Triage Table (Expanded by default)
    with st.expander("⚠️ Actionable Stale Triage Table (Recent Failures)", expanded=True):
        symbols_path = Path("logs/dq/symbols.jsonl")
        if symbols_path.exists() and symbols_path.stat().st_size > 0:
            target_run_id = latest_run.get("run_id")
            failed_rows = []
            with open(symbols_path, encoding="utf-8") as sf:
                for line in sf:
                    line = line.strip()
                    if line:
                        try:
                            item = json.loads(line)
                            if target_run_id and item.get("run_id") != target_run_id:
                                continue
                            if not item.get("passed", True) and item.get("failure_reason"):
                                failed_rows.append(item)
                        except Exception:
                            pass

            if not failed_rows and target_run_id:
                # Fallback to last failed records across any run if target run had no failures
                with open(symbols_path, encoding="utf-8") as sf:
                    for line in sf:
                        line = line.strip()
                        if line:
                            try:
                                item = json.loads(line)
                                if not item.get("passed", True) and item.get("failure_reason"):
                                    failed_rows.append(item)
                            except Exception:
                                pass

            if failed_rows:
                # Show most recent 100
                df_failed = pd.DataFrame(failed_rows[-100:][::-1])
                cols_to_show = [
                    c for c in ["symbol", "failure_reason", "last_bar_date", "row_count", "coverage_pct", "classification"]
                    if c in df_failed.columns
                ]
                if "coverage_pct" in df_failed.columns:
                    df_failed["coverage_pct"] = df_failed["coverage_pct"].map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
                st.dataframe(df_failed[cols_to_show], use_container_width=True, height=360)
            else:
                st.info("No symbol failures recorded for this run.")
        else:
            st.info("No symbol-level audit records found in logs/dq/symbols.jsonl.")

    # 2. Inactive Universe Table (Collapsed)
    with st.expander("📦 Inactive & Suspended Symbols Registry (inactive_symbols.csv)", expanded=False):
        inactive_csv = Path("data/historical/inactive_symbols.csv")
        if inactive_csv.exists() and inactive_csv.stat().st_size > 0:
            df_inact = pd.read_csv(inactive_csv)
            st.dataframe(df_inact, use_container_width=True, height=360)
        else:
            st.info("No inactive symbols registry found at data/historical/inactive_symbols.csv.")

    # 3. Run History Table (Collapsed)
    with st.expander("📜 Gate Run History (Last 20 Runs)", expanded=False):
        recent_runs = runs[-20:][::-1]
        df_hist = pd.DataFrame(recent_runs)
        display_cols = [
            c for c in ["timestamp", "stage", "total_symbols", "failure_pct", "halt_triggered", "duration_ms"]
            if c in df_hist.columns
        ]
        if "failure_pct" in df_hist.columns:
            df_hist["failure_pct"] = df_hist["failure_pct"].map(lambda x: f"{x:.2%}" if pd.notna(x) else "0.00%")
        if "duration_ms" in df_hist.columns:
            df_hist["duration_ms"] = df_hist["duration_ms"].map(lambda x: f"{x/1000.0:.2f}s" if pd.notna(x) else "—")
        st.dataframe(df_hist[display_cols], use_container_width=True, height=360)
