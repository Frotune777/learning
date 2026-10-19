"""Canonical price rebuilder from official NSE sec_bhavdata_full archives."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.platform.loaders.warehouse import WarehouseLoader

LOGGER = logging.getLogger(__name__)


def parse_sec_bhavdata_for_price(
    csv_path: Path, trade_date: date | None = None
) -> pd.DataFrame:
    """Parse sec_bhavdata_full CSV for canonical price columns.

    Returns DataFrame with columns:
      symbol, series, trade_date, date_sk, open, high, low, close,
      last, prev_close, volume, turnover, trades, vwap,
      source_sk, batch_id, price_semantics, source_ref
    """
    if not csv_path.is_file():
        return pd.DataFrame()

    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception as exc:
        LOGGER.warning("Could not read %s: %s", csv_path, exc)
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Clean whitespace in column headers
    df.columns = [c.strip().upper() for c in df.columns]

    required_cols = {"SYMBOL", "SERIES", "OPEN_PRICE", "HIGH_PRICE", "LOW_PRICE", "CLOSE_PRICE"}
    if not required_cols.issubset(set(df.columns)):
        LOGGER.warning("Missing required price columns in %s", csv_path)
        return pd.DataFrame()

    # Filter SERIES == 'EQ'
    df["SERIES"] = df["SERIES"].fillna("").astype(str).str.strip().str.upper()
    df = df[df["SERIES"] == "EQ"].copy()
    if df.empty:
        return pd.DataFrame()

    # Clean symbols
    df["SYMBOL"] = df["SYMBOL"].fillna("").astype(str).str.strip().str.upper()
    df = df[df["SYMBOL"] != ""]

    # Extract date
    if "DATE1" in df.columns:
        date_strs = df["DATE1"].fillna("").astype(str).str.strip()
        parsed_dates = pd.to_datetime(date_strs, format="%d-%b-%Y", errors="coerce").dt.date
        df["trade_date"] = parsed_dates
        if trade_date is not None:
            df["trade_date"] = df["trade_date"].fillna(trade_date)
    else:
        if trade_date is None:
            m = re.search(r"(\d{2})(\d{2})(\d{4})", csv_path.name)
            if m:
                dd, mm, yyyy = m.groups()
                trade_date = date(int(yyyy), int(mm), int(dd))
            else:
                trade_date = date.today()
        df["trade_date"] = trade_date

    df["trade_date"] = df["trade_date"].fillna(trade_date if trade_date else date.today())
    df["date_sk"] = pd.to_datetime(df["trade_date"].astype(str)).dt.strftime("%Y%m%d").astype(int)

    # Convert numeric columns
    def _to_num(col_name: str, default: float = 0.0) -> pd.Series:
        if col_name in df.columns:
            cleaned = df[col_name].astype(str).str.replace(",", "").str.strip()
            return pd.to_numeric(cleaned, errors="coerce").fillna(default)
        return pd.Series([default] * len(df), index=df.index, dtype="float64")

    df["open"] = _to_num("OPEN_PRICE")
    df["high"] = _to_num("HIGH_PRICE")
    df["low"] = _to_num("LOW_PRICE")
    df["close"] = _to_num("CLOSE_PRICE")
    df["last"] = _to_num("LAST_PRICE")
    df["prev_close"] = _to_num("PREV_CLOSE")
    df["volume"] = _to_num("TTL_TRD_QNTY").astype("int64")
    # TURNOVER_LACS in lacs -> rupees (* 100,000)
    df["turnover"] = _to_num("TURNOVER_LACS") * 100000.0
    df["trades"] = _to_num("NO_OF_TRADES").astype("int64")
    df["vwap"] = _to_num("AVG_PRICE")

    # Sanity checks: skip close <= 0 or high < low
    valid_mask = (df["close"] > 0) & (df["high"] >= df["low"])
    df = df[valid_mask].copy()

    df["series"] = "EQ"
    df["source_sk"] = 1  # Official NSE Bhavcopy
    df["batch_id"] = "sec_bhavdata_rebuild"
    df["price_semantics"] = "unadjusted"
    df["source_ref"] = "sec_bhavdata_" + df["date_sk"].astype(str)

    return df[[
        "SYMBOL", "date_sk", "trade_date", "series",
        "open", "high", "low", "close", "last", "prev_close",
        "volume", "turnover", "trades", "vwap",
        "source_sk", "batch_id", "price_semantics", "source_ref"
    ]].rename(columns={"SYMBOL": "symbol"})


def rebuild_price_from_sec_bhavdata(
    start_date: date = date(2020, 1, 1),
    end_date: date = date(2026, 10, 16),
    cache_dir: str = "data/raw/delivery",
    warehouse_loader: WarehouseLoader | None = None,
) -> dict[str, int]:
    """Rebuild fact_price_daily for 2020+ from official NSE sec_bhavdata archives."""
    if warehouse_loader is None:
        warehouse_loader = WarehouseLoader()

    cache_path = Path(cache_dir)
    if not cache_path.is_dir():
        LOGGER.error("Cache directory does not exist: %s", cache_dir)
        return {"files_parsed": 0, "rows_inserted": 0, "rows_deleted": 0, "dates_processed": 0}

    warehouse_loader.acquire_lock()
    conn = warehouse_loader._get_conn()

    try:
        start_sk = int(start_date.strftime("%Y%m%d"))
        end_sk = int(end_date.strftime("%Y%m%d"))

        # Candidate dates in range
        candidate_dates: list[date] = []
        curr = start_date
        while curr <= end_date:
            candidate_dates.append(curr)
            curr += timedelta(days=1)

        conn.begin()
        # Wipe existing rows in date range for clean rebuild
        del_res = conn.execute(
            f"DELETE FROM fact_price_daily WHERE date_sk >= {start_sk} AND date_sk <= {end_sk}"
        )
        rows_deleted = del_res.fetchone()[0] if del_res else 0
        conn.commit()
        LOGGER.info("Deleted %d existing fact_price_daily rows in range %s to %s", rows_deleted, start_date, end_date)

        files_parsed = 0
        rows_inserted = 0
        dates_processed: set[int] = set()
        batch_dfs: list[pd.DataFrame] = []

        upsert_sql = """
        INSERT INTO fact_price_daily (
            symbol_sk, date_sk, symbol, trade_date, series,
            open, high, low, close, last, prev_close,
            volume, turnover, trades, vwap,
            source_sk, batch_id, price_semantics, source_ref
        )
        SELECT
            COALESCE(ds_pit.symbol_sk, ds_curr.symbol_sk) AS symbol_sk,
            b.date_sk, b.symbol, b.trade_date, b.series,
            b.open, b.high, b.low, b.close, b.last, b.prev_close,
            b.volume, b.turnover, b.trades, b.vwap,
            b.source_sk, b.batch_id, b.price_semantics, b.source_ref
        FROM df_batch b
        LEFT JOIN dim_symbol ds_pit
          ON ds_pit.symbol = b.symbol
         AND b.trade_date >= ds_pit.valid_from
         AND b.trade_date <= ds_pit.valid_to
        LEFT JOIN dim_symbol ds_curr
          ON ds_curr.symbol = b.symbol AND ds_curr.is_current = TRUE
        WHERE COALESCE(ds_pit.symbol_sk, ds_curr.symbol_sk) IS NOT NULL
        ON CONFLICT (symbol_sk, date_sk) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            last = excluded.last,
            prev_close = excluded.prev_close,
            volume = excluded.volume,
            turnover = excluded.turnover,
            trades = excluded.trades,
            vwap = excluded.vwap,
            price_semantics = excluded.price_semantics,
            source_ref = excluded.source_ref
        """

        for idx, d in enumerate(candidate_dates, 1):
            stamp = d.strftime("%d%m%Y")
            csv_path = cache_path / f"sec_bhavdata_full_{stamp}.csv"
            if not csv_path.is_file():
                continue

            df = parse_sec_bhavdata_for_price(csv_path, trade_date=d)
            if df.empty:
                continue

            files_parsed += 1
            batch_dfs.append(df)
            dates_processed.update(df["date_sk"].unique())

            # Flush batch every 50 files or at the end
            if len(batch_dfs) >= 50 or idx == len(candidate_dates):
                if batch_dfs:
                    combined = pd.concat(batch_dfs, ignore_index=True)
                    combined = combined.drop_duplicates(subset=["symbol", "date_sk"], keep="last")
                    conn.begin()
                    conn.register("df_batch", combined)
                    ins_res = conn.execute(upsert_sql)
                    ins_cnt = ins_res.fetchone()[0] if ins_res else len(combined)
                    conn.unregister("df_batch")
                    conn.commit()
                    rows_inserted += ins_cnt
                    batch_dfs.clear()
                    LOGGER.info("Inserted batch (%d total rows, %d dates processed so far)", rows_inserted, len(dates_processed))

        LOGGER.info("Price rebuild complete: %d rows inserted across %d dates", rows_inserted, len(dates_processed))
        return {
            "files_parsed": files_parsed,
            "rows_inserted": rows_inserted,
            "rows_deleted": rows_deleted,
            "dates_processed": len(dates_processed),
        }
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        LOGGER.exception("Price rebuild failed: %s", exc)
        raise
    finally:
        warehouse_loader.release_lock()
