"""
File: src/nse_bhavcopy/historical_sync.py
Purpose: Download and incrementally update per-symbol Parquet historical data.

Dependencies:
External:
- pandas>=2.2.3: DataFrame operations, Parquet read/write
Internal:
- src.data.fetcher.prices.base: [AbstractPriceFetcher]
- src.data.fetcher.prices.yfinance_fetcher: [YFinanceFetcher]
- src.storage.sync_registry: [SyncRegistry, _last_trading_day]

Key Components:
Classes:
- HistoricalSync: Manages full-history download and incremental CRUD via Parquet.
"""

import logging
import os
import sqlite3
import tempfile
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd

from src.data.fetcher.prices.base import AbstractPriceFetcher
from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher
from src.nse_bhavcopy.fyers_fetcher import FyersAuthError
from src.nse_bhavcopy.ta_indicators import add_ta_indicators
from src.storage.sync_registry import SyncRegistry, _last_trading_day

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
        if fetcher is not None:
            self.fetcher: AbstractPriceFetcher = fetcher
        else:
            from src.core.data_sources import get_data_source_manager
            self.fetcher = get_data_source_manager().get_price_fetcher()

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

        # Ensure all technical indicators (RSI, MACD, EMAs, ATR, ADX, etc.) are up-to-date
        # Check if indicators need calculation or re-calculation due to new trailing bars with NaNs
        try:
            req_cols = {"Close", "High", "Low"}
            if req_cols.issubset(set(df.columns)):
                if "RSI_14" not in df.columns or pd.isna(df["RSI_14"].iloc[-1]):
                    df = add_ta_indicators(df)
        except Exception as exc:
            LOGGER.warning("Could not calculate TA indicators for %s during save: %s", symbol, exc)

        final_path = self._parquet_path(symbol)
        dir_name = os.path.dirname(final_path)
        os.makedirs(dir_name, exist_ok=True)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=dir_name, prefix=f".{symbol}_", suffix=".tmp", delete=False
            ) as tmp:
                tmp_path = tmp.name
            df.to_parquet(tmp_path)
            os.replace(tmp_path, final_path)
            tmp_path = None
            LOGGER.debug("Saved %d rows → %s", len(df), final_path)
        except Exception as exc:
            LOGGER.error("Failed to save Parquet for %s: %s", symbol, exc)
            raise
        finally:
            if tmp_path is not None and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

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

    def _trip_circuit_breaker(self, symbol: str) -> None:
        """Switch active fetcher to YFinance across the entire sync session on auth failure."""
        LOGGER.critical(
            "Fyers auth failure on %s. Tripping session circuit breaker: "
            "switching all remaining symbols to YFinanceFetcher.",
            symbol,
        )
        from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher
        self.fetcher = YFinanceFetcher()

    def _fetch_full(self, symbol: str) -> pd.DataFrame:
        """Download complete history from start_date to today."""
        from_dt = datetime.strptime(self.start_date, "%Y-%m-%d")
        to_dt = datetime.now().replace(hour=23, minute=59, second=59)

        LOGGER.info("Full history download: %s from %s", symbol, self.start_date)

        try:
            df = self.fetcher.fetch(
                symbol,
                timeframe=self.timeframe,
                from_date=int(from_dt.timestamp()),
                to_date=int(to_dt.timestamp()),
            )
        except FyersAuthError:
            self._trip_circuit_breaker(symbol)
            df = self.fetcher.fetch(
                symbol,
                timeframe=self.timeframe,
                from_date=int(from_dt.timestamp()),
                to_date=int(to_dt.timestamp()),
            )

        if getattr(self.fetcher, "access_token", "not_fyers") is None:
            self._trip_circuit_breaker(symbol)

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

    def _merge_and_adjust(
        self, symbol: str, existing: pd.DataFrame, new_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge newly fetched bars into existing DataFrame,
        handling splits and bonus adjustments.
        """
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

    def _incremental_update(self, symbol: str, existing: pd.DataFrame) -> pd.DataFrame:
        """Fetch only missing bars since the last saved date and merge them."""
        last_date: datetime = existing.index.max().to_pydatetime()
        from_dt = last_date - timedelta(days=5)
        to_dt = datetime.now().replace(hour=23, minute=59, second=59)

        LOGGER.info("Incremental update %s from %s", symbol, from_dt.date())
        try:
            new_data = self.fetcher.fetch(
                symbol,
                timeframe=self.timeframe,
                from_date=int(from_dt.timestamp()),
                to_date=int(to_dt.timestamp()),
            )
        except FyersAuthError:
            self._trip_circuit_breaker(symbol)
            new_data = self.fetcher.fetch(
                symbol,
                timeframe=self.timeframe,
                from_date=int(from_dt.timestamp()),
                to_date=int(to_dt.timestamp()),
            )

        if getattr(self.fetcher, "access_token", "not_fyers") is None:
            self._trip_circuit_breaker(symbol)

        return self._merge_and_adjust(symbol, existing, new_data)

    def _extract_symbol_from_batch(
        self, df_batch: pd.DataFrame, symbol: str
    ) -> pd.DataFrame:
        """Extract single-symbol OHLCV DataFrame from multi-ticker MultiIndex DataFrame."""
        if df_batch.empty or not isinstance(df_batch.columns, pd.MultiIndex):
            return pd.DataFrame()

        sym_clean = symbol.strip().upper()
        keys_to_try = [f"{sym_clean}.NS", sym_clean]

        found_key = None
        level_0 = df_batch.columns.get_level_values(0)
        for k in keys_to_try:
            if k in level_0:
                found_key = k
                break

        if found_key is None:
            return pd.DataFrame()

        try:
            df_sym = df_batch[found_key].dropna(how="all").copy()
            if df_sym.empty:
                return pd.DataFrame()
            if "Close" in df_sym.columns:
                df_sym = df_sym.dropna(subset=["Close"])
            cols = [
                c
                for c in ["Open", "High", "Low", "Close", "Volume"]
                if c in df_sym.columns
            ]
            if not cols:
                return pd.DataFrame()
            df_sym = df_sym[cols].astype(float)
            df_sym.index.name = "Date"
            if df_sym.index.tz is not None:
                df_sym.index = df_sym.index.tz_convert(None)
            return df_sym.sort_index()
        except Exception as exc:
            LOGGER.warning("Error extracting %s from bulk batch: %s", symbol, exc)
            return pd.DataFrame()

    def sync_one(
        self, symbol: str, force: bool = False, registry: SyncRegistry | None = None
    ) -> bool:
        """
        Synchronise historical data for a single NSE equity symbol.

        Smart path selection:
            - No existing file → full download
            - Existing file with gaps/low coverage → full download (gap fill)
            - Existing file, current, good coverage → incremental update
        """
        symbol = symbol.strip().upper()
        if getattr(self.fetcher, "access_token", "not_fyers") is None:
            self._trip_circuit_breaker(symbol)
        existing = self._load(symbol)

        # Check if full refresh was done recently (within last 15 days) to avoid rate limit loops
        recently_full_refreshed = False
        if registry:
            rec = registry.get(symbol)
            if rec and rec.last_full_refresh_at:
                days_since = (datetime.now() - rec.last_full_refresh_at).days
                if days_since < 15:
                    recently_full_refreshed = True

        if existing.empty:
            # Case 1: Never downloaded → full history
            df = self._fetch_full(symbol)
            if registry and not df.empty:
                registry.mark_full_refreshed(symbol)
        elif (
            self._needs_full_refresh(existing)
            and not recently_full_refreshed
            and not force
        ):
            # Case 2: Partial/gappy data → full refresh to fill gaps
            LOGGER.info(
                "%s: Existing data has gaps (%d rows, %s → %s). Running full refresh.",
                symbol,
                len(existing),
                existing.index.min().date(),
                existing.index.max().date(),
            )
            df = self._fetch_full(symbol)
            if registry:
                registry.mark_full_refreshed(symbol)
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
            # Case 3: Good data or recently full refreshed
            # (fallback to incremental to avoid rate limit) → incremental
            if recently_full_refreshed and self._needs_full_refresh(existing):
                LOGGER.info(
                    "%s has low coverage but was recently full-refreshed. "
                    "Performing incremental update instead of full refresh.",
                    symbol,
                )
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
        try:
            from src.storage.dq_gate import DataQualityGate

            gate = DataQualityGate()
            gate.check_batch(
                [symbol],
                hist_dir=self.data_dir,
                stage="historical_sync.sync_one",
                halt_on_breach=False,
            )
        except Exception as exc:
            LOGGER.warning("DQ gate check failed for %s: %s", symbol, exc)
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

        # Load failed symbols from quarantine and filter them out to prevent infinite retries
        failed_symbols = self._load_failed_symbols()
        if failed_symbols:
            pre_len = len(queue)
            queue = [s for s in queue if s not in failed_symbols]
            skipped_failed_count = pre_len - len(queue)
            if skipped_failed_count > 0:
                LOGGER.info(
                    "Skipped %d symbols because they are in the failed-symbols registry",
                    skipped_failed_count,
                )

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
        batch_results = self.sync_batch(queue, chunk_size=save_every, registry=registry)
        results.update(batch_results)

        if registry:
            registry.save()

        ok_count = sum(v for v in results.values())
        LOGGER.info(
            "Sync complete: %d/%d symbols succeeded (%d skipped as current).",
            ok_count,
            len(results),
            len(skipped),
        )

        touched_symbols = [s for s, ok_val in results.items() if ok_val and s not in skipped]
        if touched_symbols:
            from src.storage.dq_gate import DataQualityGate

            gate = DataQualityGate()
            gate.check_batch(
                touched_symbols,
                hist_dir=self.data_dir,
                stage="historical_sync.sync",
                halt_on_breach=True,
            )

        return results

    def sync_batch(
        self,
        symbols: list[str],
        chunk_size: int = 50,
        registry: SyncRegistry | None = None,
        pbar: Any = None,
    ) -> dict[str, bool]:
        """
        Synchronise historical data for multiple symbols, leveraging YFinance bulk download.

        For YFinance, groups up to 50 symbols per single HTTP request.
        For non-bulk fetchers (e.g. Fyers), falls back to sequential sync_one.
        """
        results: dict[str, bool] = {}
        total = len(symbols)
        if total == 0:
            return results

        if getattr(self.fetcher, "access_token", "not_fyers") is None:
            self._trip_circuit_breaker(symbols[0])

        is_bulk = hasattr(self.fetcher, "fetch_batch") and (
            isinstance(self.fetcher, YFinanceFetcher)
            or "yfinance" in self.fetcher.__class__.__name__.lower()
        )

        if not is_bulk:
            for s in symbols:
                try:
                    res = self.sync_one(s, registry=registry)
                except FyersAuthError:
                    self._trip_circuit_breaker(s)
                    res = self.sync_one(s, registry=registry)
                results[s] = res
                if res:
                    self._remove_failed_symbol(s)
                else:
                    self._record_failed_symbol(s, reason="Fetcher sync failed or empty")
                if pbar is not None:
                    pbar.update(1)
                if self.rate_delay > 0:
                    time.sleep(self.rate_delay)
            return results

        for i in range(0, total, chunk_size):
            chunk = symbols[i : i + chunk_size]
            needs_inc: list[str] = []
            needs_full: list[str] = []
            existing_map: dict[str, pd.DataFrame] = {}

            for s in chunk:
                sym = s.strip().upper()
                ex = self._load(sym)
                existing_map[sym] = ex
                if ex.empty or self._needs_full_refresh(ex):
                    needs_full.append(sym)
                else:
                    needs_inc.append(sym)

            if needs_inc:
                min_last = min(existing_map[s].index.max() for s in needs_inc)
                from_dt = min_last.to_pydatetime() - timedelta(days=5)
                to_dt = datetime.now().replace(hour=23, minute=59, second=59)

                try:
                    df_batch_inc = self.fetcher.fetch_batch(
                        needs_inc,
                        timeframe=self.timeframe,
                        from_date=int(from_dt.timestamp()),
                        to_date=int(to_dt.timestamp()),
                        chunk_size=len(needs_inc),
                    )
                except Exception as exc:
                    LOGGER.warning("Bulk incremental fetch failed: %s; falling back", exc)
                    df_batch_inc = pd.DataFrame()

                for sym in needs_inc:
                    sym_new = self._extract_symbol_from_batch(df_batch_inc, sym)
                    if sym_new.empty:
                        res = self.sync_one(sym, registry=registry)
                    else:
                        merged = self._merge_and_adjust(sym, existing_map[sym], sym_new)
                        self._save(sym, merged)
                        if registry and not merged.empty:
                            registry.mark_done(
                                sym,
                                first_bar=merged.index.min().date(),
                                last_bar=merged.index.max().date(),
                                row_count=len(merged),
                            )
                        self._remove_failed_symbol(sym)
                        res = True
                    results[sym] = res
                    if pbar is not None:
                        pbar.update(1)

            if needs_full:
                from_dt = pd.to_datetime(self.start_date)
                to_dt = datetime.now().replace(hour=23, minute=59, second=59)

                try:
                    df_batch_full = self.fetcher.fetch_batch(
                        needs_full,
                        timeframe=self.timeframe,
                        from_date=int(from_dt.timestamp()),
                        to_date=int(to_dt.timestamp()),
                        chunk_size=len(needs_full),
                    )
                except Exception as exc:
                    LOGGER.warning("Bulk full fetch failed: %s; falling back", exc)
                    df_batch_full = pd.DataFrame()

                for sym in needs_full:
                    sym_df = self._extract_symbol_from_batch(df_batch_full, sym)
                    if sym_df.empty:
                        res = self.sync_one(sym, registry=registry)
                    else:
                        self._save(sym, sym_df)
                        if registry and not sym_df.empty:
                            registry.mark_done(
                                sym,
                                first_bar=sym_df.index.min().date(),
                                last_bar=sym_df.index.max().date(),
                                row_count=len(sym_df),
                            )
                        self._remove_failed_symbol(sym)
                        res = True
                    results[sym] = res
                    if pbar is not None:
                        pbar.update(1)

            if registry:
                registry.save()

            if self.rate_delay > 0:
                time.sleep(self.rate_delay)

        return results

    def _get_failed_db(self) -> sqlite3.Connection:
        db_path = os.path.join(self.data_dir, "failed_symbols.db")
        os.makedirs(self.data_dir, exist_ok=True)
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS failed (
                symbol     TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                reason     TEXT
            )
            """
        )
        csv_path = os.path.join(self.data_dir, "failed_symbols.csv")
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                if "SYMBOL" in df.columns:
                    now_utc = datetime.now(UTC).isoformat()
                    rows = []
                    for _, r in df.iterrows():
                        sym = str(r.get("SYMBOL", "")).strip().upper()
                        if not sym or sym == "NAN":
                            continue
                        last = r.get("LAST_ATTEMPT")
                        seen = str(last) if pd.notna(last) else now_utc
                        rsn = r.get("ERROR_REASON")
                        reason = str(rsn) if pd.notna(rsn) else None
                        rows.append((sym, seen, reason))
                    if rows:
                        conn.executemany(
                            "INSERT OR REPLACE INTO failed (symbol, first_seen, reason) "
                            "VALUES (?, ?, ?)",
                            rows,
                        )
                        conn.commit()
                os.rename(csv_path, f"{csv_path}.migrated")
            except Exception as exc:
                LOGGER.warning("Failed migrating failed_symbols.csv: %s", exc)
        return conn

    def _load_failed_symbols(self) -> set[str]:
        db_path = os.path.join(self.data_dir, "failed_symbols.db")
        csv_path = os.path.join(self.data_dir, "failed_symbols.csv")
        if not os.path.exists(db_path) and not os.path.exists(csv_path):
            return set()
        try:
            conn = self._get_failed_db()
            try:
                cur = conn.execute("SELECT symbol FROM failed")
                return {row[0].strip().upper() for row in cur.fetchall()}
            finally:
                conn.close()
        except Exception as exc:
            LOGGER.warning("Failed to load failed symbols: %s", exc)
            return set()

    def _record_failed_symbol(self, symbol: str, reason: str = "Sync failed") -> None:
        symbol = symbol.strip().upper()
        now_utc = datetime.now(UTC).isoformat()
        try:
            conn = self._get_failed_db()
            try:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO failed (symbol, first_seen, reason) "
                        "VALUES (?, ?, ?)",
                        (symbol, now_utc, reason),
                    )
                LOGGER.info("Recorded %s in failed symbols quarantine", symbol)
            finally:
                conn.close()
        except Exception as exc:
            LOGGER.warning("Failed to record failed symbol %s: %s", symbol, exc)

    def _remove_failed_symbol(self, symbol: str) -> None:
        db_path = os.path.join(self.data_dir, "failed_symbols.db")
        if not os.path.exists(db_path):
            return
        symbol = symbol.strip().upper()
        try:
            conn = self._get_failed_db()
            try:
                with conn:
                    conn.execute("DELETE FROM failed WHERE symbol = ?", (symbol,))
                LOGGER.info("Removed %s from failed symbols quarantine", symbol)
            finally:
                conn.close()
        except Exception as exc:
            LOGGER.warning("Failed to remove %s from failed symbols: %s", symbol, exc)

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
                # Check indicator completeness and staleness against current calendar
                has_indicator_nan = False
                days_stale = 0
                if not df.empty:
                    if "RSI_14" in df.columns:
                        has_indicator_nan = bool(pd.isna(df["RSI_14"].iloc[-1]))
                    else:
                        has_indicator_nan = True
                    if last_date:
                        days_stale = (_last_trading_day() - last_date).days

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
                        "days_stale": max(0, days_stale),
                        "has_indicator_nan": has_indicator_nan,
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
                        "days_stale": 9999,
                        "has_indicator_nan": True,
                        "parquet_path": path,
                    }
                )
        return pd.DataFrame(rows).sort_values("symbol")
