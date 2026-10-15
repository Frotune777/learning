"""
File: tests/test_no_circular_imports.py
Purpose: Regression test for Unit 11 — the src.ui ↔ src.data circular
         import. Each test spawns a fresh Python subprocess so the import
         graph is evaluated from a cold state (as a user's script or tool
         would see it). This catches cycles that pytest's forgiving import
         order would otherwise hide.

Rule 11 compliance: no magic numbers, no dummy data. Real subprocess
execution against real modules.

Last Modified: 2026-10-15
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _isolated_import(statement: str) -> tuple[int, str]:
    """
    Run an import statement in a fresh Python subprocess.

    Returns:
        (returncode, combined stdout+stderr stripped)
    """
    result = subprocess.run(
        [sys.executable, "-c", statement],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


@pytest.mark.parametrize(
    "statement",
    [
        # Isolation tests — each spawns a fresh interpreter
        "from src.ui.VisualUI import VisualUI; print('ok')",
        "from src.ui.StockUniverseSelector import StockUniverseSelector; print('ok')",
        "import src.ui; print('ok')",
        "import src.ui.universe; print('ok')",
        "import src.data.manager; print('ok')",
        "import src.data; print('ok')",
        "import download_historical_data; print('ok')",
        "import repair_data; print('ok')",
        # Cross-module pair — previously the entry point of the cycle
        "from src.ui import VisualUI, MenuService, StockUniverseSelector; print('ok')",
        "from src.data import DataRepository, Fetcher, PersistenceService; print('ok')",
        # Shim safety — each shim must resolve from a cold start
        "from src.data.DataRepository import DataRepository; print('ok')",
        "from src.data.Fetcher import Fetcher; print('ok')",
        "from src.data.PersistenceService import PersistenceService; print('ok')",
        "from src.ui.VisualUI import VisualUI; print('ok')",
        "from src.ui.ColorText import colorText; print('ok')",
        "from src.ui.MenuService import MenuService; print('ok')",
    ],
    ids=[
        "isolated_ui_visualui",
        "isolated_ui_stockuniverse",
        "isolated_ui_package",
        "isolated_ui_universe",
        "isolated_data_manager",
        "isolated_data_package",
        "isolated_dhd_root",
        "isolated_repair_root",
        "cross_ui_multi",
        "cross_data_multi",
        "shim_data_repository",
        "shim_data_fetcher",
        "shim_data_persistence",
        "shim_ui_visualui",
        "shim_ui_colortext",
        "shim_ui_menuservice",
    ],
)
def test_isolated_import_succeeds(statement: str) -> None:
    """
    Every module in src/ must be importable from a fresh interpreter without
    triggering a circular-import failure.

    Regression test for Unit 11 — the src.ui ↔ src.data cycle previously
    caused NameError / ImportError on a cold start even though pytest's
    forgiving import order made it pass in-suite.
    """
    returncode, output = _isolated_import(statement)
    assert returncode == 0, (
        f"Isolated import failed (exit {returncode}):\n"
        f"  statement: {statement}\n"
        f"  output:\n{output}"
    )
    assert "ok" in output, f"Expected 'ok' in output, got:\n{output}"
