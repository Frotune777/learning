"""
Tests for Fyers API data fetcher module.
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.symbol_mapper import SymbolMapper
from src.nse_bhavcopy.fyers_fetcher import (
    FyersFetcher,
    exchange_auth_code,
)


@pytest.fixture
def temp_cache(tmp_path):
    cache_file = tmp_path / "fyers_token.txt"
    return str(cache_file)


def test_fyers_symbol():
    assert SymbolMapper.to_fyers("TCS") == "NSE:TCS-EQ"
    assert SymbolMapper.to_fyers("nse:TCS-EQ") == "NSE:TCS-EQ"
    assert SymbolMapper.to_fyers(" INFY ") == "NSE:INFY-EQ"


def test_token_cache_rw(temp_cache):
    fetcher = FyersFetcher(token_cache=temp_cache, fallback_enabled=False)
    assert fetcher.access_token is None

    fetcher.set_token("dummy_token_123")
    assert fetcher.access_token == "dummy_token_123"
    assert os.path.exists(temp_cache)

    with open(temp_cache) as fh:
        assert fh.read() == "dummy_token_123"

    fetcher2 = FyersFetcher(token_cache=temp_cache, fallback_enabled=False)
    assert fetcher2.access_token == "dummy_token_123"


@patch("src.nse_bhavcopy.fyers_fetcher.requests.post")
def test_exchange_auth_code_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"s": "ok", "access_token": "valid_token"}
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    token = exchange_auth_code("auth_123", "app_key", "secret")
    assert token == "valid_token"


@patch("src.nse_bhavcopy.fyers_fetcher.requests.post")
def test_exchange_auth_code_failure(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"s": "error", "message": "Invalid code"}
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    token = exchange_auth_code("auth_123", "app_key", "secret")
    assert token is None


@patch("src.nse_bhavcopy.fyers_fetcher.requests.get")
def test_fetch_chunk_success(mock_get, temp_cache):
    fetcher = FyersFetcher(
        access_token="tok", token_cache=temp_cache, fallback_enabled=False
    )
    fetcher.api_key = "test_key"

    mock_resp = MagicMock()
    # Mocking Fyers response format (epoch in UTC seconds)
    # 2024-05-01 00:00 UTC = 1714521600
    mock_resp.json.return_value = {
        "s": "ok",
        "candles": [
            [1714521600, 100, 105, 95, 102, 5000],
            [1714608000, 102, 110, 100, 108, 6000],
        ],
    }
    mock_get.return_value = mock_resp

    start = datetime(2024, 5, 1)
    end = datetime(2024, 5, 2)
    df = fetcher._fetch_chunk("NSE:TCS-EQ", "1D", start, end)

    assert not df.empty
    assert len(df) == 2
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df.iloc[0]["Close"] == 102
    assert df.index.name == "Date"


@patch("src.nse_bhavcopy.fyers_fetcher.FyersFetcher._fetch_chunk")
def test_fetch_pagination(mock_fetch_chunk, temp_cache):
    fetcher = FyersFetcher(
        access_token="tok", token_cache=temp_cache, fallback_enabled=False
    )
    fetcher.rate_delay = 0  # speed up test

    def side_effect(sym, res, start, end):
        # Return a 1-row DataFrame for each chunk
        df = pd.DataFrame({"Close": [100]}, index=[start])
        df.index.name = "Date"
        return df

    mock_fetch_chunk.side_effect = side_effect

    # Fetch 2 years of daily data -> should split into ~2 chunks (365 days max)
    end = datetime.utcnow()
    start = end - timedelta(days=700)

    df = fetcher.fetch(
        "TCS",
        timeframe="1d",
        from_date=int(start.replace(tzinfo=UTC).timestamp()),
        to_date=int(end.replace(tzinfo=UTC).timestamp()),
    )

    assert mock_fetch_chunk.call_count >= 2
    assert not df.empty
    assert len(df) >= 2


@patch("src.nse_bhavcopy.fyers_fetcher.requests.get")
def test_get_quotes_success(mock_get, temp_cache):
    fetcher = FyersFetcher(
        access_token="tok", token_cache=temp_cache, fallback_enabled=False
    )
    fetcher.api_key = "test_key"

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "s": "ok",
        "d": [
            {"n": "NSE:TCS-EQ", "v": {"lp": 3500.5}},
            {"n": "NSE:INFY-EQ", "v": {"lp": 1400.0}},
        ],
    }
    mock_get.return_value = mock_resp

    quotes = fetcher.get_quotes(["TCS", "INFY", "INVALID"])
    assert "TCS" in quotes
    assert quotes["TCS"] == 3500.5
    assert quotes["INFY"] == 1400.0
    assert "INVALID" not in quotes
