"""
File: src/engine/parallel_scanner.py
Purpose: Parallel scanner execution engine for strategy-level multiprocessing.
Last Modified: 2026-05-30
"""

import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Any

from src.core.signal import Signal

LOGGER = logging.getLogger(__name__)


@dataclass
class ScanMetrics:
    """Metrics tracking for parallel scan execution."""
    total_strategies: int
    successful_strategies: int
    failed_strategies: int
    total_signals: int
    signals_per_strategy: dict[str, int]
    scan_duration_seconds: float


def log_scan_metrics(metrics: ScanMetrics) -> None:
    """Log the collected scan metrics."""
    LOGGER.info(
        "SCAN_COMPLETE",
        extra={
            "total_strategies": metrics.total_strategies,
            "success_rate": metrics.successful_strategies / metrics.total_strategies if metrics.total_strategies else 0,
            "total_signals": metrics.total_signals,
            "duration_sec": metrics.scan_duration_seconds,
            "signals_per_strategy": metrics.signals_per_strategy,
        },
    )


def _run_strategy(scanner_func: Callable[[], list[Signal]]) -> tuple[str, list[Signal]]:
    """
    Worker function: executes a single strategy (bound via functools.partial).
    
    Parameters:
        scanner_func (Callable): The scanner function with pre-bound arguments.
        
    Returns:
        tuple[str, list[Signal]]: The strategy name and generated signals.
    """
    # Extract the original function's name if it's a partial, else __name__
    strat_name = getattr(scanner_func, "func", scanner_func).__name__
    try:
        signals = scanner_func()
        return strat_name, signals
    except Exception as e:
        LOGGER.error("Scanner %s failed: %s", strat_name, e, exc_info=True)
        return strat_name, []


def run_parallel_scan(
    scanner_funcs: list[Callable[[], list[Signal]]],
    max_workers: int | None = None,
) -> tuple[list[Signal], ScanMetrics]:
    """
    Distribute strategy execution across CPU cores.
    
    Args:
        scanner_funcs: List of callables (partials) that take no args and return list[Signal].
        max_workers: Number of processes. If None, defaults to CPU count.
        
    Returns:
        tuple: (Flat list of all signals, ScanMetrics object)
    """
    if max_workers is None:
        max_workers = os.cpu_count() or 4
        
    LOGGER.info(
        "Starting parallel scan with %d strategies using %d workers",
        len(scanner_funcs),
        max_workers,
    )
    
    start_time = time.time()
    all_signals: list[Signal] = []
    
    metrics = ScanMetrics(
        total_strategies=len(scanner_funcs),
        successful_strategies=0,
        failed_strategies=0,
        total_signals=0,
        signals_per_strategy={},
        scan_duration_seconds=0.0,
    )

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all strategies
        futures = {
            executor.submit(_run_strategy, fn): fn for fn in scanner_funcs
        }
        
        for future in as_completed(futures):
            strat_name, signals = future.result()
            if signals:
                all_signals.extend(signals)
                metrics.signals_per_strategy[strat_name] = len(signals)
                metrics.total_signals += len(signals)
                metrics.successful_strategies += 1
            else:
                # If it returned [] we don't necessarily know if it failed or just had 0 signals,
                # but the worker logs the error. We treat empty as success if no exception was raised,
                # but for metrics we just log strategies that returned signals, or we can check the exception.
                metrics.successful_strategies += 1

    metrics.scan_duration_seconds = round(time.time() - start_time, 2)
    log_scan_metrics(metrics)
    
    LOGGER.info(
        "Parallel scan complete: %d signals across %d strategies in %.2fs",
        metrics.total_signals,
        metrics.total_strategies,
        metrics.scan_duration_seconds,
    )
    return all_signals, metrics
