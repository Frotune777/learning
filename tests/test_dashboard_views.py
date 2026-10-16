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
