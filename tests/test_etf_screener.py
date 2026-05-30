import pandas as pd
from unittest.mock import patch, MagicMock
from src.scanners.etf_screener import run_liquid_etf_screener
from src.core.signal import Signal

@patch("src.scanners.etf_screener.NseUtils")
def test_run_liquid_etf_screener_signal_protocol(mock_nse_utils):
    mock_instance = MagicMock()
    mock_nse_utils.return_value = mock_instance
    
    # Mock return DataFrame
    df = pd.DataFrame({
        "symbol": ["NIFTYBEES", "BANKBEES", "JUNIORBEES"],
        "assets": ["Nifty 50", "Nifty Bank", "Nifty Next 50"],
        "open": [100.0, 200.0, 150.0],
        "high": [101.0, 201.0, 151.0],
        "low": [99.0, 199.0, 149.0],
        "ltP": [100.5, 200.5, 150.5],
        "qty": [100000, 50000, 20000],
    })
    mock_instance.get_etf_list.return_value = df

    signals = run_liquid_etf_screener()
    
    assert isinstance(signals, list)
    assert len(signals) == 3
    
    for sig in signals:
        assert isinstance(sig, Signal)
        assert sig.strategy_name == "etf_screener"
        assert sig.action == 1
        assert 0.0 <= sig.conviction <= 1.0
        assert "category" in sig.meta
        assert "weight" in sig.meta
        assert "volume" in sig.meta
