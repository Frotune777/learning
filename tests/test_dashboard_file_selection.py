import glob
import os
from pathlib import Path

import streamlit as st

from src.dashboard.views.portfolio_view import render_portfolio_view
from src.dashboard.views.screener_view import get_screener_csvs, render_screener_view


def test_enriched_selected_over_analyzed(tmp_path: Path):
    analyzed = tmp_path / "top_250_analyzed_20261015.csv"
    enriched = tmp_path / "top_250_enriched_20261015.csv"
    analyzed.write_text("Symbol,Close\nTCS,3500\n", encoding="utf-8")
    enriched.write_text("Symbol,Close,COMPOSITE_SCORE\nTCS,3500,85.0\n", encoding="utf-8")

    analyzed_files = sorted(glob.glob(os.path.join(str(tmp_path), "top_250_analyzed_*.csv")))
    enriched_files = sorted(glob.glob(os.path.join(str(tmp_path), "top_250_enriched_*.csv")))

    # Selection contract from 01_daily_signals.py
    target_files = enriched_files if enriched_files else analyzed_files

    assert len(target_files) == 1
    assert "top_250_enriched_" in target_files[0]


def test_screener_view_selects_latest_enriched_csv(tmp_path: Path):
    older = tmp_path / "top_250_enriched_20261014.csv"
    newer = tmp_path / "top_250_enriched_20261016.csv"
    analyzed = tmp_path / "top_250_analyzed_20261016.csv"

    older.write_text("SYMBOL,CAR_RATING,VOL_SPIKE,COMPOSITE_SCORE\nINFY,Buy,2.1,80.0\n", encoding="utf-8")
    newer.write_text("SYMBOL,CAR_RATING,VOL_SPIKE,COMPOSITE_SCORE\nTCS,Buy,2.5,90.0\n", encoding="utf-8")
    analyzed.write_text("SYMBOL,Close\nTCS,3500\n", encoding="utf-8")

    csvs = get_screener_csvs(str(tmp_path))
    assert len(csvs) == 3
    # Newer enriched file should be first in the priority list
    assert os.path.basename(csvs[0]) == "top_250_enriched_20261016.csv"
    assert os.path.basename(csvs[1]) == "top_250_enriched_20261014.csv"
    assert os.path.basename(csvs[2]) == "top_250_analyzed_20261016.csv"


def test_screener_view_handles_empty_dir(tmp_path: Path):
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    csvs = get_screener_csvs(str(empty_dir))
    assert csvs == []

    # Should execute gracefully without crashing and output info message
    render_screener_view(data_dir=str(empty_dir))


def test_portfolio_view_dict_schema():
    st.session_state["portfolio_cash"] = 500_000.0
    st.session_state["portfolio_positions"] = {}

    # View loads cleanly with empty dict schema
    render_portfolio_view()
    assert isinstance(st.session_state["portfolio_positions"], dict)
    assert len(st.session_state["portfolio_positions"]) == 0

    # View loads cleanly with active positions dict
    st.session_state["portfolio_positions"]["TCS"] = {
        "symbol": "TCS",
        "qty": 10.0,
        "entry_price": 3500.0,
        "current_price": 3550.0,
        "stop_price": 3400.0,
        "target_price": 3700.0,
        "sector": "IT",
        "entry_date": "2026-10-16",
        "risk_amount": 1000.0,
    }
    render_portfolio_view()
    assert "TCS" in st.session_state["portfolio_positions"]
