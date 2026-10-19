"""
NSE Delivery Backfill Loader.

Downloads, parses, and loads historical security-wise delivery statistics
from NSE official sec_bhavdata_full archives into fact_delivery_daily.
Scoped to 2020+ (sec_bhavdata_full availability).
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
import logging
from pathlib import Path
import time
from typing import Any

import pandas as pd
import requests

LOGGER = logging.getLogger(__name__)

NSE_ARCHIVE_SEC_BHAV_URL = (
    "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{stamp}.csv"
)

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _iter_candidate_dates(start_date: date, end_date: date) -> list[date]:
    """Return all weekday dates (Mon-Fri) in [start_date, end_date]."""
    days: list[date] = []
    curr = start_date
    while curr <= end_date:
        if curr.weekday() < 5:  # Mon-Fri
            days.append(curr)
        curr += timedelta(days=1)
    return days


def download_sec_bhavdata_range(
    start_date: date,
    end_date: date,
    cache_dir: str | Path = "data/raw/delivery",
    rate_delay: float = 1.0,
) -> int:
    """
    Download sec_bhavdata_full_{DDMMYYYY}.csv for each trading day in [start_date, end_date].

    Skips weekends and NSE holidays (404 response skipped gracefully).
    Caches to cache_dir; skips if already present.
    Rate limit 1 req/sec. Returns count of successfully cached files.
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    candidate_dates = _iter_candidate_dates(start_date, end_date)
    total_days = len(candidate_dates)
    cached_count = 0
    session = requests.Session()
    session.headers.update(HTTP_HEADERS)

    for idx, d in enumerate(candidate_dates, 1):
        stamp = d.strftime("%d%m%Y")
        out_file = cache_path / f"sec_bhavdata_full_{stamp}.csv"

        if out_file.is_file() and out_file.stat().st_size > 0:
            cached_count += 1
            if idx % 100 == 0 or idx == total_days:
                LOGGER.info("Downloading: %d/%d days (cached: %d)", idx, total_days, cached_count)
            continue

        url = NSE_ARCHIVE_SEC_BHAV_URL.format(stamp=stamp)
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                out_file.write_bytes(resp.content)
                cached_count += 1
            elif resp.status_code == 404:
                # Holiday or weekend scheduled trading skipped
                LOGGER.debug("Trading holiday or unavailable on %s (404)", d.isoformat())
            else:
                LOGGER.warning("HTTP %d fetching %s", resp.status_code, url)
        except requests.RequestException as exc:
            LOGGER.warning("Network error fetching %s: %s", url, exc)

        if rate_delay > 0:
            time.sleep(rate_delay)

        if idx % 100 == 0 or idx == total_days:
            LOGGER.info("Downloading: %d/%d days (cached: %d)", idx, total_days, cached_count)

    return cached_count


def parse_sec_bhavdata(csv_path: Path, trade_date: date) -> pd.DataFrame:
    """
    Parse sec_bhavdata_full CSV.

    Columns of interest:
      SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE,
      LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY,
      TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
    Filter SERIES == 'EQ'. Return canonical DataFrame with columns:
      symbol, trade_date, traded_qty, deliverable_qty, delivery_pct
    Handle whitespace in column values (NSE CSVs have ' ' padding).
    """
    if not csv_path.is_file() or csv_path.stat().st_size == 0:
        return pd.DataFrame(columns=["symbol", "trade_date", "traded_qty", "deliverable_qty", "delivery_pct"])

    rows: list[dict[str, Any]] = []
    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            # Strip whitespace from keys and values
            row = {
                k.strip(): (v.strip() if isinstance(v, str) else v)
                for k, v in raw_row.items()
                if k is not None
            }
            series = str(row.get("SERIES", "")).upper()
            if series != "EQ":
                continue

            symbol = str(row.get("SYMBOL", "")).upper()
            if not symbol:
                continue

            d_str = row.get("DATE1", "")
            try:
                row_date = datetime.strptime(d_str, "%d-%b-%Y").date() if d_str else trade_date
            except Exception:
                row_date = trade_date

            def _parse_int(val: Any) -> int | None:
                if val is None or val == "" or val == "-":
                    return None
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    return None

            def _parse_float(val: Any) -> float | None:
                if val is None or val == "" or val == "-":
                    return None
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

            traded_qty = _parse_int(row.get("TTL_TRD_QNTY")) or 0
            deliverable_qty = _parse_int(row.get("DELIV_QTY"))
            delivery_pct = _parse_float(row.get("DELIV_PER"))

            rows.append({
                "symbol": symbol,
                "trade_date": row_date,
                "traded_qty": traded_qty,
                "deliverable_qty": deliverable_qty,
                "delivery_pct": delivery_pct,
            })

    return pd.DataFrame(rows)


def backfill_delivery_history(
    start_date: date,
    end_date: date,
    warehouse_loader: Any,
    cache_dir: str | Path = "data/raw/delivery",
    rate_delay: float = 1.0,
) -> dict[str, int]:
    """
    Orchestrates download -> parse -> upsert into fact_delivery_daily.

    Batch commits by date file for resilience and progress reporting.
    Looks up symbol_sk from dim_symbol. Skips unknown symbols.
    Returns {downloaded, parsed, inserted, skipped_unknown_symbol}.
    """
    cache_path = Path(cache_dir)
    downloaded = download_sec_bhavdata_range(
        start_date=start_date,
        end_date=end_date,
        cache_dir=cache_path,
        rate_delay=rate_delay,
    )

    candidate_dates = _iter_candidate_dates(start_date, end_date)
    warehouse_loader.acquire_lock()
    conn = warehouse_loader._get_conn()
    total_inserted = 0
    skipped_unknown = 0
    parsed_files = 0

    try:
        scd2_rows = conn.execute(
            "SELECT symbol, symbol_sk, valid_from, valid_to, is_current FROM dim_symbol"
        ).fetchall()
        sym_pit_map: dict[str, list[tuple[date, date, int]]] = {}
        sym_curr_map: dict[str, int] = {}
        for s_sym, s_sk, v_from, v_to, is_cur in scd2_rows:
            s_upper = s_sym.upper()
            if s_upper not in sym_pit_map:
                sym_pit_map[s_upper] = []
            sym_pit_map[s_upper].append((v_from, v_to, s_sk))
            if is_cur:
                sym_curr_map[s_upper] = s_sk

        def _resolve_sk(sym_name: str, trade_d: date) -> int | None:
            if sym_name in sym_pit_map:
                for v_from, v_to, s_sk in sym_pit_map[sym_name]:
                    if v_from <= trade_d <= v_to:
                        return s_sk
            return sym_curr_map.get(sym_name)

        conn.begin()

        for idx, d in enumerate(candidate_dates, 1):
            stamp = d.strftime("%d%m%Y")
            csv_path = cache_path / f"sec_bhavdata_full_{stamp}.csv"
            if not csv_path.is_file():
                continue

            parsed_files += 1
            df = parse_sec_bhavdata(csv_path, trade_date=d)
            if df.empty:
                continue

            insert_rows: list[tuple[Any, ...]] = []
            for _, r in df.iterrows():
                sym = r["symbol"]
                t_date = r["trade_date"]
                sym_sk = _resolve_sk(sym, t_date)
                if sym_sk is None:
                    skipped_unknown += 1
                    continue
                d_sk = int(t_date.strftime("%Y%m%d"))
                trd_qty = int(r["traded_qty"])
                del_qty = int(r["deliverable_qty"]) if pd.notna(r["deliverable_qty"]) and r["deliverable_qty"] is not None else None
                del_pct = float(r["delivery_pct"]) if pd.notna(r["delivery_pct"]) and r["delivery_pct"] is not None else None

                insert_rows.append((
                    sym_sk,
                    d_sk,
                    sym,
                    t_date,
                    "EQ",
                    trd_qty,
                    del_qty,
                    del_pct,
                    1,
                    "delivery_backfill",
                ))

            if insert_rows:
                conn.executemany(
                    """
                    INSERT INTO fact_delivery_daily (
                        symbol_sk, date_sk, symbol, trade_date, series,
                        traded_qty, deliverable_qty, delivery_pct, source_sk, batch_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (symbol_sk, date_sk) DO UPDATE SET
                        traded_qty = excluded.traded_qty,
                        deliverable_qty = excluded.deliverable_qty,
                        delivery_pct = excluded.delivery_pct
                    """,
                    insert_rows,
                )
                total_inserted += len(insert_rows)

            # Commit periodically every 50 files for memory efficiency
            if parsed_files % 50 == 0:
                conn.commit()
                conn.begin()
                LOGGER.info("Parsed %d files, inserted %d rows...", parsed_files, total_inserted)

        conn.commit()
        return {
            "downloaded": downloaded,
            "parsed": parsed_files,
            "inserted": total_inserted,
            "skipped_unknown_symbol": skipped_unknown,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        warehouse_loader.release_lock()
