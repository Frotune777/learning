from unittest.mock import patch

import pandas as pd

from src.core.signal import Signal
from src.scanners.minervini_screener import run_minervini_cli


@patch("src.scanners.minervini_screener.run_minervini_screener")
@patch("src.scanners.minervini_screener.filter_candidates")
def test_run_minervini_cli_signal_protocol(
    mock_filter_candidates, mock_run_minervini_screener
):
    # Mock return DataFrame from filter_candidates
    df = pd.DataFrame(
        {
            "index": ["RELIANCE", "TCS"],
            "RS_Rating": [85.0, 75.0],
            "Template_Score": [9, 8],
            "Stage2": [True, True],
            "High_Proximity": [0.95, 0.88],
            "RVOL": [1.5, 1.3],
        }
    )
    mock_filter_candidates.return_value = df
    mock_run_minervini_screener.return_value = pd.DataFrame()

    signals = run_minervini_cli()

    assert isinstance(signals, list)
    assert len(signals) == 2

    for sig in signals:
        assert isinstance(sig, Signal)
        assert sig.strategy_name == "minervini_screener"
        assert sig.action == 1
        assert 0.0 <= sig.conviction <= 1.0
        assert "rs_rating" in sig.meta
        assert "template_score" in sig.meta
        assert "stage2" in sig.meta
