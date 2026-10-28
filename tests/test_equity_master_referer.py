"""
File: tests/test_equity_master_referer.py
Purpose: Unit tests for dynamic NSE Referer hardening and 403 handling (R-04).
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.storage.equity_master import NSEEquityMasterBuilder


def test_class_docstring_intact() -> None:
    assert NSEEquityMasterBuilder.__doc__ is not None
    assert "Downloads and merges" in NSEEquityMasterBuilder.__doc__


def test_referer_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("NSE_REFERER", "https://example.test/x")
    builder = NSEEquityMasterBuilder(
        output_dir=str(tmp_path), cache_dir=str(tmp_path / "cache")
    )
    with patch.object(builder.session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        builder._get("https://www.nseindia.com/api/test")
        assert builder.session.headers.get("Referer") == "https://example.test/x"


def test_referer_warmup_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("NSE_REFERER", raising=False)
    builder = NSEEquityMasterBuilder(
        output_dir=str(tmp_path), cache_dir=str(tmp_path / "cache")
    )
    with patch.object(builder.session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        builder._warmup_cookies(force=True)
        assert (
            builder._last_warmed_url
            == "https://www.nseindia.com/market-data/live-equity-market"
        )

        builder._get("https://www.nseindia.com/api/equity-stockIndices")
        assert (
            builder.session.headers.get("Referer")
            == "https://www.nseindia.com/market-data/live-equity-market"
        )


def test_referer_default_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("NSE_REFERER", raising=False)
    builder = NSEEquityMasterBuilder(
        output_dir=str(tmp_path), cache_dir=str(tmp_path / "cache")
    )
    with patch.object(builder.session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        builder._get("https://www.nseindia.com/api/equity-stockIndices")
        assert builder.session.headers.get("Referer") == builder.DEFAULT_REFERER


def test_403_logs_hint_no_retry(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("NSE_REFERER", raising=False)
    builder = NSEEquityMasterBuilder(
        output_dir=str(tmp_path), cache_dir=str(tmp_path / "cache")
    )
    target_url = "https://www.nseindia.com/api/equity-stockIndices"
    with patch.object(builder.session, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_get.return_value = mock_resp

        with caplog.at_level(logging.WARNING):
            resp = builder._get(target_url)
            assert resp.status_code == 403

        # (a) WARNING contains both the URL and literal substring "NSE_REFERER"
        warning_logs = [
            rec.message
            for rec in caplog.records
            if rec.levelno == logging.WARNING
        ]
        assert any(
            target_url in msg and "NSE_REFERER" in msg for msg in warning_logs
        )

        # (b) Mock called exactly ONCE (no retry loop on 403)
        assert mock_get.call_count == 1


def test_referer_class_attributes(tmp_path: Path) -> None:
    builder = NSEEquityMasterBuilder(
        output_dir=str(tmp_path), cache_dir=str(tmp_path / "cache")
    )
    assert (
        builder.DEFAULT_REFERER
        == "https://www.nseindia.com/market-data/live-equity-market"
    )
    assert builder._last_warmed_url is None
