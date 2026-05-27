"""
File: tests/test_nse_charts.py
Purpose: Unit tests for NSEChartFetcher, CircuitBreaker, and Session dependencies.

Dependencies:
External:
- pytest>=8.2.2: Unit test runner framework
- pandas>=2.2.3: Used for structuring expected OHLCV dataframes
- requests>=2.32.3: Requests mapping mocks
Internal:
- src.data.fetcher.prices.base: [AbstractPriceFetcher]
- src.data.fetcher.prices.nse_charts: [NSEChartFetcher]
- src.data.fetcher.circuit_breaker: [CircuitBreaker]
- src.data.fetcher.session.manager: [SessionManager]
- src.data.fetcher.session.nse_session: [NSESessionInitializer]
- src.data.fetcher.symbols.resolver: [SymbolResolver]

Key Components:
Classes:
- None
Functions:
- test_abstract_price_fetcher: Verifies abstract fetch requirements.
- test_circuit_breaker_transitions: Verifies CLOSED/OPEN state cycles.
- test_session_manager_headers: Verifies browser headers setup.
- test_nse_session_warmup: Verifies cookie landing fetches.
- test_symbol_resolver_local_map: Verifies JSON mappings loading.
- test_nse_chart_fetcher_retrieval: Verifies API JSON parses.

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Add edge case test for negative timestamps

Related Files:
- src/data/fetcher/prices/nse_charts.py: Component under test.
"""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from src.data.fetcher.circuit_breaker import CircuitBreaker
from src.data.fetcher.prices.base import AbstractPriceFetcher
from src.data.fetcher.prices.nse_charts import NSEChartFetcher
from src.data.fetcher.session.manager import SessionManager
from src.data.fetcher.session.nse_session import NSESessionInitializer
from src.data.fetcher.symbols.resolver import SymbolResolver


def test_abstract_price_fetcher() -> None:
    """
    Verify AbstractPriceFetcher enforces override of the fetch method.

    Logic:
        Step 1: Attempt to instantiate base AbstractPriceFetcher. Assert TypeError.
        Step 2: Subclass and instantiate concrete test fetcher. Assert success.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> test_abstract_price_fetcher()
    """
    with pytest.raises(TypeError):
        # type: ignore[abstract]
        AbstractPriceFetcher()

    class ValidFetcher(AbstractPriceFetcher):
        def fetch(
            self,
            symbol: str,
            timeframe: str = "1d",
            period: str = "1y",
            from_date: int | None = None,
            to_date: int | None = None,
        ) -> pd.DataFrame:
            return pd.DataFrame([{"Close": 100.0}])

    fetcher = ValidFetcher()
    assert fetcher.fetch("TCS").iloc[0]["Close"] == 100.0


def test_circuit_breaker_transitions() -> None:
    """
    Verify CircuitBreaker moves states CLOSED -> OPEN -> HALF-OPEN -> CLOSED.

    Logic:
        Step 1: Create failing dummy function call.
        Step 2: Assert state transitions to OPEN after 2 successive failures.
        Step 3: Assert fast-failing error is raised immediately when OPEN.
        Step 4: Elapse time mock to trigger recovery and transition back.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> test_circuit_breaker_transitions()
    """
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    assert cb.state == "CLOSED"

    def fail_call() -> None:
        raise ValueError("Fail connection")

    # Fail 1
    with pytest.raises(ValueError):
        cb.call(fail_call)
    assert cb.state == "CLOSED"

    # Fail 2 (Reaches threshold -> Transition to OPEN)
    with pytest.raises(ValueError):
        cb.call(fail_call)
    assert cb.state == "OPEN"

    # Fast failing
    with pytest.raises(RuntimeError):
        cb.call(fail_call)

    # Elapse recovery time
    time.sleep(0.15)

    # Trigger recovery call
    def success_call() -> int:
        return 42

    res = cb.call(success_call)
    assert res == 42
    assert cb.state == "CLOSED"


def test_session_manager_headers() -> None:
    """
    Verify SessionManager coordinates headers, browser sessions, and delays.

    Logic:
        Step 1: Verify default browser headers are present.
        Step 2: Track clock duration before and after rate pacing triggers.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> test_session_manager_headers()
    """
    sm = SessionManager(rate_limit_delay=0.1)
    session = sm.get_session()
    assert isinstance(session, requests.Session)
    assert "User-Agent" in session.headers
    assert sm.get_proxy() is None

    # Verify rate limit pacing delay
    sm.respect_rate_limit()
    start = time.time()
    sm.respect_rate_limit()
    duration = time.time() - start
    assert duration >= 0.08


def test_nse_session_warmup() -> None:
    """
    Verify NSESessionInitializer triggers landing cookie warmup calls.

    Logic:
        Step 1: Mock landing page response returning mock cookie dictionary.
        Step 2: Execute warmup session initialization.
        Step 3: Assert session is marked initialized and bypasses on repeat.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> test_nse_session_warmup()
    """
    sm = SessionManager(rate_limit_delay=0.01)
    initializer = NSESessionInitializer(sm, main_url="https://mocknse.com/")
    assert not initializer.initialized

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.cookies.get_dict.return_value = {"nsit": "123"}

    with patch.object(requests.Session, "get", return_value=mock_resp) as mock_get:
        initializer.ensure_initialized()
        assert initializer.initialized
        mock_get.assert_called_once()

        # Call again, should bypass landing page get request
        initializer.ensure_initialized()
        mock_get.assert_called_once()


def test_symbol_resolver_local_map(tmp_path: Path) -> None:
    """
    Verify SymbolResolver resolves symbol-to-token mappings and saves.

    Logic:
        Step 1: Instantiate resolver with temporary filepath.
        Step 2: Assert predefined mapping indexes.
        Step 3: Register new mapping dynamically and assert saved payload.

    Parameters:
        tmp_path (Path): Pytest temporary path fixture.

    Returns:
        None

    Raises:
        None

    Example:
        >>> # Executed by pytest
    """
    cache_file = tmp_path / "tokens_test.json"
    resolver = SymbolResolver(cache_path=str(cache_file))

    # Assert pre-seeded mapping
    assert resolver.get_token("TCS") == "11536"
    assert resolver.get_token("  reliance  ") == "2885"
    assert resolver.get_token("UNKNOWN") is None

    # Add dynamically and assert saved
    resolver.add_token("MOCKSTOCK", "9999")
    assert resolver.get_token("mockstock") == "9999"
    assert os.path.exists(str(cache_file))

    # Reload mapping cache from storage file
    resolver_new = SymbolResolver(cache_path=str(cache_file))
    assert resolver_new.get_token("MOCKSTOCK") == "9999"


def test_nse_chart_fetcher_retrieval() -> None:
    """
    Verify NSEChartFetcher queries official charting endpoints successfully.

    Logic:
        Step 1: Mock session manager and landing initializers.
        Step 2: Mock response returning standard JSON records data.
        Step 3: Execute fetcher mapping. Assert timezone and parsed values.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> test_nse_chart_fetcher_retrieval()
    """
    sm = SessionManager(rate_limit_delay=0.01)
    init = NSESessionInitializer(sm)
    init.initialized = True
    resolver = SymbolResolver()

    # Pre-seeded mock data matching charting SymbolsHistoricalData endpoint
    mock_json = {
        "data": [
            {
                "time": 1779930000000,  # Milliseconds epoch timestamp
                "open": "100.5",
                "high": "105.2",
                "low": "99.1",
                "close": "104.3",
                "volume": "1000",
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_json

    fetcher = NSEChartFetcher(sm, init, resolver)

    with patch.object(requests.Session, "get", return_value=mock_resp):
        df = fetcher.fetch("TCS", period="1y")
        assert not df.empty
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert df.index.name == "Date"
        assert df.iloc[0]["Close"] == 104.3
        assert df.iloc[0]["Volume"] == 1000.0


def test_nse_chart_fetcher_errors() -> None:
    """
    Verify NSEChartFetcher defensive error handling for missing and HTTP errors.

    Logic:
        Step 1: Check unmapped token returns empty DataFrame.
        Step 2: Mocks remote failure throwing HTTPError inside fetcher.

    Parameters:
        None

    Returns:
        None

    Raises:
        None

    Example:
        >>> test_nse_chart_fetcher_errors()
    """
    sm = SessionManager(rate_limit_delay=0.01)
    init = NSESessionInitializer(sm)
    init.initialized = True
    resolver = SymbolResolver()

    fetcher = NSEChartFetcher(sm, init, resolver)

    # Unmapped token returns empty dataframe
    df_empty = fetcher.fetch("MISSING_TICKER_99")
    assert df_empty.empty

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )

    with patch.object(requests.Session, "get", return_value=mock_resp):
        with pytest.raises(requests.exceptions.HTTPError):
            fetcher.fetch("TCS")
