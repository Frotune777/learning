"""
File: src/nse_bhavcopy/sync_registry.py
Purpose: Maintain a Parquet-backed sync registry with trading calendar awareness.

Dependencies:
External:
- pandas>=2.2.3: Registry Parquet read/write
- pandas_market_calendars>=4.3.1: NSE trading calendar for accurate "stale" detection
Internal:
- None

Key Components:
Classes:
- SyncRegistry: Hash-map registry with trading-day-aware stale detection.
Functions:
- None

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Add exponential back-off skip for symbols with fail_count > 5 [2h]
"""

import heapq
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

LOGGER: logging.Logger = logging.getLogger(__name__)

# Lazy import — only load when needed to avoid startup overhead
_NSE_CALENDAR = None


def _get_nse_calendar() -> Any:
    """Lazy singleton for NSE trading calendar."""
    global _NSE_CALENDAR
    if _NSE_CALENDAR is None:
        try:
            import pandas_market_calendars as mcal

            _NSE_CALENDAR = mcal.get_calendar("NSE")
            LOGGER.info("Loaded NSE trading calendar.")
        except Exception as exc:
            LOGGER.warning(
                "Failed to load NSE calendar (%s), falling back to weekday logic.", exc
            )
            _NSE_CALENDAR = False  # sentinel: unavailable
    return _NSE_CALENDAR


def _last_trading_day(ref_date: date | None = None) -> date:
    """
    Return the most recent NSE trading day before or on ref_date.

    Uses pandas_market_calendars if available, otherwise weekday fallback.
    """
    d = ref_date or date.today()
    cal = _get_nse_calendar()

    if cal is False:
        # Fallback: skip weekends only
        while d.weekday() >= 5:  # Sat=5, Sun=6
            d -= timedelta(days=1)
        return d

    # Use actual NSE calendar (handles holidays, Diwali, etc.)
    # Get last 10 valid sessions ending at or before d
    try:
        schedule = cal.schedule(start_date=d - timedelta(days=30), end_date=d)
        valid_days = schedule.index.date
        # Filter to days <= d
        valid_days = [day for day in valid_days if day <= d]
        if valid_days:
            last_val = valid_days[-1]
            if isinstance(last_val, date):
                return last_val
        return d
    except Exception as exc:
        LOGGER.warning("Calendar lookup failed: %s, using weekday fallback.", exc)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d


@dataclass
class SyncRecord:
    """
    Immutable value object holding sync metadata for one symbol.

    Attributes:
        symbol (str): NSE equity symbol. | Uppercase non-empty.
        status (str): 'pending', 'ok', 'failed'. | Default 'pending'.
        first_bar_date (date | None): Oldest bar date in Parquet.
        last_bar_date (date | None): Newest bar date in Parquet.
        row_count (int): Number of OHLCV rows stored. | Default 0.
        timeframe (str): Candle resolution. | e.g. '1d'.
        last_synced_at (datetime | None): Timestamp of last successful sync.
        fail_count (int): Consecutive failure count. | Default 0.
        expected_rows (int): Expected row count based on trading days. | Default 0.
        last_full_refresh_at (datetime | None): Timestamp of last full refresh execution.
    """

    symbol: str
    status: str = "pending"
    first_bar_date: date | None = None
    last_bar_date: date | None = None
    row_count: int = 0
    timeframe: str = "1d"
    last_synced_at: datetime | None = None
    fail_count: int = 0
    expected_rows: int = 0
    last_full_refresh_at: datetime | None = None

    def needs_update(self, today: date | None = None) -> bool:
        """
        Return True if symbol needs sync — checks both recency AND completeness.

        Logic:
            Step 1: If status is pending or last_bar_date is None → needs update.
            Step 2: Get effective reference date (last trading day).
            Step 3: Check recency: last_bar_date < last_trading_day.
            Step 4: Check completeness: if we have < 80% of expected rows,
                    there may be gaps in history → needs full refresh.

        Parameters:
            today (date | None): Reference date. | Defaults to last trading day.

        Returns:
            bool: True if update or gap-fill is needed.
        """
        if self.status == "pending" or self.last_bar_date is None:
            return True

        # Cooldown check: if successfully synced in the last 24 hours, skip!
        if self.last_synced_at:
            hours_since = (
                datetime.now() - self.last_synced_at
            ).total_seconds() / 3600.0
            if hours_since < 24.0:
                return False

        ref = today or _last_trading_day()

        # Check 1: Recency — is last bar before the most recent trading day?
        if self.last_bar_date < ref:
            return True

        # Check 2: Completeness — do we have suspiciously few rows?
        # If first_bar_date is known, estimate expected trading days
        if self.first_bar_date and self.row_count > 0:
            trading_days_estimate = self._estimate_trading_days(
                self.first_bar_date, ref
            )
            if trading_days_estimate > 50:  # Only check for meaningful history
                coverage_ratio = self.row_count / trading_days_estimate
                if coverage_ratio < 0.8:  # Less than 80% coverage → gaps likely
                    LOGGER.debug(
                        "%s: Low coverage %.1f%% (%d/%d estimated rows) "
                        "— needs gap fill.",
                        self.symbol,
                        coverage_ratio * 100,
                        self.row_count,
                        trading_days_estimate,
                    )
                    return True

        return False

    @staticmethod
    def _estimate_trading_days(start: date, end: date) -> int:
        """Rough estimate of trading days between two dates (≈ 252/year)."""
        if start >= end:
            return 0
        years = (end - start).days / 365.25
        return int(years * 252)  # ~252 trading days per year

    def priority_key(self) -> tuple[int, int, int]:
        """
        Return a sort key for min-heap ordering (lowest = highest priority).

        Returns:
            tuple: (priority_tier, last_bar_date_ordinal, -row_count) for heapq.

        Complexity:
            Time: O(1)
            Space: O(1)
        """
        bar_ord = self.last_bar_date.toordinal() if self.last_bar_date else 0
        # Symbols with fewer rows get higher priority (gap-fill needed)
        if self.status == "pending":
            return (0, bar_ord, -self.row_count)
        if self.status == "failed":
            return (1, bar_ord, -self.row_count)
        # For 'ok' symbols, those with low coverage come first
        return (2, bar_ord, -self.row_count)


class SyncRegistry:
    """
    Hash-map backed sync registry with min-heap priority queue for stale symbols.

    DSA Design:
        - Internal store: dict[str, SyncRecord] — O(1) lookup by symbol.
        - Priority queue: heapq (min-heap) built with heapify — O(N) build,
          O(log N) pop.
        - Persistence: Parquet columnar store — O(N) full scan for batch filters.
    """

    def __init__(
        self,
        registry_dir: str = "data",
        timeframe: str = "1d",
    ) -> None:
        self.registry_dir: str = registry_dir
        self.timeframe: str = timeframe
        os.makedirs(registry_dir, exist_ok=True)
        self._store: dict[str, SyncRecord] = {}

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, symbol: str) -> bool:
        return symbol.strip().upper() in self._store

    def get(self, symbol: str) -> SyncRecord | None:
        return self._store.get(symbol.strip().upper())

    def _path(self) -> str:
        return os.path.join(
            self.registry_dir, f"sync_registry_{self.timeframe}.parquet"
        )

    def load(self) -> int:
        path = self._path()
        if not os.path.exists(path):
            LOGGER.info("No registry found at %s — starting fresh.", path)
            return 0
        try:
            df = pd.read_parquet(path)
            self._store = {}
            for _, row in df.iterrows():
                rec = SyncRecord(
                    symbol=str(row["symbol"]),
                    status=str(row.get("status", "pending")),
                    first_bar_date=self._to_date(row.get("first_bar_date")),
                    last_bar_date=self._to_date(row.get("last_bar_date")),
                    row_count=int(row.get("row_count", 0)),
                    timeframe=str(row.get("timeframe", self.timeframe)),
                    last_synced_at=self._to_datetime(row.get("last_synced_at")),
                    fail_count=int(row.get("fail_count", 0)),
                    expected_rows=int(row.get("expected_rows", 0)),
                    last_full_refresh_at=self._to_datetime(
                        row.get("last_full_refresh_at")
                    ),
                )
                self._store[rec.symbol] = rec
            LOGGER.info("Registry loaded: %d symbols.", len(self._store))
            return len(self._store)
        except Exception as exc:
            LOGGER.warning("Registry load failed: %s — resetting.", exc)
            self._store = {}
            return 0

    def save(self) -> str:
        path = self._path()
        tmp_path = path + ".tmp"
        rows = [
            {
                "symbol": r.symbol,
                "status": r.status,
                "first_bar_date": r.first_bar_date,
                "last_bar_date": r.last_bar_date,
                "row_count": r.row_count,
                "timeframe": r.timeframe,
                "last_synced_at": r.last_synced_at,
                "fail_count": r.fail_count,
                "expected_rows": r.expected_rows,
                "last_full_refresh_at": r.last_full_refresh_at,
            }
            for r in self._store.values()
        ]
        try:
            df = pd.DataFrame(rows)
            df.to_parquet(tmp_path, index=False)
            os.replace(tmp_path, path)
            LOGGER.info("Registry saved: %d symbols → %s", len(rows), path)
            return path
        except Exception as exc:
            LOGGER.error("Registry save failed: %s", exc)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return path

    def register(self, symbols: list[str]) -> int:
        added = 0
        for sym in set(symbols):
            sym = sym.strip().upper()
            if sym not in self._store:
                self._store[sym] = SyncRecord(symbol=sym, timeframe=self.timeframe)
                added += 1
        LOGGER.info("Registry: %d new symbols registered.", added)
        return added

    def mark_done(
        self,
        symbol: str,
        first_bar: date,
        last_bar: date,
        row_count: int,
    ) -> None:
        sym = symbol.strip().upper()
        rec = self._store.get(sym) or SyncRecord(symbol=sym, timeframe=self.timeframe)
        rec.status = "ok"
        rec.first_bar_date = first_bar
        rec.last_bar_date = last_bar
        rec.row_count = row_count
        rec.expected_rows = rec._estimate_trading_days(first_bar, last_bar)
        rec.last_synced_at = datetime.now()
        rec.fail_count = 0
        self._store[sym] = rec

    def mark_full_refreshed(self, symbol: str) -> None:
        sym = symbol.strip().upper()
        rec = self._store.get(sym) or SyncRecord(symbol=sym, timeframe=self.timeframe)
        rec.last_full_refresh_at = datetime.now()
        self._store[sym] = rec

    def mark_failed(self, symbol: str) -> None:
        sym = symbol.strip().upper()
        rec = self._store.get(sym) or SyncRecord(symbol=sym, timeframe=self.timeframe)
        rec.fail_count += 1
        rec.status = "failed"
        self._store[sym] = rec

    def pending_symbols(
        self,
        today: date | None = None,
        max_fail_skip: int = 5,
    ) -> list[str]:
        """
        Return priority-ordered list of symbols that need syncing.

        Priority order:
            1. Pending symbols (never synced)
            2. Failed symbols (retry)
            3. OK symbols with stale last_bar_date
            4. OK symbols with low row coverage (gap-fill)

        Parameters:
            today (date | None): Reference date. | Default last trading day.
            max_fail_skip (int): Skip symbols with >= this many failures.

        Returns:
            list[str]: Priority-ordered symbol list.
        """
        ref = today or _last_trading_day()

        heap = [
            (rec.priority_key(), sym)
            for sym, rec in self._store.items()
            if rec.fail_count < max_fail_skip and rec.needs_update(ref)
        ]
        heapq.heapify(heap)

        ordered: list[str] = []
        while heap:
            _, sym = heapq.heappop(heap)
            ordered.append(sym)

        LOGGER.info(
            "Pending queue: %d symbols need sync (of %d total).",
            len(ordered),
            len(self._store),
        )
        return ordered

    def summary(self) -> pd.DataFrame:
        if not self._store:
            return pd.DataFrame()
        rows = [
            {
                "symbol": r.symbol,
                "status": r.status,
                "first_bar_date": r.first_bar_date,
                "last_bar_date": r.last_bar_date,
                "row_count": r.row_count,
                "expected_rows": r.expected_rows,
                "coverage_pct": round(r.row_count / r.expected_rows * 100, 1)
                if r.expected_rows > 0
                else 0,
                "fail_count": r.fail_count,
                "last_synced_at": r.last_synced_at,
                "needs_update": r.needs_update(),
            }
            for r in self._store.values()
        ]
        df = pd.DataFrame(rows)
        return df.sort_values(
            ["status", "last_bar_date"], na_position="first"
        ).reset_index(drop=True)

    @staticmethod
    def _to_date(val: object) -> date | None:
        if val is None:
            return None
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        try:
            dt = pd.to_datetime(val)
            if hasattr(dt, "date"):
                d_val = dt.date()
                if isinstance(d_val, date):
                    return d_val
            return None
        except Exception:
            return None

    @staticmethod
    def _to_datetime(val: object) -> datetime | None:
        if val is None:
            return None
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        if isinstance(val, datetime):
            return val
        try:
            dt = pd.to_datetime(val)
            if hasattr(dt, "to_pydatetime"):
                dt_val = dt.to_pydatetime()
                if isinstance(dt_val, datetime):
                    return dt_val
            return None
        except Exception:
            return None
