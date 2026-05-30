"""
File: src/nse_bhavcopy/bhavcopy_incremental.py
Purpose: Fast batch incremental OHLCV update via NSE Bhavcopy ZIPs.
Last Modified: 2026-05-30
"""

import logging
import os
import time
from datetime import date, datetime, timedelta

import pandas as pd

from src.storage.downloader import BhavcopyDownloader
from src.storage.sync_registry import SyncRegistry, _last_trading_day

LOGGER: logging.Logger = logging.getLogger(__name__)

# Corporate-action sanity threshold — price gap beyond this triggers full refresh
_CORP_ACTION_THRESHOLD: float = 0.20


class BhavcopyIncrementalSync:
    """
    Download batch Bhavcopy ZIPs and append OHLCV rows into per-symbol Parquets.

    Design Rationale:
        Instead of 1 HTTP call per symbol (1 800+ calls/day), this class makes
        1 HTTP call per *trading day* that is missing, parses all EQ symbols
        from each ZIP, and appends the rows to the relevant Parquet files.

    Attributes:
        data_dir (str): Root historical data directory.
        timeframe (str): Candle resolution — only '1d' is supported for Bhavcopy.
        raw_dir (str): Directory where raw Bhavcopy ZIPs are cached.
        rate_delay (float): Seconds to sleep between consecutive ZIP downloads.
        recompute_ta (bool): Whether to recompute TA indicators after appending.

    Public Methods:
        - detect_missing_days(symbols): Return set of trading dates to fill.
        - download_bhavcopies(dates): Fetch+cache ZIPs; skip if already on disk.
        - update_symbol(symbol, day_frames): Append rows, dedup, save Parquet.
        - run(symbols, days_back, recompute_ta): Orchestrate full incremental sync.

    Thread Safety: No — file I/O is not thread-safe across calls for same symbol.
    """

    def __init__(
        self,
        data_dir: str = "data/historical",
        timeframe: str = "1d",
        raw_dir: str = "data/raw",
        rate_delay: float = 1.0,
        recompute_ta: bool = True,
    ) -> None:
        """
        Initialise BhavcopyIncrementalSync with directory paths and options.

        Parameters:
            data_dir (str): Historical Parquet storage root. | Writable path.
            timeframe (str): Only '1d' is meaningful for Bhavcopy. | Default '1d'.
            raw_dir (str): Cache directory for raw Bhavcopy ZIPs. | Writable path.
            rate_delay (float): Sleep between ZIP downloads in seconds. | >= 0.
            recompute_ta (bool): Run TA-Lib indicators after each symbol append.

        Returns:
            None

        Raises:
            OSError: If directory creation fails.

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> syncer = BhavcopyIncrementalSync()
        """
        self.data_dir: str = data_dir
        self.timeframe: str = timeframe
        self.raw_dir: str = raw_dir
        self.rate_delay: float = rate_delay
        self.recompute_ta: bool = recompute_ta
        self._tf_dir: str = os.path.join(data_dir, timeframe)

        os.makedirs(self._tf_dir, exist_ok=True)
        os.makedirs(self.raw_dir, exist_ok=True)

        self._downloader: BhavcopyDownloader = BhavcopyDownloader(
            raw_dir=raw_dir,
            processed_dir=os.path.join(os.path.dirname(raw_dir), "processed"),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parquet_path(self, symbol: str) -> str:
        """Return the full Parquet file path for a symbol."""
        return os.path.join(self._tf_dir, f"{symbol.upper()}.parquet")

    def _load(self, symbol: str) -> pd.DataFrame:
        """
        Load the existing Parquet for a symbol, returning empty DataFrame if absent.

        Parameters:
            symbol (str): NSE equity symbol. | Uppercase preferred.

        Returns:
            pd.DataFrame: Existing OHLCV data with DatetimeIndex, or empty DataFrame.

        Raises:
            None

        Complexity:
            Time: O(N) [N rows in Parquet]
            Space: O(N)

        Example:
            >>> df = syncer._load("TCS")
        """
        path = self._parquet_path(symbol)
        if not os.path.exists(path):
            return pd.DataFrame()
        try:
            df: pd.DataFrame = pd.read_parquet(path)
            if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            return df
        except Exception as exc:
            LOGGER.warning("Failed to load Parquet for %s: %s - skipping.", symbol, exc)
            return pd.DataFrame()

    def _save(self, symbol: str, df: pd.DataFrame) -> None:
        """
        Deduplicate, sort, optionally compute TA indicators, and save Parquet.

        Parameters:
            symbol (str): NSE equity symbol. | Uppercase preferred.
            df (pd.DataFrame): Updated OHLCV DataFrame with DatetimeIndex.

        Returns:
            None

        Raises:
            None — errors are logged and swallowed to keep the run going.

        Complexity:
            Time: O(N log N) [sorting]
            Space: O(N)

        Example:
            >>> syncer._save("TCS", updated_df)
        """
        if df.empty:
            return
        df = df[~df.index.duplicated(keep="last")].sort_index()
        path = self._parquet_path(symbol)
        try:
            if self.recompute_ta:
                from src.nse_bhavcopy.ta_indicators import add_ta_indicators

                df = add_ta_indicators(df)
            df.to_parquet(path)
            LOGGER.debug("Saved %d rows → %s", len(df), path)
        except Exception as exc:
            LOGGER.error("Failed to save Parquet for %s: %s", symbol, exc)

    @staticmethod
    def _get_trading_days(start: date, end: date) -> list[date]:
        """
        Return a list of weekday dates between start and end (inclusive).

        Uses weekday logic as a lightweight fallback; NSE calendar holidays may
        cause harmless 404s which are handled gracefully in download_bhavcopies().

        Parameters:
            start (date): First date (inclusive). | Must be <= end.
            end (date): Last date (inclusive). | Must be >= start.

        Returns:
            list[date]: Weekday dates in ascending order.

        Raises:
            None

        Complexity:
            Time: O(D) [D = number of calendar days in range]
            Space: O(D)

        Example:
            >>> days = BhavcopyIncrementalSync._get_trading_days(
            ...     date(2026, 5, 26), date(2026, 5, 30))
        """
        days: list[date] = []
        current = start
        while current <= end:
            if current.weekday() < 5:  # Mon-Fri
                days.append(current)
            current += timedelta(days=1)
        return days

    # ------------------------------------------------------------------
    # Core public methods
    # ------------------------------------------------------------------

    def detect_missing_days(
        self,
        symbols: list[str],
        registry: SyncRegistry | None = None,
        days_back: int = 10,
    ) -> set[date]:
        """
        Compute the union of trading dates missing across all held Parquets.

        For each symbol, examines the last known bar date and collects all
        weekday dates between that date+1 and the most recent trading day.

        Parameters:
            symbols (list[str]): EQ symbols to inspect. | Non-empty list.
            registry (SyncRegistry | None): Optional pre-loaded registry. |
                A fresh registry is loaded from disk if None.
            days_back (int): Safety cap — look back at most this many calendar
                days. | Must be positive. Default 10.

        Returns:
            set[date]: Set of trading dates that need to be fetched.

        Raises:
            None

        Complexity:
            Time: O(S) [S = number of symbols]
            Space: O(D) [D = distinct missing dates]

        Example:
            >>> missing = syncer.detect_missing_days(["TCS", "INFY"])
            >>> print(sorted(missing))
        """
        if registry is None:
            registry = SyncRegistry(
                registry_dir=self.data_dir, timeframe=self.timeframe
            )
            registry.load()

        last_trading = _last_trading_day()
        earliest_allowed: date = last_trading - timedelta(days=days_back)
        missing: set[date] = set()

        for raw_sym in symbols:
            sym = raw_sym.strip().upper()
            rec = registry.get(sym)

            if rec is not None and rec.last_bar_date is not None:
                last_known: date = rec.last_bar_date
            else:
                # No registry entry — also check Parquet directly
                df = self._load(sym)
                if not df.empty:
                    last_known = df.index.max().date()
                else:
                    # Symbol completely new — needs full history, not incremental
                    continue

            if last_known >= last_trading:
                continue  # Already current

            fill_from = max(last_known + timedelta(days=1), earliest_allowed)
            days = self._get_trading_days(fill_from, last_trading)
            missing.update(days)

        LOGGER.info(
            "detect_missing_days: %d unique trading days to fill across %d symbols.",
            len(missing),
            len(symbols),
        )
        return missing

    def download_bhavcopies(self, dates: set[date]) -> dict[date, bytes]:
        """
        Download (or load from cache) Bhavcopy ZIPs for each requested date.

        Checks if the ZIP already exists in raw_dir before making an HTTP call.
        NSE holiday dates will return a 404 — these are silently skipped.

        Parameters:
            dates (set[date]): Trading dates to fetch. | Non-empty set.

        Returns:
            dict[date, bytes]: Mapping of date → raw ZIP bytes for successful
                downloads only (holiday/error dates are absent from the dict).

        Raises:
            None — individual failures are logged and skipped.

        Complexity:
            Time: O(D * N) [D = dates, N = network latency per ZIP, ~2MB each]
            Space: O(D * M) [M = ZIP size in memory]

        Example:
            >>> zips = syncer.download_bhavcopies({date(2026, 5, 29)})
        """
        results: dict[date, bytes] = {}

        for d in sorted(dates):
            dt = datetime(d.year, d.month, d.day)
            date_str = d.strftime("%Y%m%d")
            cached_path = os.path.join(
                self.raw_dir,
                f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip",
            )

            if os.path.exists(cached_path):
                LOGGER.info("Cache hit for %s — loading from disk.", date_str)
                try:
                    with open(cached_path, "rb") as fh:
                        results[d] = fh.read()
                    continue
                except OSError as exc:
                    LOGGER.warning("Cache read failed for %s: %s", date_str, exc)

            try:
                raw_bytes = self._downloader.download_raw_bhavcopy(dt)
                # Persist to disk cache for next run
                self._downloader.save_raw_bhavcopy(dt, raw_bytes)
                results[d] = raw_bytes
                LOGGER.info(
                    "Downloaded Bhavcopy for %s (%d bytes).",
                    date_str,
                    len(raw_bytes),
                )
                time.sleep(self.rate_delay)
            except ValueError:
                LOGGER.info(
                    "Bhavcopy not available for %s "
                    "(likely holiday/weekend) - skipping.",
                    date_str,
                )
            except Exception as exc:
                LOGGER.warning("Failed to download Bhavcopy for %s: %s", date_str, exc)

        LOGGER.info(
            "download_bhavcopies: %d/%d dates fetched successfully.",
            len(results),
            len(dates),
        )
        return results

    def update_symbol(
        self,
        symbol: str,
        day_frames: dict[date, pd.DataFrame],
        registry: SyncRegistry | None = None,
    ) -> bool:
        """
        Append new OHLCV rows from day_frames into the symbol's Parquet.

        Checks for corporate-action price gaps (>20% single-day jump) and
        triggers a full-refresh flag rather than appending potentially bad data.

        Parameters:
            symbol (str): NSE equity symbol. | Uppercase.
            day_frames (dict[date, pd.DataFrame]): Mapping of date → single-row
                OHLCV DataFrame for that date. | Keys must be trading dates.
            registry (SyncRegistry | None): Registry to update on success. |
                If None, registry update is skipped (caller should handle it).

        Returns:
            bool: True if append succeeded, False if symbol needs full refresh.

        Raises:
            None — errors are logged and False is returned.

        Complexity:
            Time: O(D + N) [D new rows, N existing rows for dedup+sort]
            Space: O(N + D)

        Example:
            >>> ok = syncer.update_symbol("TCS", {date(2026, 5, 29): row_df})
        """
        sym = symbol.strip().upper()

        new_rows: list[pd.DataFrame] = []
        for d in sorted(day_frames):
            row_df = day_frames[d]
            sym_rows = row_df[row_df["Symbol"] == sym]
            if sym_rows.empty:
                continue
            new_rows.append(sym_rows)

        if not new_rows:
            return True  # Nothing to do — not a failure

        new_df = pd.concat(new_rows, ignore_index=True)
        new_df.index = pd.to_datetime(new_df["Date"])
        new_df = new_df.drop(columns=["Symbol", "Date"], errors="ignore")

        existing = self._load(sym)

        if not existing.empty:
            # Corporate action sanity check - compare last existing close
            # against first new close
            last_close = float(existing["Close"].iloc[-1])
            first_new_close = float(new_df["Close"].iloc[0])
            if last_close > 0 and first_new_close > 0:
                ratio = first_new_close / last_close
                if ratio < (1 - _CORP_ACTION_THRESHOLD) or ratio > (
                    1 + _CORP_ACTION_THRESHOLD * 5
                ):
                    LOGGER.warning(
                        "%s: Large price ratio %.3f detected - "
                        "needs full refresh instead of incremental append.",
                        sym,
                        ratio,
                    )
                    return False  # Caller should trigger full refresh

            merged = pd.concat([existing, new_df])
        else:
            merged = new_df

        self._save(sym, merged)

        if registry is not None:
            registry.mark_done(
                sym,
                first_bar=merged.index.min().date(),
                last_bar=merged.index.max().date(),
                row_count=len(merged),
            )

        return True

    def run(
        self,
        symbols: list[str],
        days_back: int = 10,
        recompute_ta: bool = True,
    ) -> dict[str, bool]:
        """
        Orchestrate the full Bhavcopy incremental sync for all given symbols.

        Flow:
            1. Load sync registry.
            2. Detect missing trading days across the symbol universe.
            3. Download only the required Bhavcopy ZIPs (with disk caching).
            4. Parse each ZIP once into a date-keyed dict of DataFrames.
            5. For each symbol: append rows, handle corp-action fallback,
               update registry.
            6. Save registry checkpoint.

        Parameters:
            symbols (list[str]): EQ symbols to update. | Non-empty list.
            days_back (int): Max days back to look for missing data. | Default 10.
            recompute_ta (bool): Recompute TA indicators after each append. |
                Default True. Set False for speed when TA is recomputed separately.

        Returns:
            dict[str, bool]: Map of symbol → True (success) / False (needs
                full refresh or errored).

        Raises:
            None — all errors are caught and logged.

        Complexity:
            Time: O(D * N + S * N) [D dates, S symbols, N rows per Bhavcopy]
            Space: O(D * N) [D parsed DataFrames in memory simultaneously]

        Example:
            >>> results = syncer.run(["TCS", "INFY", "RELIANCE"], days_back=5)
            >>> print(sum(results.values()), "symbols updated")
        """
        self.recompute_ta = recompute_ta

        registry = SyncRegistry(registry_dir=self.data_dir, timeframe=self.timeframe)
        registry.load()
        registry.register(symbols)

        # Step 1: Which days do we actually need?
        missing_days = self.detect_missing_days(
            symbols, registry=registry, days_back=days_back
        )

        if not missing_days:
            LOGGER.info("All %d symbols are already up to date.", len(symbols))
            return {s.strip().upper(): True for s in symbols}

        # Step 2: Download those Bhavcopies (1 HTTP call per day)
        raw_zips = self.download_bhavcopies(missing_days)

        if not raw_zips:
            LOGGER.warning("No Bhavcopies were downloaded — NSE may be on holiday.")
            return {s.strip().upper(): True for s in symbols}

        # Step 3: Parse each ZIP once → dict[date → DataFrame]
        day_frames: dict[date, pd.DataFrame] = {}
        for d, zip_bytes in raw_zips.items():
            dt = datetime(d.year, d.month, d.day)
            try:
                day_frames[d] = self._downloader.parse_bhavcopy_ohlcv(zip_bytes, dt)
            except Exception as exc:
                LOGGER.error(
                    "Failed to parse Bhavcopy for %s: %s",
                    d.strftime("%Y-%m-%d"),
                    exc,
                )

        if not day_frames:
            LOGGER.error("No valid Bhavcopy data parsed — aborting incremental sync.")
            return {s.strip().upper(): False for s in symbols}

        # Step 4: Update each symbol
        results: dict[str, bool] = {}
        total = len(symbols)
        needs_full_refresh: list[str] = []

        for i, raw_sym in enumerate(symbols, 1):
            sym = raw_sym.strip().upper()
            LOGGER.info("[%d/%d] Incremental append: %s", i, total, sym)
            try:
                ok = self.update_symbol(sym, day_frames, registry=registry)
                results[sym] = ok
                if not ok:
                    needs_full_refresh.append(sym)
            except Exception as exc:
                LOGGER.error("update_symbol failed for %s: %s", sym, exc)
                results[sym] = False

        registry.save()

        ok_count = sum(v for v in results.values())
        LOGGER.info(
            "Bhavcopy incremental sync complete: %d/%d symbols updated, "
            "%d need full refresh.",
            ok_count,
            total,
            len(needs_full_refresh),
        )

        if needs_full_refresh:
            LOGGER.info(
                "Symbols needing full refresh (%d): %s",
                len(needs_full_refresh),
                ", ".join(needs_full_refresh[:20]),
            )

        return results
