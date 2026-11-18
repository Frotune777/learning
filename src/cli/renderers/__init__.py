"""
Presentation renderers for Fortune ADSS CLI.
Exports Rich table and panel view builders for all terminal screens.
"""

from src.cli.renderers.capsule_views import _render_capsule_table, render_capsule_table
from src.cli.renderers.screener_views import (
    render_backtest_table,
    render_consensus_leaderboard,
    render_lux_regimes_table,
    render_strategy_inspector_card,
    render_strategy_results_table,
    render_unified_signals_table,
)
from src.cli.renderers.system_views import (
    render_dq_audit_panel,
    render_nse_live_quote_table,
    render_option_chain_table,
    render_pre_flight_panel,
)

__all__ = [
    "render_capsule_table",
    "_render_capsule_table",
    "render_strategy_inspector_card",
    "render_consensus_leaderboard",
    "render_strategy_results_table",
    "render_unified_signals_table",
    "render_lux_regimes_table",
    "render_backtest_table",
    "render_dq_audit_panel",
    "render_pre_flight_panel",
    "render_nse_live_quote_table",
    "render_option_chain_table",
]
