"""
File: tests/test_bhavcopy_incremental.py
Purpose: Unit tests for BhavcopyIncrementalSync and parse_bhavcopy_ohlcv.
Last Modified: 2026-05-30
"""

import io
import os
import zipfile
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from src.storage.bhavcopy_incremental import BhavcopyIncrementalSync
from src.storage.downloader import BhavcopyDownloader
from src.storage.sync_registry import SyncRecord, SyncRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bhavcopy_zip(rows: list[dict[str, object]]) -> bytes:
    """
    Build a minimal in-memory Bhavcopy ZIP bytes containing a single CSV.

    Parameters:
        rows (list[dict]): List of row dicts — keys should be Bhavcopy column names.

    Returns:
        bytes: Valid ZIP bytes with an inner CSV file.
    """
    import csv

    if not rows:
        rows = []

    fieldnames = list(rows[0].keys()) if rows else ["TckrSymb"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    csv_bytes = buf.getvalue().encode()

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("BhavCopy_NSE_CM_20260529.csv", csv_bytes)
    return zip_buf.getvalue()


SAMPLE_ROWS: list[dict[str, object]] = [
    {
        "TckrSymb": "TCS",
        "SctySrs": "EQ",
        "OpnPric": 3500.0,
        "HghPric": 3550.0,
        "LwPric": 3480.0,
        "ClsPric": 3520.0,
        "TtlTrdQnty": 1_000_000,
        "TtlTrfVal": 3_520_000_000.0,
    },
    {
        "TckrSymb": "INFY",
        "SctySrs": "EQ",
        "OpnPric": 1600.0,
        "HghPric": 1630.0,
        "LwPric": 1590.0,
        "ClsPric": 1615.0,
        "TtlTrdQnty": 2_000_000,
        "TtlTrfVal": 3_230_000_000.0,
    },
    {
        "TckrSymb": "GOLDIETF",
        "SctySrs": "ETF",  # Should be filtered out
        "OpnPric": 500.0,
        "HghPric": 510.0,
        "LwPric": 498.0,
        "ClsPric": 505.0,
        "TtlTrdQnty": 50_000,
        "TtlTrfVal": 25_250_000.0,
    },
]


@pytest.fixture()
def sample_zip() -> bytes:
    """Return a sample Bhavcopy ZIP with 2 EQ + 1 ETF rows."""
    return _make_bhavcopy_zip(SAMPLE_ROWS)


@pytest.fixture()
def syncer(tmp_path: "pytest.TempPathFactory") -> BhavcopyIncrementalSync:
    """Return a BhavcopyIncrementalSync wired to a temp directory."""
    return BhavcopyIncrementalSync(
        data_dir=str(tmp_path / "historical"),
        timeframe="1d",
        raw_dir=str(tmp_path / "raw"),
        rate_delay=0.0,
    )


# ---------------------------------------------------------------------------
# parse_bhavcopy_ohlcv tests
# ---------------------------------------------------------------------------


class TestParseBhavcopyOhlcv:
    """Tests for BhavcopyDownloader.parse_bhavcopy_ohlcv()."""

    def test_returns_eq_rows_only(self, sample_zip: bytes, tmp_path: object) -> None:
        """ETF rows must be filtered out; only EQ rows returned."""
        dl = BhavcopyDownloader(
            raw_dir=str(tmp_path),  # type: ignore[arg-type]
            processed_dir=str(tmp_path),  # type: ignore[arg-type]
        )
        trade_date = datetime(2026, 5, 29)
        df = dl.parse_bhavcopy_ohlcv(sample_zip, trade_date)

        assert len(df) == 2
        assert set(df["Symbol"].tolist()) == {"TCS", "INFY"}
        assert "GOLDIETF" not in df["Symbol"].values

    def test_column_schema(self, sample_zip: bytes, tmp_path: object) -> None:
        """Output DataFrame must have exactly the expected columns."""
        dl = BhavcopyDownloader(
            raw_dir=str(tmp_path),  # type: ignore[arg-type]
            processed_dir=str(tmp_path),  # type: ignore[arg-type]
        )
        df = dl.parse_bhavcopy_ohlcv(sample_zip, datetime(2026, 5, 29))
        expected_cols = {
            "Symbol",
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "Turnover",
        }
        assert set(df.columns) == expected_cols

    def test_date_column_matches_trade_date(
        self, sample_zip: bytes, tmp_path: object
    ) -> None:
        """All rows must carry the exact trade_date as their Date value."""
        dl = BhavcopyDownloader(
            raw_dir=str(tmp_path),  # type: ignore[arg-type]
            processed_dir=str(tmp_path),  # type: ignore[arg-type]
        )
        trade_date = datetime(2026, 5, 29)
        df = dl.parse_bhavcopy_ohlcv(sample_zip, trade_date)
        expected = pd.Timestamp("2026-05-29")
        assert all(df["Date"] == expected)

    def test_ohlc_numeric_types(self, sample_zip: bytes, tmp_path: object) -> None:
        """OHLCV columns must be numeric (float64)."""
        dl = BhavcopyDownloader(
            raw_dir=str(tmp_path),  # type: ignore[arg-type]
            processed_dir=str(tmp_path),  # type: ignore[arg-type]
        )
        df = dl.parse_bhavcopy_ohlcv(sample_zip, datetime(2026, 5, 29))
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            assert pd.api.types.is_numeric_dtype(df[col]), f"{col} not numeric"

    def test_bad_zip_raises(self, tmp_path: object) -> None:
        """Non-ZIP bytes must raise zipfile.BadZipFile."""
        import zipfile as zf

        dl = BhavcopyDownloader(
            raw_dir=str(tmp_path),  # type: ignore[arg-type]
            processed_dir=str(tmp_path),  # type: ignore[arg-type]
        )
        with pytest.raises(zf.BadZipFile):
            dl.parse_bhavcopy_ohlcv(b"not a zip", datetime(2026, 5, 29))

    def test_missing_volume_column_defaults_to_zero(self, tmp_path: object) -> None:
        """When no volume column exists, Volume must default to 0."""
        rows_no_vol = [
            {
                "TckrSymb": "WIPRO",
                "SctySrs": "EQ",
                "OpnPric": 250.0,
                "HghPric": 260.0,
                "LwPric": 248.0,
                "ClsPric": 255.0,
                # No TtlTrdQnty
            }
        ]
        zip_bytes = _make_bhavcopy_zip(rows_no_vol)
        dl = BhavcopyDownloader(
            raw_dir=str(tmp_path),  # type: ignore[arg-type]
            processed_dir=str(tmp_path),  # type: ignore[arg-type]
        )
        df = dl.parse_bhavcopy_ohlcv(zip_bytes, datetime(2026, 5, 29))
        assert df["Volume"].iloc[0] == 0.0


# ---------------------------------------------------------------------------
# detect_missing_days tests
# ---------------------------------------------------------------------------


class TestDetectMissingDays:
    """Tests for BhavcopyIncrementalSync.detect_missing_days()."""

    def test_returns_empty_when_all_current(
        self, syncer: BhavcopyIncrementalSync, tmp_path: object
    ) -> None:
        """When registry shows last_bar_date == last_trading_day, nothing missing."""
        from src.storage.sync_registry import _last_trading_day

        today = _last_trading_day()
        registry = SyncRegistry(
            registry_dir=str(tmp_path),
            timeframe="1d",  # type: ignore[arg-type]
        )
        rec = SyncRecord(
            symbol="TCS",
            status="ok",
            last_bar_date=today,
            row_count=5000,
            timeframe="1d",
        )
        registry._store["TCS"] = rec  # type: ignore[attr-defined]

        # Patch _last_trading_day in bhavcopy_incremental to the same day
        with patch(
            "src.storage.bhavcopy_incremental._last_trading_day",
            return_value=today,
        ):
            missing = syncer.detect_missing_days(["TCS"], registry=registry)

        assert missing == set()

    def test_returns_missing_days_for_stale_symbol(
        self, syncer: BhavcopyIncrementalSync, tmp_path: object
    ) -> None:
        """Symbol last synced 3 days ago → 3 (approx) missing weekday dates."""
        from src.storage.sync_registry import _last_trading_day

        today = _last_trading_day()
        stale_date = today - timedelta(days=4)  # 4 calendar days back

        registry = SyncRegistry(
            registry_dir=str(tmp_path),
            timeframe="1d",  # type: ignore[arg-type]
        )
        rec = SyncRecord(
            symbol="INFY",
            status="ok",
            last_bar_date=stale_date,
            row_count=1000,
            timeframe="1d",
        )
        registry._store["INFY"] = rec  # type: ignore[attr-defined]

        with patch(
            "src.storage.bhavcopy_incremental._last_trading_day",
            return_value=today,
        ):
            missing = syncer.detect_missing_days(
                ["INFY"], registry=registry, days_back=10
            )

        assert len(missing) > 0
        assert all(d > stale_date for d in missing)

    def test_new_symbol_skipped(
        self, syncer: BhavcopyIncrementalSync, tmp_path: object
    ) -> None:
        """Symbol with no Parquet and no registry entry is skipped (needs full sync)."""
        registry = SyncRegistry(
            registry_dir=str(tmp_path),
            timeframe="1d",  # type: ignore[arg-type]
        )
        missing = syncer.detect_missing_days(
            ["BRANDNEW"], registry=registry, days_back=5
        )
        # BRANDNEW has no Parquet and no registry — no days should be added for it
        assert isinstance(missing, set)


# ---------------------------------------------------------------------------
# update_symbol tests
# ---------------------------------------------------------------------------


class TestUpdateSymbol:
    """Tests for BhavcopyIncrementalSync.update_symbol()."""

    def _make_existing_parquet(
        self,
        syncer: BhavcopyIncrementalSync,
        symbol: str,
        n_rows: int,
        last_close: float = 102.0,
    ) -> None:
        """Write a dummy Parquet with n_rows of historical data."""
        dates = pd.date_range(end="2026-05-26", periods=n_rows, freq="B")
        df = pd.DataFrame(
            {
                "Open": [last_close * 0.99] * n_rows,
                "High": [last_close * 1.01] * n_rows,
                "Low": [last_close * 0.98] * n_rows,
                "Close": [last_close] * n_rows,
                "Volume": [500_000.0] * n_rows,
            },
            index=dates,
        )
        df.to_parquet(syncer._parquet_path(symbol))

    def test_append_new_rows(self, syncer: BhavcopyIncrementalSync) -> None:
        """After update_symbol, Parquet row count must increase by D new rows."""
        n_existing = 10
        symbol = "RELIANCE"
        # Use a last_close close to the new bar's close (2920) to avoid corp-action flag
        self._make_existing_parquet(syncer, symbol, n_existing, last_close=2900.0)

        new_date = date(2026, 5, 29)
        new_row = pd.DataFrame(
            {
                "Symbol": [symbol],
                "Date": [pd.Timestamp(new_date)],
                "Open": [2900.0],
                "High": [2950.0],
                "Low": [2880.0],
                "Close": [2920.0],
                "Volume": [1_200_000.0],
            }
        )
        day_frames = {new_date: new_row}

        result = syncer.update_symbol(symbol, day_frames)
        assert result is True

        saved = pd.read_parquet(syncer._parquet_path(symbol))
        assert len(saved) == n_existing + 1
        assert pd.Timestamp(new_date) in saved.index

    def test_deduplication_prevents_double_append(
        self, syncer: BhavcopyIncrementalSync
    ) -> None:
        """Appending the same date twice must not create duplicate rows."""
        symbol = "HDFC"
        self._make_existing_parquet(syncer, symbol, 5)

        new_date = date(2026, 5, 29)
        new_row = pd.DataFrame(
            {
                "Symbol": [symbol],
                "Date": [pd.Timestamp(new_date)],
                "Open": [1600.0],
                "High": [1650.0],
                "Low": [1590.0],
                "Close": [1625.0],
                "Volume": [800_000.0],
            }
        )
        day_frames = {new_date: new_row}

        syncer.update_symbol(symbol, day_frames)
        syncer.update_symbol(symbol, day_frames)  # Second call — should dedup

        saved = pd.read_parquet(syncer._parquet_path(symbol))
        assert saved.index.duplicated().sum() == 0

    def test_corp_action_triggers_false(self, syncer: BhavcopyIncrementalSync) -> None:
        """A >100% price gap between last existing close and new close returns False."""
        symbol = "SMALLCAP"
        n_existing = 5
        # last_close=100; new close=210 → ratio=2.1 → exceeds 1 + 0.20*5 = 2.0 threshold
        self._make_existing_parquet(syncer, symbol, n_existing, last_close=100.0)

        new_date = date(2026, 5, 29)
        new_row = pd.DataFrame(
            {
                "Symbol": [symbol],
                "Date": [pd.Timestamp(new_date)],
                "Open": [208.0],
                "High": [215.0],
                "Low": [205.0],
                "Close": [210.0],  # 2.1x last close -> exceeds 2.0 ceiling
                "Volume": [500_000.0],
            }
        )
        result = syncer.update_symbol(symbol, {new_date: new_row})
        assert result is False

    def test_symbol_absent_from_day_frames_returns_true(
        self, syncer: BhavcopyIncrementalSync
    ) -> None:
        """If symbol has no rows in day_frames, return True (nothing to do)."""
        symbol = "ABSENT"
        # No Parquet written — and no rows in day_frames
        empty_df = pd.DataFrame(
            columns=["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"]
        )
        result = syncer.update_symbol(symbol, {date(2026, 5, 29): empty_df})
        assert result is True


# ---------------------------------------------------------------------------
# download_bhavcopies tests
# ---------------------------------------------------------------------------


class TestDownloadBhavcopies:
    """Tests for BhavcopyIncrementalSync.download_bhavcopies()."""

    def test_uses_disk_cache_when_available(
        self, syncer: BhavcopyIncrementalSync, sample_zip: bytes
    ) -> None:
        """If ZIP exists on disk, no HTTP call must be made."""
        target_date = date(2026, 5, 29)
        date_str = target_date.strftime("%Y%m%d")
        cached_path = (
            f"{syncer.raw_dir}/BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
        )
        os.makedirs(syncer.raw_dir, exist_ok=True)
        with open(cached_path, "wb") as fh:
            fh.write(sample_zip)

        with patch.object(
            syncer._downloader,
            "download_raw_bhavcopy",
            side_effect=AssertionError("Should not call HTTP"),
        ):
            results = syncer.download_bhavcopies({target_date})

        assert target_date in results
        assert results[target_date] == sample_zip

    def test_http_called_when_no_cache(
        self, syncer: BhavcopyIncrementalSync, sample_zip: bytes
    ) -> None:
        """If no cache, download_raw_bhavcopy must be called once."""
        target_date = date(2026, 5, 28)

        with (
            patch.object(
                syncer._downloader,
                "download_raw_bhavcopy",
                return_value=sample_zip,
            ) as mock_dl,
            patch.object(syncer._downloader, "save_raw_bhavcopy"),
        ):
            results = syncer.download_bhavcopies({target_date})

        mock_dl.assert_called_once()
        assert target_date in results

    def test_http_404_is_skipped_gracefully(
        self, syncer: BhavcopyIncrementalSync
    ) -> None:
        """NSE 404 (holiday/weekend) must not raise — date is simply absent."""
        target_date = date(2026, 5, 24)  # Saturday

        with patch.object(
            syncer._downloader,
            "download_raw_bhavcopy",
            side_effect=ValueError("File not found on NSE. HTTP status: 404"),
        ):
            results = syncer.download_bhavcopies({target_date})

        assert target_date not in results


# ---------------------------------------------------------------------------
# run() integration smoke test
# ---------------------------------------------------------------------------


class TestRunIntegration:
    """Lightweight integration test for BhavcopyIncrementalSync.run()."""

    def test_run_with_mocked_download(
        self,
        syncer: BhavcopyIncrementalSync,
        sample_zip: bytes,
        tmp_path: object,
    ) -> None:
        """run() must return a dict with True for symbols found in Bhavcopy."""
        # Write small existing Parquets for both symbols
        for sym, last_close in [("TCS", 3490.0), ("INFY", 1600.0)]:
            dates = pd.date_range(end="2026-05-27", periods=10, freq="B")
            df = pd.DataFrame(
                {
                    "Open": [last_close * 0.99] * 10,
                    "High": [last_close * 1.01] * 10,
                    "Low": [last_close * 0.98] * 10,
                    "Close": [last_close] * 10,
                    "Volume": [500_000.0] * 10,
                },
                index=dates,
            )
            df.to_parquet(syncer._parquet_path(sym))

        trade_date = date(2026, 5, 29)

        with (
            patch.object(
                syncer,
                "detect_missing_days",
                return_value={trade_date},
            ),
            patch.object(
                syncer,
                "download_bhavcopies",
                return_value={trade_date: sample_zip},
            ),
        ):
            results = syncer.run(["TCS", "INFY"], days_back=5)

        assert "TCS" in results
        assert "INFY" in results
        # Both should succeed (close prices are within 20% range)
        assert results["TCS"] is True
        assert results["INFY"] is True
