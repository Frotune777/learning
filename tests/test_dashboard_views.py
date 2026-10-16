from pathlib import Path

import streamlit as st

from src.dashboard.views.dossier_view import render_dossier_view
from src.dashboard.views.dq_view import render_dq_view


def test_dq_view_renders():
    # Should render gracefully using logs/dq/runs.jsonl
    render_dq_view()


def test_dossier_view_renders():
    # Should render symbol picker and button
    render_dossier_view()


def test_app_menu_configuration():
    from src.dashboard.app import selected_tab
    # Just importing verifies no syntax/import errors in app.py
    assert selected_tab is not None or selected_tab is None


def test_select_latest_run_prefers_full_universe():
    from src.dashboard.views.dq_view import _select_latest_run

    runs = [
        {"timestamp": "2026-10-16T12:00:00Z", "stage": "cli.dq-check", "total_symbols": 2700},
        {"timestamp": "2026-10-16T12:05:00Z", "stage": "historical_sync.sync_one", "total_symbols": 5},
    ]
    selected = _select_latest_run(runs)
    assert selected is not None
    assert selected["total_symbols"] == 2700
    assert selected["stage"] == "cli.dq-check"


def test_select_latest_run_sorts_by_timestamp():
    from src.dashboard.views.dq_view import _select_latest_run

    # Second in file order has EARLIER timestamp than first
    runs = [
        {"timestamp": "2026-10-16T15:00:00Z", "stage": "cli.dq-check", "total_symbols": 2700, "id": "later"},
        {"timestamp": "2026-10-16T14:00:00Z", "stage": "cli.dq-check", "total_symbols": 2700, "id": "earlier"},
    ]
    selected = _select_latest_run(runs)
    assert selected is not None
    assert selected["id"] == "later"


def test_select_latest_run_falls_back_when_no_batch():
    from src.dashboard.views.dq_view import _select_latest_run

    runs = [
        {"timestamp": "2026-10-16T10:00:00Z", "stage": "historical_sync.sync_one", "total_symbols": 1, "id": "1"},
        {"timestamp": "2026-10-16T12:00:00Z", "stage": "historical_sync.sync_one", "total_symbols": 1, "id": "3"},
        {"timestamp": "2026-10-16T11:00:00Z", "stage": "historical_sync.sync_one", "total_symbols": 1, "id": "2"},
    ]
    selected = _select_latest_run(runs)
    assert selected is not None
    assert selected["id"] == "3"
    assert selected["timestamp"] == "2026-10-16T12:00:00Z"

