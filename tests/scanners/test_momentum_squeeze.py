import pandas as pd
from unittest.mock import patch
from src.scanners.momentum_squeeze import run_squeeze_cli
from src.core.signal import Signal

@patch("src.scanners.momentum_squeeze.momentum_squeeze")
def test_run_squeeze_cli_signal_protocol(mock_momentum_squeeze):
    import numpy as np
    # Mock return DataFrame
    df = pd.DataFrame({
        "Close": [100.0] * 15,
        "Momentum": [0.5] * 15,
        "SqueezeOn": [True] * 15,
        "SqueezeOff": [False] * 15,
        "NoSqueeze": [False] * 15,
        "HistColor": ["lime"] * 15,
        "ZeroLineColor": ["black"] * 15,
    })
    mock_momentum_squeeze.return_value = df

    signals = run_squeeze_cli("RELIANCE")
    
    assert isinstance(signals, list)
    assert len(signals) == 10  # It takes tail(10)
    
    for sig in signals:
        assert isinstance(sig, Signal)
        assert sig.strategy_name == "momentum_squeeze"
        assert sig.action in (-1, 0, 1)
        assert 0.0 <= sig.conviction <= 1.0
