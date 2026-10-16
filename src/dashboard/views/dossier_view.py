"""
File: src/dashboard/views/dossier_view.py
Purpose: On-demand institutional LLM quantitative dossier generation and markdown viewer.
"""

from __future__ import annotations

import glob
import os
import traceback

import streamlit as st

from src.engine.llm_report import generate_symbol_llm_dossier


def render_dossier_view():
    st.markdown("""
    <div>
        <h2 style="margin:0; font-weight:800; color:#f8fafc;">📄 LLM Quantitative Dossier</h2>
        <p style="margin:4px 0 16px; color:#94a3b8; font-size:0.9rem;">
            Deep institutional multi-lens synthesis across Price Action, SMC, LuxAlgo Regimes, and Risk-Reward parameters for LLM prompt context.
        </p>
    </div>
    """, unsafe_allow_html=True)

    hist_dir = "data/historical/1d"
    parquet_files = sorted(glob.glob(os.path.join(hist_dir, "*.parquet")))
    symbols = [os.path.basename(f).replace(".parquet", "") for f in parquet_files]

    if not symbols:
        st.error("No historical Parquet files found in data/historical/1d. Sync data first.")
        return

    col_sym, col_btn = st.columns([3, 1])
    with col_sym:
        default_idx = symbols.index("TCS") if "TCS" in symbols else 0
        sel_symbol = st.selectbox("Select Equity Symbol", symbols, index=default_idx)

    with col_btn:
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        generate_clicked = st.button("Generate Dossier", use_container_width=True, type="primary")

    cache_key = f"dossier_{sel_symbol}"

    if generate_clicked:
        try:
            with st.spinner(f"Compiling multi-factor quantitative dossier for {sel_symbol}..."):
                dossier_text = generate_symbol_llm_dossier(sel_symbol)
                st.session_state[cache_key] = dossier_text
        except Exception as exc:
            st.error(f"Failed to generate dossier for {sel_symbol}: {exc}")
            st.code(traceback.format_exc(), language="python")

    if cache_key in st.session_state:
        dossier_content = st.session_state[cache_key]

        # Top Download Button
        st.download_button(
            label=f"⬇️ Download {sel_symbol}_LLM_DOSSIER.md",
            data=dossier_content,
            file_name=f"{sel_symbol}_LLM_DOSSIER.md",
            mime="text/markdown",
            use_container_width=True,
        )

        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

        # Render formatted markdown
        with st.container():
            st.markdown(dossier_content, unsafe_allow_html=True)

    st.markdown("---")
    st.caption(
        "This dossier reconciles six independent lenses (Weinstein, SMC, Composite, NWE, SavGol, VSA). "
        "Section 7 names divergences; Section 8 is a prompt for downstream LLMs."
    )
