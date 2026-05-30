import time
import functools
from datetime import datetime
from src.core.signal import Signal
from src.engine.parallel_scanner import run_parallel_scan, _run_strategy

def dummy_scanner_fast() -> list[Signal]:
    return [
        Signal(symbol="A", strategy_name="fast", action=1, conviction=0.8, timestamp=datetime.now(), meta={})
    ]

def dummy_scanner_slow() -> list[Signal]:
    time.sleep(0.5)
    return [
        Signal(symbol="B", strategy_name="slow", action=-1, conviction=0.9, timestamp=datetime.now(), meta={})
    ]

def dummy_scanner_fail() -> list[Signal]:
    raise ValueError("Intentional failure")

def run_sequential_scan(scanner_funcs: list) -> list[Signal]:
    all_signals = []
    for fn in scanner_funcs:
        strat_name, signals = _run_strategy(fn)
        all_signals.extend(signals)
    return all_signals

def test_parallel_matches_sequential():
    """Verify determinism: parallel output should match sequential output."""
    scanners = [dummy_scanner_fast, dummy_scanner_slow]
    
    # Sequential
    seq_signals = run_sequential_scan(scanners)
    
    # Parallel
    par_signals, metrics = run_parallel_scan(scanners, max_workers=2)
    
    # Same count
    assert len(seq_signals) == len(par_signals)
    
    # Same symbols covered
    seq_symbols = {s.symbol for s in seq_signals}
    par_symbols = {s.symbol for s in par_signals}
    assert seq_symbols == par_symbols

def test_performance_improvement():
    """Verify that multiple slow scanners run faster in parallel."""
    # Run 4 slow scanners
    scanners = [dummy_scanner_slow for _ in range(4)]
    
    t1 = time.time()
    run_sequential_scan(scanners)
    seq_time = time.time() - t1
    
    t2 = time.time()
    run_parallel_scan(scanners, max_workers=4)
    par_time = time.time() - t2
    
    speedup = seq_time / par_time
    print(f"Sequential: {seq_time:.2f}s, Parallel: {par_time:.2f}s, Speedup: {speedup:.2f}x")
    
    # With 4 slow scanners of 0.5s each, sequential is ~2.0s, parallel with 4 workers is ~0.5s.
    assert speedup > 1.5

def test_graceful_scanner_failure():
    """Verify one failing scanner doesn't kill the whole batch."""
    scanners = [dummy_scanner_fail, dummy_scanner_fast]
    
    signals, metrics = run_parallel_scan(scanners, max_workers=2)
    
    # Should get the fast signals despite bad_scanner failing
    assert any(s.strategy_name == "fast" for s in signals)
    assert metrics.total_strategies == 2
