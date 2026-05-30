from src.core.signal import Signal
from src.nse_bhavcopy.consensus_engine import aggregate_signals
from datetime import datetime

def test_signal_validation():
    # Should raise on bad action
    try:
        Signal("RELIANCE", "test", 2, 0.5, datetime.now(), {})
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

def test_consensus_aggregation():
    signals = [
        Signal("RELIANCE", "rsi", 1, 0.8, datetime.now(), {"rsi": 75}),
        Signal("RELIANCE", "macd", 1, 0.6, datetime.now(), {}),
        Signal("RELIANCE", "darvas", 0, 0.5, datetime.now(), {}),
    ]
    result = aggregate_signals(signals)
    assert "RELIANCE" in result
    assert -1.0 <= result["RELIANCE"] <= 1.0
