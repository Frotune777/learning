"""
Automated CLI Smoke & Regression Tests for Fortune ADSS.
Exercises all renderers and offline menu_* handlers with both valid and empty/partial DataFrames.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.cli.menus import (
    ARCHIVE_MENU_SECTIONS,
    LEGACY_MENU_ALIASES,
    MENU_SECTIONS,
    PRIMARY_MENU_SECTIONS,
    _print_main_menu,
    interactive_menu,
    menu_capsule_5star,
    menu_capsule_smc,
    menu_capsule_turnover,
    menu_consensus_leaderboard,
    menu_data_quality,
    menu_data_source_settings,
    menu_fo_ban,
    menu_llm_dossier,
    menu_lux_regimes,
    menu_nifty_ki_dukan,
    menu_query_engine,
    menu_registry,
    menu_smc_calls,
    menu_smc_scan,
    menu_status,
    menu_strategy_inspector,
    menu_ta_dashboard,
    menu_toggle_data_mode,
    menu_train_920130,
)
from src.cli.renderers import (
    render_backtest_table,
    render_capsule_table,
    render_consensus_leaderboard,
    render_dq_audit_panel,
    render_lux_regimes_table,
    render_nse_live_quote_table,
    render_option_chain_table,
    render_pre_flight_panel,
    render_strategy_inspector_card,
    render_strategy_results_table,
    render_unified_signals_table,
)


# ---------------------------------------------------------------------------
# 1. Renderer Tests: Valid & Empty/Partial DataFrames
# ---------------------------------------------------------------------------


def test_render_capsule_table_all_modes():
    """Verify render_capsule_table handles all 4 modes with full and empty data."""
    # Empty DataFrame
    render_capsule_table(pd.DataFrame(), mode="5star")
    render_capsule_table(None, mode="train")

    # Sample DataFrame with domain metrics
    data = {
        "Symbol": ["TCS", "INFY"],
        "Close": [3500.0, 1800.0],
        "Stars": ["★★★★★", "★★★☆☆"],
        "Monthly_Farms": ["✔", "—"],
        "Weekly_Sunflowers": ["✔", "✔"],
        "Daily_Seeds": ["✔", "—"],
        "Turnover_Surge": ["✔", "—"],
        "Train_920130": ["BOARDING", "—"],
        "RSI_D": [65.2, 52.1],
        "RSI_W": [61.0, 50.0],
        "RSI_M": [58.4, 48.0],
        "Action": ["STRONG BUY", "WATCH"],
        "Stop_Loss": [3420.0, 1750.0],
        "Target": [3750.0, 1920.0],
        "SMC_Setup": ["BISI FVG", "None"],
        "Spring": ["✔", "—"],
        "IFC": ["✔", "—"],
    }
    df = pd.DataFrame(data)

    render_capsule_table(df, mode="5star")
    render_capsule_table(df, mode="train")
    render_capsule_table(df, mode="turnover")
    render_capsule_table(df, mode="smc")


def test_render_strategy_inspector_card_graceful_degradation():
    """Verify strategy inspector degrades gracefully when optional columns (e.g. TECH_SCORE) are absent."""
    # Minimal DataFrame missing TECH_SCORE and CAR_RATING
    partial_df = pd.DataFrame([{"SYMBOL": "RELIANCE", "CMP": 2950.0}])
    render_strategy_inspector_card("RELIANCE", partial_df)

    # Missing symbol
    render_strategy_inspector_card("UNKNOWN", partial_df)

    # Dict input with partial keys
    render_strategy_inspector_card("TCS", {"CMP": 3500.0, "TECH_SCORE": 85.0})


def test_render_consensus_leaderboard_graceful_degradation():
    """Verify consensus leaderboard sorts and renders even if columns are missing."""
    render_consensus_leaderboard(pd.DataFrame())

    # Partial DataFrame
    df = pd.DataFrame([
        {"SYMBOL": "SBIN", "CMP": 820.0, "CONSENSUS_SCORE": 8},
        {"SYMBOL": "ICICIBANK", "CMP": 1150.0, "CONSENSUS_SCORE": 11},
    ])
    render_consensus_leaderboard(df, top_n=5)


def test_render_other_views_smoke():
    """Exercise remaining renderers for smoke safety."""
    render_strategy_results_table(pd.DataFrame(), title="Empty Strategy")
    render_strategy_results_table(pd.DataFrame([{"SYMBOL": "TCS", "PRICE": 3500.0}]), title="Valid Strategy")

    render_unified_signals_table(pd.DataFrame())
    render_unified_signals_table(pd.DataFrame([{"SYMBOL": "WIPRO", "ACTION": "BUY"}]))

    render_lux_regimes_table([])
    render_lux_regimes_table([{
        "symbol": "TCS",
        "stage_name": "Stage 2 Markup",
        "ma_value": 3400.0,
        "ma_slope_pct": 2.5,
        "volume_ratio": 1.4,
        "action": "STAGE 2 BREAKOUT",
    }])

    render_backtest_table({"accuracy": 0.68, "total_return_pct": 0.154, "total_trades": 42})
    render_dq_audit_panel(2966, 2400, 100, 50, 10, 400, 6)
    render_pre_flight_panel({"yfinance": {"ok": True, "details": "Latency 150ms"}})
    render_nse_live_quote_table({"symbol": "INFY", "LTP": "₹1,850.00"})
    render_option_chain_table(pd.DataFrame())
    render_option_chain_table(pd.DataFrame([{"STRIKE": 25000, "CE_OI": 120000}]))


# ---------------------------------------------------------------------------
# 2. Offline Menu Handler Tests (Monkeypatched Inputs)
# ---------------------------------------------------------------------------


def test_menu_toggle_data_mode(monkeypatch):
    """Test switching between offline and live modes."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_toggle_data_mode()
    import src.core.config as config
    # Toggle back to ensure test isolation
    if not config.OFFLINE:
        menu_toggle_data_mode()


def test_menu_data_source_settings(monkeypatch):
    """Test data source settings returning to menu."""
    monkeypatch.setattr("builtins.input", lambda _: "0")
    menu_data_source_settings()


def test_menu_query_engine_exit(monkeypatch, tmp_path):
    """Test DuckDB query engine handles 'exit' gracefully."""
    inputs = iter(["exit", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))
    menu_query_engine(str(tmp_path), str(tmp_path))


def test_menu_status_empty_dir(monkeypatch, tmp_path):
    """Test menu_status with empty master gracefully warns and exits."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_status(str(tmp_path), str(tmp_path))


def test_menu_registry_empty_dir(monkeypatch, tmp_path):
    """Test menu_registry with no registry file."""
    inputs = iter(["1d", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    menu_registry(str(tmp_path), str(tmp_path))


def test_menu_fo_ban_smoke(monkeypatch, tmp_path):
    """Test F&O Ban menu handler."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_fo_ban(str(tmp_path))


def test_menu_nifty_ki_dukan_smoke(monkeypatch, tmp_path):
    """Test Nifty Ki Dukan handler with empty inputs."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_nifty_ki_dukan(str(tmp_path), str(tmp_path))


def test_menu_lux_regimes_smoke(monkeypatch, tmp_path):
    """Test LuxAlgo regimes on directory without Parquet files."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_lux_regimes(str(tmp_path))


def test_menu_ta_dashboard_empty_input(monkeypatch, tmp_path):
    """Test TA dashboard with no symbol entered returns immediately."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_ta_dashboard(str(tmp_path))


def test_menu_llm_dossier_empty_input(monkeypatch, tmp_path):
    """Test LLM dossier with no symbol entered returns immediately."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_llm_dossier(str(tmp_path))


def test_menu_strategy_inspector_no_csv(monkeypatch, tmp_path):
    """Test strategy inspector without previous screener CSV."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_strategy_inspector(str(tmp_path))


def test_menu_consensus_leaderboard_no_csv(monkeypatch, tmp_path):
    """Test consensus leaderboard without previous screener CSV."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_consensus_leaderboard(str(tmp_path))


def test_menu_capsule_handlers_smoke(monkeypatch, tmp_path):
    """Test Capsule screener handlers with mocked runner returning empty DataFrame."""
    inputs = iter(["50", "2", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

    with patch("src.scanners.capsule_screener.run_capsule_screener", return_value=pd.DataFrame()):
        menu_capsule_5star(str(tmp_path), str(tmp_path))
        menu_train_920130(str(tmp_path), str(tmp_path))
        menu_capsule_turnover(str(tmp_path), str(tmp_path))
        menu_capsule_smc(str(tmp_path), str(tmp_path))


def test_menu_smc_handlers_smoke(monkeypatch, tmp_path):
    """Test SMC scan and ledger menu handlers."""
    inputs = iter(["", "10", "ALL", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, ""))

    with patch("src.cli.actions.cmd_smc_scan") as mock_scan, patch("src.cli.actions.cmd_smc_calls") as mock_calls:
        menu_smc_scan(str(tmp_path), str(tmp_path))
        menu_smc_calls(str(tmp_path))
        assert mock_scan.called
        assert mock_calls.called


def test_interactive_menu_exit(monkeypatch, tmp_path):
    """Test main REPL loop starts and exits on choice '0' without errors."""
    monkeypatch.setattr("builtins.input", lambda _: "0")
    interactive_menu(data_dir=str(tmp_path), hist_dir=str(tmp_path))


def test_menu_sections_structure_and_print():
    """Verify primary and archive menu categories structure and rendering."""
    # Ensure Category 10, 20, 30, and 90 are in PRIMARY_MENU_SECTIONS
    assert "CATEGORY 10 — DATA & LAKE OPERATIONS" in PRIMARY_MENU_SECTIONS
    assert "CATEGORY 20 — CAPSULE & SMC SCREENERS" in PRIMARY_MENU_SECTIONS
    assert "CATEGORY 30 — INSPECTION, DOSSIERS & ALERTS" in PRIMARY_MENU_SECTIONS
    assert "CATEGORY 90 — ARCHIVED & EXPERIMENTAL TOOLS" in PRIMARY_MENU_SECTIONS

    # Verify primary category codes: 11-14, 21-26, 31-33, 90
    primary_codes = {code for items in PRIMARY_MENU_SECTIONS.values() for code, _, _, _ in items}
    expected_primary = {"11", "12", "13", "14", "21", "22", "23", "24", "25", "26", "31", "32", "33", "90"}
    assert expected_primary.issubset(primary_codes)

    # Verify archive categories: 40s, 50s, 60s
    assert "CATEGORY 40 — QUANTITATIVE & LIVE MARKET" in ARCHIVE_MENU_SECTIONS
    assert "CATEGORY 50 — ML, BACKTESTING & ANALYTICS" in ARCHIVE_MENU_SECTIONS
    assert "CATEGORY 60 — STORAGE, SQL & ADVANCED DATA" in ARCHIVE_MENU_SECTIONS

    # Test rendering in collapsed and expanded modes
    _print_main_menu(show_archive=False)
    _print_main_menu(show_archive=True)


def test_legacy_menu_aliases_completeness():
    """Verify all 43 legacy option keys (1 through 43) exist in LEGACY_MENU_ALIASES."""
    for i in range(1, 44):
        key = str(i)
        assert key in LEGACY_MENU_ALIASES, f"Legacy menu option {key} missing from LEGACY_MENU_ALIASES"
        # Ensure the target new code is a valid non-empty string
        target = LEGACY_MENU_ALIASES[key]
        assert isinstance(target, str) and len(target) > 0


def test_interactive_menu_dispatcher_and_alias_resolution(monkeypatch, tmp_path):
    """Verify interactive REPL handles toggle '90', new category code, and legacy alias."""
    # Inputs:
    # 1. "90" (Toggle archive)
    # 2. "21" (New code: Capsule 5-Star)
    # 3. "39" (Legacy alias for Capsule 5-Star)
    # 4. "0"  (Exit)
    inputs = iter(["90", "21", "39", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs, "0"))

    with patch("src.cli.menus.menu_capsule_5star") as mock_capsule:
        interactive_menu(data_dir=str(tmp_path), hist_dir=str(tmp_path))
        # Both "21" and legacy alias "39" should have invoked menu_capsule_5star
        assert mock_capsule.call_count == 2


def test_menu_ta_dashboard_smoke(monkeypatch, tmp_path):
    """Test TA dashboard reads parquet and computes technical score without error."""
    hist_1d = tmp_path / "1d"
    hist_1d.mkdir(parents=True, exist_ok=True)

    # Create dummy parquet
    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    df = pd.DataFrame(
        {
            "Open": [100.0] * 100,
            "High": [105.0] * 100,
            "Low": [95.0] * 100,
            "Close": [102.0] * 100,
            "Volume": [100000] * 100,
            "RSI_14": [50.0] * 100,
            "EMA_20": [101.0] * 100,
            "EMA_50": [100.0] * 100,
            "EMA_200": [98.0] * 100,
        },
        index=dates,
    )
    df.to_parquet(hist_1d / "TESTSYM.parquet")

    monkeypatch.setattr("builtins.input", lambda _: "")
    menu_ta_dashboard(str(tmp_path), symbol="TESTSYM")


def test_menu_liquid_etf_offline_smoke(monkeypatch, tmp_path):
    """Test liquid ETF menu runs cleanly with offline fallback data."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    with patch("src.scanners.etf_screener.NseUtils.get_etf_list", return_value=pd.DataFrame()):
        from src.cli.menus import menu_liquid_etf
        menu_liquid_etf()


def test_menu_squeeze_and_ma_slope_smoke(monkeypatch, tmp_path):
    """Test squeeze and MA slope menu handlers with mocked signals."""
    monkeypatch.setattr("builtins.input", lambda _: "")
    from src.cli.menus import menu_ma_slope, menu_squeeze

    with patch("src.cli.handlers.screeners.run_squeeze_cli", return_value=[]):
        menu_squeeze(ticker="RELIANCE")

    with patch("src.cli.handlers.screeners.analyze_stock_ma_slope", return_value={"slope": 0.5, "trend": "Bullish"}):
        menu_ma_slope(ticker="RELIANCE")


