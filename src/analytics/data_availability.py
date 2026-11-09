"""
File: src/analytics/data_availability.py
Purpose: Offline data coverage checking and historical parquet generation.
"""

from __future__ import annotations

import glob
import io
import os
import re
import tempfile
import zipfile
from datetime import date, datetime

import pandas as pd

DATE_REGEX = re.compile(r"(\d{8})")


def _extract_date_from_filename(filename: str) -> date | None:
    match = DATE_REGEX.search(os.path.basename(filename))
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            return None
    return None


def _get_expected_trading_days(
    start_d: date,
    end_d: date,
    hist_dir: str = "data/historical/1d",
    raw_dir: str = "data/raw",
) -> set[date]:
    """Determine expected trading days in [start_d, end_d] from available local data."""
    raw_dates: set[date] = set()
    for zf in glob.glob(os.path.join(raw_dir, "BhavCopy*.zip")):
        d = _extract_date_from_filename(zf)
        if d and start_d <= d <= end_d:
            raw_dates.add(d)

    ref_dates: set[date] = set()
    ref_parquet = os.path.join(hist_dir, "RELIANCE.parquet")
    if os.path.exists(ref_parquet):
        try:
            df_ref = pd.read_parquet(ref_parquet)
            ref_dates = {
                d for d in pd.to_datetime(df_ref.index).date if start_d <= d <= end_d
            }
        except Exception:
            pass

    expected = raw_dates | ref_dates
    if not expected:
        expected = set(pd.bdate_range(start_d, end_d).date)
    return expected


def check_coverage(
    symbols: list[str],
    start: str | date | None = None,
    end: str | date | None = None,
    hist_dir: str = "data/historical/1d",
    raw_dir: str = "data/raw",
) -> dict[str, list[str]]:
    """
    Check historical data coverage across symbols against local parquets and raw archives.

    Returns:
        dict with keys: 'available', 'loadable', 'partial', 'missing'
        - available: parquet exists and covers >=85% of trading days
        - loadable:  parquet missing/stale BUT raw ZIPs cover it
        - partial:   parquet exists but < 85% coverage
        - missing:   no data anywhere
    """
    start_d = (
        datetime.strptime(start, "%Y-%m-%d").date()
        if isinstance(start, str)
        else (start or date(2026, 1, 1))
    )
    end_d = (
        datetime.strptime(end, "%Y-%m-%d").date()
        if isinstance(end, str)
        else (end or date.today())
    )

    expected_days = _get_expected_trading_days(start_d, end_d, hist_dir, raw_dir)
    total_expected = len(expected_days) or 1

    # Check which symbols exist across raw zips
    raw_zips = sorted(glob.glob(os.path.join(raw_dir, "BhavCopy*.zip")))

    # Pre-index symbols in raw zips for requested symbols
    requested_upper = {s.strip().upper() for s in symbols}
    raw_symbol_days: dict[str, set[date]] = {s: set() for s in requested_upper}

    for zpath in raw_zips:
        f_date = _extract_date_from_filename(zpath)
        if not f_date or not (start_d <= f_date <= end_d):
            continue
        try:
            with zipfile.ZipFile(zpath) as z:
                for name in z.namelist():
                    if not name.endswith(".csv"):
                        continue
                    content = z.read(name)
                    for sym in requested_upper:
                        if sym.encode("utf-8") in content:
                            raw_symbol_days[sym].add(f_date)
        except Exception:
            continue

    result: dict[str, list[str]] = {
        "available": [],
        "loadable": [],
        "partial": [],
        "missing": [],
    }

    for sym in symbols:
        sym_upper = sym.strip().upper()
        parquet_path = os.path.join(hist_dir, f"{sym_upper}.parquet")
        has_parquet = os.path.exists(parquet_path)

        parquet_days: set[date] = set()
        if has_parquet:
            try:
                df = pd.read_parquet(parquet_path)
                parquet_days = {
                    d for d in pd.to_datetime(df.index).date if start_d <= d <= end_d
                }
            except Exception:
                parquet_days = set()

        coverage = len(parquet_days) / total_expected
        raw_available_days = raw_symbol_days.get(sym_upper, set())
        combined_days = parquet_days | raw_available_days
        combined_coverage = len(combined_days) / total_expected

        if coverage >= 0.85:
            result["available"].append(sym_upper)
        elif combined_coverage >= 0.85:
            result["loadable"].append(sym_upper)
        elif has_parquet and len(parquet_days) > 0:
            result["partial"].append(sym_upper)
        elif len(raw_available_days) > 0:
            result["loadable"].append(sym_upper)
        else:
            result["missing"].append(sym_upper)

    return result


def build_from_raw(
    symbol: str,
    start: str | date | None = None,
    end: str | date | None = None,
    raw_dir: str = "data/raw",
    hist_dir: str = "data/historical/1d",
) -> bool:
    """
    Extract OHLCV rows for symbol from local BhavCopy ZIPs and write/update Parquet.
    Returns True if at least 1 row written.
    ZERO network calls.
    """
    sym = symbol.strip().upper()
    start_d = (
        datetime.strptime(start, "%Y-%m-%d").date()
        if isinstance(start, str)
        else (start or date(2000, 1, 1))
    )
    end_d = (
        datetime.strptime(end, "%Y-%m-%d").date()
        if isinstance(end, str)
        else (end or date.today())
    )

    raw_files = sorted(glob.glob(os.path.join(raw_dir, "BhavCopy*.zip")))
    extracted_rows: list[dict] = []

    for zf in raw_files:
        f_date = _extract_date_from_filename(zf)
        if f_date and (f_date < start_d or f_date > end_d):
            continue

        try:
            with zipfile.ZipFile(zf) as z:
                csv_files = [n for n in z.namelist() if n.endswith(".csv")]
                for cname in csv_files:
                    with z.open(cname) as f:
                        raw_bytes = f.read()
                        if sym.encode("utf-8") not in raw_bytes:
                            continue

                        df_raw = pd.read_csv(io.BytesIO(raw_bytes))
                        df_raw.columns = [c.strip() for c in df_raw.columns]

                        sym_col = next(
                            (c for c in ["TckrSymb", "SYMBOL"] if c in df_raw.columns), None
                        )
                        if not sym_col:
                            continue

                        match_rows = df_raw[df_raw[sym_col].astype(str).str.upper() == sym]
                        if match_rows.empty:
                            continue

                        # Prioritize EQ series if series column exists
                        series_col = next(
                            (c for c in ["SctySrs", "SERIES"] if c in match_rows.columns), None
                        )
                        if series_col:
                            is_eq = match_rows[series_col].astype(str).str.upper() == "EQ"
                            eq_rows = match_rows[is_eq]
                            if not eq_rows.empty:
                                match_rows = eq_rows

                        row = match_rows.iloc[0]

                        # Date resolution
                        date_val = f_date
                        date_col = next(
                            (c for c in ["TradDt", "BizDt", "TIMESTAMP"] if c in row.index), None
                        )
                        if date_col and pd.notna(row[date_col]):
                            try:
                                date_val = pd.to_datetime(row[date_col]).date()
                            except Exception:
                                pass

                        open_col = next(
                            (c for c in ["OpnPric", "OPEN"] if c in row.index), None
                        )
                        high_col = next(
                            (c for c in ["HghPric", "HIGH"] if c in row.index), None
                        )
                        low_col = next(
                            (c for c in ["LwPric", "LOW"] if c in row.index), None
                        )
                        close_col = next(
                            (c for c in ["ClsPric", "CLOSE"] if c in row.index), None
                        )
                        vol_col = next(
                            (
                                c
                                for c in [
                                    "TtlTradgVol",
                                    "TtlTrdQnty",
                                    "TTL_TRD_QNTY",
                                    "TOTTRDQTY",
                                    "VOLUME",
                                ]
                                if c in row.index
                            ),
                            None,
                        )

                        o_val = (
                            float(row[open_col])
                            if open_col and pd.notna(row[open_col])
                            else 0.0
                        )
                        h_val = (
                            float(row[high_col])
                            if high_col and pd.notna(row[high_col])
                            else 0.0
                        )
                        l_val = float(row[low_col]) if low_col and pd.notna(row[low_col]) else 0.0
                        c_val = (
                            float(row[close_col])
                            if close_col and pd.notna(row[close_col])
                            else 0.0
                        )
                        v_val = float(row[vol_col]) if vol_col and pd.notna(row[vol_col]) else 0.0

                        extracted_rows.append(
                            {
                                "Date": pd.to_datetime(date_val),
                                "Open": o_val,
                                "High": h_val,
                                "Low": l_val,
                                "Close": c_val,
                                "Volume": v_val,
                            }
                        )
        except Exception:
            continue

    parquet_path = os.path.join(hist_dir, f"{sym}.parquet")
    existing_df = pd.DataFrame()
    if os.path.exists(parquet_path):
        try:
            existing_df = pd.read_parquet(parquet_path)
            if "Date" not in existing_df.columns:
                existing_df.index.name = "Date"
        except Exception:
            existing_df = pd.DataFrame()

    if not extracted_rows and existing_df.empty:
        return False

    if extracted_rows:
        new_df = pd.DataFrame(extracted_rows).drop_duplicates(subset=["Date"]).set_index("Date")
        if not existing_df.empty:
            combined = pd.concat([existing_df, new_df])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        else:
            combined = new_df.sort_index()
    else:
        combined = existing_df.sort_index()

    if combined.empty:
        return False

    # Standardize column names
    standard_cols = ["Open", "High", "Low", "Close", "Volume"]
    for col in standard_cols:
        if col not in combined.columns:
            combined[col] = 0.0

    # Add TA indicators if enough rows
    if len(combined) >= 30:
        try:
            from src.nse_bhavcopy.ta_indicators import add_ta_indicators
            combined = add_ta_indicators(combined)
        except Exception:
            pass

    # Atomic write to parquet
    os.makedirs(hist_dir, exist_ok=True)
    temp_dir = os.path.dirname(parquet_path)
    fd, temp_path = tempfile.mkstemp(prefix=f".{sym}_", suffix=".tmp", dir=temp_dir)
    os.close(fd)
    try:
        combined.to_parquet(temp_path, engine="pyarrow", index=True)
        os.replace(temp_path, parquet_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    return True
