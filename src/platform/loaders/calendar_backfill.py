"""NSE trading calendar backfill using pandas_market_calendars."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pandas_market_calendars as mcal

LOGGER = logging.getLogger(__name__)


def populate_full_nse_calendar(
    start_date: date = date(2000, 1, 1),
    end_date: date = date(2030, 12, 31),
    conn: duckdb.DuckDBPyConnection | None = None,
    db_path: Path | str = "data/warehouse.duckdb",
    holidays_path: Path | str = "config/holidays.json",
) -> int:
    """Populate dim_date with full historical NSE trading days and holidays.

    Uses pandas_market_calendars XNSE (or XBOM fallback) to determine
    all official trading days. Overrides / future dates can be supplemented
    via config/holidays.json.

    Idempotent: updates existing date records and inserts missing ones.
    Returns the count of rows processed.
    """
    try:
        cal = mcal.get_calendar("XNSE")
    except Exception:
        try:
            cal = mcal.get_calendar("NSE")
        except Exception:
            cal = mcal.get_calendar("XBOM")

    schedule = cal.schedule(start_date=start_date.isoformat(), end_date=end_date.isoformat())
    valid_dates: set[date] = set(schedule.index.date)

    override_holidays: set[str] = set()
    h_path = Path(holidays_path)
    if h_path.is_file():
        try:
            h_data = json.loads(h_path.read_text(encoding="utf-8"))
            for v in h_data.values():
                if isinstance(v, list):
                    override_holidays.update(v)
        except Exception as exc:
            LOGGER.warning("Could not read %s for holiday overrides: %s", holidays_path, exc)

    # Known special live trading sessions on NSE (Muhurat trading, disaster recovery live drills, rescheduled holidays)
    special_sessions: set[date] = {
        date(2020, 7, 31),
        date(2020, 11, 14),
        date(2021, 11, 4),
        date(2022, 10, 24),
        date(2023, 11, 12),
        date(2024, 1, 20),
        date(2024, 5, 18),
        date(2024, 11, 1),
        date(2025, 10, 21),
    }
    valid_dates.update(special_sessions)

    date_rows: list[tuple[Any, ...]] = []
    curr = start_date
    today = date.today()
    while curr <= end_date:
        d_sk = int(curr.strftime("%Y%m%d"))
        dow = curr.isoweekday()  # 1=Mon ... 7=Sun
        is_weekday = dow <= 5
        d_str = curr.isoformat()

        # holidays.json is only an override for forward-looking future dates
        is_future_override = (curr > today) and (d_str in override_holidays)

        if (curr in valid_dates or curr in special_sessions) and not is_future_override:
            is_trading = True
            holiday_name = None
        else:
            is_trading = False
            holiday_name = "NSE Holiday" if is_weekday else None

        date_rows.append((
            d_sk,
            curr,
            curr.year,
            (curr.month - 1) // 3 + 1,
            curr.month,
            curr.isocalendar()[1],
            dow,
            is_weekday,
            is_trading,
            holiday_name,
            "T+1",
        ))
        curr += timedelta(days=1)

    cols = [
        "date_sk", "calendar_date", "year", "quarter", "month", "week_of_year",
        "day_of_week", "is_weekday", "is_trading_day", "holiday_name", "settlement_type"
    ]
    df_dates = pd.DataFrame(date_rows, columns=cols)

    upsert_sql = """
    INSERT INTO dim_date (
        date_sk, calendar_date, year, quarter, month, week_of_year,
        day_of_week, is_weekday, is_trading_day, holiday_name, settlement_type
    )
    SELECT * FROM df_dates
    ON CONFLICT (date_sk) DO UPDATE SET
        is_trading_day = excluded.is_trading_day,
        holiday_name = excluded.holiday_name
    """

    close_conn = False
    if conn is None:
        conn = duckdb.connect(str(db_path))
        close_conn = True

    try:
        conn.register("df_dates", df_dates)
        conn.execute(upsert_sql)
        conn.unregister("df_dates")
        LOGGER.info("Populated dim_date with %d dates (%s to %s)", len(date_rows), start_date, end_date)
        return len(date_rows)
    finally:
        if close_conn:
            conn.close()
