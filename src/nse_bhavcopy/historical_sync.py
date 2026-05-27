"""
File: src/nse_bhavcopy/historical_sync.py
Purpose: Download and incrementally update per-symbol Parquet historical data.

Dependencies:
External:
- pandas>=2.2.3: DataFrame operations, Parquet read/write
Internal:
- src.data.fetcher.prices.base: [AbstractPriceFetcher]
- src.data.fetcher.prices.yfinance_fetcher: [YFinanceFetcher]
- src.nse_bhavcopy.sync_registry: [SyncRegistry, _last_trading_day]

Key Components:
Classes:
- HistoricalSync: Manages full-history download and incremental CRUD via Parquet.
"""

import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from src.data.fetcher.prices.base import AbstractPriceFetcher
from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher
from src.nse_bhavcopy.sync_registry import SyncRegistry, _last_trading_day

LOGGER: logging.Logger = logging.getLogger(__name__)


class HistoricalSync:
    """
    Manages full historical download and incremental daily CRUD for NSE equities.

    Key Design Decisions:
        - When a symbol has < 80% expected row coverage, triggers FULL REFRESH
          instead of incremental (gaps in history need backfill).
        - Uses trading calendar (not calendar days) for "current" detection.
        - All date comparisons use _last_trading_day() to handle weekends/holidays.
    """

    # Coverage threshold: below this, treat as partial data and do full refresh
    COVERAGE_THRESHOLD: float = 0.8

    def __init__(
        self,
        data_dir: str = "data/historical",
        timeframe: str = "1d",
        start_date: str = "2000-01-01",
        rate_delay: float = 0.5,
        fetcher: AbstractPriceFetcher | None = None,
    ) -> None:
        self.data_dir: str = data_dir
        self.timeframe: str = timeframe
        self.start_date: str = start_date
        self.rate_delay: float = rate_delay
        self.fetcher: AbstractPriceFetcher = fetcher or YFinanceFetcher()

        self._tf_dir: str = os.path.join(data_dir, timeframe)
        os.makedirs(self._tf_dir, exist_ok=True)

    def _parquet_path(self, symbol: str) -> str:
        return os.path.join(self._tf_dir, f"{symbol.upper()}.parquet")

    def _load(self, symbol: str) -> pd.DataFrame:
        path = self._parquet_path(symbol)
        if not os.path.exists(path):
            return pd.DataFrame()
        try:
            df = pd.read_parquet(path)
            if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            return df
        except Exception as exc:
            LOGGER.warning("Failed to load Parquet for %s: %s", symbol, exc)
            try:
                os.remove(path)
                LOGGER.info(
                    "Deleted corrupted Parquet file for %s to trigger re-sync.", symbol
                )
            except OSError:
                pass
            return pd.DataFrame()

    def _save(self, symbol: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        df = df[~df.index.duplicated(keep="last")].sort_index()
        path = self._parquet_path(symbol)
        try:
            from src.nse_bhavcopy.ta_indicators import add_ta_indicators

            df = add_ta_indicators(df)
            df.to_parquet(path)
            LOGGER.debug("Saved %d rows → %s", len(df), path)
        except Exception as exc:
            LOGGER.error("Failed to save Parquet for %s: %s", symbol, exc)

    def recompute_all_ta(self) -> None:
        """
        Iterate over all existing Parquet files and recompute their TA-Lib indicators.

        Parameters:
            None

        Returns:
            None

        Raises:
            None

        Complexity:
            Time: O(S * N) [S symbols, N historical bars]
            Space: O(N) [Dataframe size per symbol]
        """
        import glob

        from src.nse_bhavcopy.ta_indicators import add_ta_indicators

        pattern = os.path.join(self._tf_dir, "*.parquet")
        files = glob.glob(pattern)
        LOGGER.info("Recomputing TA indicators for %d files...", len(files))

        success_count = 0
        for path in files:
            symbol = os.path.basename(path).replace(".parquet", "")
            try:
                df = pd.read_parquet(path)
                if not df.empty:
                    df = add_ta_indicators(df)
                    df.to_parquet(path)
                    success_count += 1
            except Exception as exc:
                LOGGER.error("Failed to recompute TA for %s: %s", symbol, exc)

        LOGGER.info(
            "Successfully recomputed TA indicators for %d/%d files.",
            success_count,
            len(files),
        )

    def _estimate_expected_rows(self, first_date: date, last_date: date) -> int:
        """Rough estimate of trading days between two dates."""
        if first_date >= last_date:
            return 0
        years = (last_date - first_date).days / 365.25
        return int(years * 252)

    def _needs_full_refresh(self, df: pd.DataFrame) -> bool:
        """
        Check if existing data has gaps that require full re-download.

        Logic:
            - If < 2 rows: definitely needs full refresh.
            - If coverage < 80% of expected trading days: gaps likely.
            - If last bar is > 7 days old AND we have few rows: full refresh.
        """
        if len(df) < 2:
            return True

        first_date = df.index.min().date()
        last_date = df.index.max().date()
        trading_day = _last_trading_day()

        expected = self._estimate_expected_rows(first_date, last_date)
        if expected > 50:  # Meaningful history
            coverage = len(df) / expected
            if coverage < self.COVERAGE_THRESHOLD:
                LOGGER.info(
                    "Low coverage %.1f%% (%d/%d rows) — triggering full refresh.",
                    coverage * 100,
                    len(df),
                    expected,
                )
                return True

        # If data ends very old and we have few rows, probably partial
        days_stale = (trading_day - last_date).days
        if days_stale > 7 and len(df) < 100:
            LOGGER.info(
                "Data ends %d days ago with only %d rows — full refresh.",
                days_stale,
                len(df),
            )
            return True

        return False

    def _fetch_full(self, symbol: str) -> pd.DataFrame:
        """Download complete history from start_date to today."""
        from_dt = datetime.strptime(self.start_date, "%Y-%m-%d")
        to_dt = datetime.now().replace(hour=23, minute=59, second=59)

        LOGGER.info("Full history download: %s from %s", symbol, self.start_date)

        df = self.fetcher.fetch(
            symbol,
            timeframe=self.timeframe,
            from_date=int(from_dt.timestamp()),
            to_date=int(to_dt.timestamp()),
        )

        if df.empty:
            LOGGER.warning("No data fetched for %s", symbol)
            return pd.DataFrame()

        LOGGER.info(
            "Full history %s: %d total rows (%s → %s)",
            symbol,
            len(df),
            df.index.min().date(),
            df.index.max().date(),
        )
        return df

    def _incremental_update(self, symbol: str, existing: pd.DataFrame) -> pd.DataFrame:
        """Fetch only missing bars since the last saved date and merge them."""
        last_date: datetime = existing.index.max().to_pydatetime()
        from_dt = last_date - timedelta(days=5)
        to_dt = datetime.now().replace(hour=23, minute=59, second=59)

        LOGGER.info("Incremental update %s from %s", symbol, from_dt.date())
        new_data = self.fetcher.fetch(
            symbol,
            timeframe=self.timeframe,
            from_date=int(from_dt.timestamp()),
            to_date=int(to_dt.timestamp()),
        )

        if new_data.empty:
            LOGGER.info("%s is already up to date.", symbol)
            return existing

        # Check for corporate action split/bonus adjustments
        overlap_dates = existing.index.intersection(new_data.index)
        if not overlap_dates.empty:
            overlap_date = overlap_dates[-1]
            old_val = existing.loc[overlap_date, "Close"]
            new_val = new_data.loc[overlap_date, "Close"]
            if isinstance(old_val, pd.Series):
                old_val = old_val.iloc[-1]
            if isinstance(new_val, pd.Series):
                new_val = new_val.iloc[-1]

            if old_val > 0 and new_val > 0:
                ratio = new_val / old_val
                if ratio < 0.95 or ratio > 1.05:
                    factor = None
                    for std_factor in [0.5, 0.2, 0.1, 1 / 1.5, 0.8, 1 / 3, 1 / 4]:
                        if abs(ratio - std_factor) < 0.05:
                            factor = std_factor
                            break
                    if factor is not None:
                        LOGGER.info(
                            "Corporate action detected for %s: ratio %.3f. "
                            "Adjusting historical prices by factor %.3f.",
                            symbol,
                            ratio,
                            factor,
                        )
                        for col in ["Open", "High", "Low", "Close"]:
                            if col in existing.columns:
                                existing[col] = existing[col] * factor
                        if "Volume" in existing.columns:
                            existing["Volume"] = existing["Volume"] / factor
                    else:
                        LOGGER.info(
                            "Significant price adjustment (ratio %.3f) detected "
                            "for %s. Triggering full history refresh.",
                            ratio,
                            symbol,
                        )
                        return self._fetch_full(symbol)
        else:
            # Check gap ratio between last existing close and first new close
            last_existing_close = existing["Close"].iloc[-1]
            first_new_close = new_data["Close"].iloc[0]
            if last_existing_close > 0:
                ratio = first_new_close / last_existing_close
                if ratio < 0.79:  # daily limit drop of >21%
                    factor = None
                    for std_factor in [0.5, 0.2, 0.1, 1 / 1.5, 0.8, 1 / 3, 1 / 4]:
                        if abs(ratio - std_factor) < 0.05:
                            factor = std_factor
                            break
                    if factor is not None:
                        LOGGER.info(
                            "Corporate action detected for %s: ratio %.3f. "
                            "Adjusting historical prices by factor %.3f.",
                            symbol,
                            ratio,
                            factor,
                        )
                        for col in ["Open", "High", "Low", "Close"]:
                            if col in existing.columns:
                                existing[col] = existing[col] * factor
                        if "Volume" in existing.columns:
                            existing["Volume"] = existing["Volume"] / factor
                    else:
                        LOGGER.info(
                            "Large price drop (ratio %.3f) detected for %s. "
                            "Triggering full history refresh.",
                            ratio,
                            symbol,
                        )
                        return self._fetch_full(symbol)

        merged = pd.concat([existing, new_data])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
        added = len(merged) - len(existing)

        if added == 0:
            LOGGER.info(
                "Incremental %s: +0 new rows (YFinance data not yet updated)", symbol
            )
            return existing

        LOGGER.info(
            "Incremental %s: +%d new rows (total %d)", symbol, added, len(merged)
        )
        return merged

    def sync_one(self, symbol: str, force: bool = False) -> bool:
        """
        Synchronise historical data for a single NSE equity symbol.

        Smart path selection:
            - No existing file → full download
            - Existing file with gaps/low coverage → full download (gap fill)
            - Existing file, current, good coverage → incremental update
        """
        symbol = symbol.strip().upper()
        existing = self._load(symbol)

        if existing.empty:
            # Case 1: Never downloaded → full history
            df = self._fetch_full(symbol)
        elif self._needs_full_refresh(existing):
            # Case 2: Partial/gappy data → full refresh to fill gaps
            LOGGER.info(
                "%s: Existing data has gaps (%d rows, %s → %s). Running full refresh.",
                symbol,
                len(existing),
                existing.index.min().date(),
                existing.index.max().date(),
            )
            df = self._fetch_full(symbol)
            # Only use new data if it's better than existing
            if not df.empty and len(df) >= len(existing):
                LOGGER.info(
                    "%s: Full refresh improved from %d to %d rows.",
                    symbol,
                    len(existing),
                    len(df),
                )
            elif not df.empty:
                LOGGER.warning(
                    "%s: Full refresh got fewer rows (%d < %d), "
                    "keeping existing + incremental.",
                    symbol,
                    len(df),
                    len(existing),
                )
                df = self._incremental_update(symbol, existing)
            else:
                df = existing  # Keep what we have
        else:
            # Case 3: Good data, just need recent bars → incremental
            df = self._incremental_update(symbol, existing)

        if df.empty:
            LOGGER.warning("No data found for %s — marked failed.", symbol)
            return False

        if df is existing:
            LOGGER.info(
                "No new data for %s yet, marked as synced for cooldown.", symbol
            )
            return True

        self._save(symbol, df)
        return True

    def sync(
        self,
        symbols: list[str],
        resume: bool = True,
        registry: SyncRegistry | None = None,
        save_every: int = 50,
    ) -> dict[str, bool]:
        """
        Synchronise historical data using a registry-driven priority queue.

        When resume=True, already-current symbols are skipped with ZERO I/O.
        """
        if registry is None:
            registry = SyncRegistry(
                registry_dir=self.data_dir, timeframe=self.timeframe
            )
            registry.load()

        registry.register(symbols)

        if resume:
            queue = registry.pending_symbols()
        else:
            queue = [s.strip().upper() for s in symbols]

        skipped = {
            s.strip().upper(): True for s in symbols if s.strip().upper() not in queue
        }

        total = len(queue)
        LOGGER.info(
            "Sync queue: %d symbols to process (%d already current, skipped).",
            total,
            len(skipped),
        )

        if not queue:
            LOGGER.info("All %d symbols are already up to date.", len(symbols))
            return {**skipped}

        results: dict[str, bool] = {**skipped}

        for i, sym in enumerate(queue, 1):
            LOGGER.info("[%d/%d] Syncing %s...", i, total, sym)
            ok = self.sync_one(sym)
            results[sym] = ok

            if ok:
                df = self._load(sym)
                if not df.empty:
                    registry.mark_done(
                        sym,
                        first_bar=df.index.min().date(),
                        last_bar=df.index.max().date(),
                        row_count=len(df),
                    )
            else:
                registry.mark_failed(sym)

            if i % save_every == 0:
                registry.save()
                LOGGER.info("Registry checkpoint saved at symbol %d.", i)

            time.sleep(self.rate_delay)

        registry.save()
        ok_count = sum(v for v in results.values())
        LOGGER.info(
            "Sync complete: %d/%d symbols succeeded (%d skipped as current).",
            ok_count,
            len(results),
            len(skipped),
        )
        return results

    def read(self, symbol: str) -> pd.DataFrame:
        return self._load(symbol)

    def status(self, symbols: list[str]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for sym in symbols:
            path = self._parquet_path(sym.upper())
            if os.path.exists(path):
                df = self._load(sym)
                first_date = df.index.min().date() if not df.empty else None
                last_date = df.index.max().date() if not df.empty else None
                expected = (
                    self._estimate_expected_rows(first_date, last_date)
                    if first_date and last_date
                    else 0
                )
                rows.append(
                    {
                        "symbol": sym.upper(),
                        "rows": len(df),
                        "expected_rows": expected,
                        "coverage_pct": round(len(df) / expected * 100, 1)
                        if expected > 0
                        else 0,
                        "first_date": first_date,
                        "last_date": last_date,
                        "parquet_path": path,
                    }
                )
            else:
                rows.append(
                    {
                        "symbol": sym.upper(),
                        "rows": 0,
                        "expected_rows": 0,
                        "coverage_pct": 0,
                        "first_date": None,
                        "last_date": None,
                        "parquet_path": path,
                    }
                )
        return pd.DataFrame(rows).sort_values("symbol")
