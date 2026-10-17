# Vendored from nse-warehouse (MIT License - Copyright (c) 2026 Siddharth Gaur)
"""Data quality checks as code.

These run against the built warehouse and return findings, not assertions. The
point is not a green tick — it is that twenty years of exchange data contains
real anomalies, and the interesting output is *what they are*. A check suite
that passes silently on this data is a check suite that is not looking.

Each check returns rows. An empty result means the check found nothing, which is
reported as such rather than as success.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Finding:
    check: str
    description: str
    count: int
    sample: list[dict[str, Any]] = field(default_factory=list)


def _rows(conn, sql: str, limit: int = 10) -> tuple[int, list[dict]]:
    result = conn.execute(sql).fetchall()
    names = [d[0] for d in conn.description]
    return len(result), [dict(zip(names, r)) for r in result[:limit]]


def missing_trading_days(conn) -> Finding:
    """Weekdays with no bars, excluding those already known to be holidays.

    The warehouse cannot distinguish "NSE was shut" from "the downloader never
    got this file", so this reports gaps for a human to reconcile against the
    fetch manifest rather than asserting either.
    """
    count, sample = _rows(
        conn,
        """
        WITH bounds AS (SELECT min(trade_date) lo, max(trade_date) hi FROM bars),
        calendar AS (
            SELECT unnest(generate_series(lo, hi, INTERVAL 1 DAY))::DATE AS d FROM bounds
        )
        SELECT d AS missing_day, dayname(d) AS weekday
        FROM calendar
        WHERE dayofweek(d) BETWEEN 1 AND 5
          AND d NOT IN (SELECT trade_date FROM trading_days)
        ORDER BY d
        """,
    )
    return Finding("missing_trading_days", "Weekdays with no published bars", count, sample)


def price_continuity(conn, threshold: float = 0.25) -> Finding:
    """Day-over-day close moves beyond `threshold`, on liquid names only.

    Restricted to symbols with meaningful turnover, because an illiquid
    small-cap printing one trade a day generates enormous ratios that are
    real and uninteresting.
    """
    count, sample = _rows(
        conn,
        f"""
        WITH liquid AS (
            SELECT symbol FROM bars
            GROUP BY symbol HAVING median(turnover) > 10000000
        ),
        moves AS (
            SELECT symbol, trade_date, close,
                   lag(close) OVER (PARTITION BY symbol ORDER BY trade_date) AS prev,
                   lag(trade_date) OVER (PARTITION BY symbol ORDER BY trade_date) AS prev_date
            FROM bars WHERE symbol IN (SELECT symbol FROM liquid)
        )
        SELECT symbol, trade_date, prev_date, prev, close, round(close / prev, 4) AS ratio
        FROM moves
        WHERE prev IS NOT NULL AND prev > 0
          -- Only genuine day-over-day moves. A price either side of a long gap
          -- (suspension, or a seam in a sampled backfill) is not a daily return.
          AND datediff('day', prev_date, trade_date) <= 7
          AND abs(close / prev - 1) > {threshold}
        ORDER BY abs(close / prev - 1) DESC
        """,
    )
    return Finding(
        "price_continuity",
        f"Single-day close moves beyond {threshold:.0%} on liquid symbols "
        "(mostly corporate actions, which is the point)",
        count,
        sample,
    )


def ohlc_consistency(conn) -> Finding:
    """high >= max(open, close) and low <= min(open, close) must hold."""
    count, sample = _rows(
        conn,
        """
        SELECT symbol, trade_date, open, high, low, close
        FROM bars
        WHERE high IS NOT NULL AND low IS NOT NULL
          AND (high < low
               OR high < greatest(coalesce(open, high), coalesce(close, high))
               OR low  > least(coalesce(open, low), coalesce(close, low)))
        ORDER BY trade_date
        """,
    )
    return Finding("ohlc_consistency", "Bars where OHLC bounds are violated", count, sample)


def zero_volume_with_turnover(conn) -> Finding:
    count, sample = _rows(
        conn,
        """
        SELECT symbol, trade_date, volume, turnover FROM bars
        WHERE coalesce(volume, 0) = 0 AND coalesce(turnover, 0) > 0
        ORDER BY trade_date
        """,
    )
    return Finding(
        "zero_volume_with_turnover", "Turnover recorded against zero volume", count, sample
    )


def symbol_isin_changes(conn) -> Finding:
    """Symbols mapping to more than one ISIN over time.

    Usually a face-value change or an amalgamation. Pre-2012 data has no ISIN
    at all, so this check simply cannot see anything in era 1 — a limitation of
    the source, not of the check.
    """
    count, sample = _rows(
        conn,
        """
        SELECT symbol, count(DISTINCT isin) AS isin_count,
               min(trade_date) AS first_seen, max(trade_date) AS last_seen
        FROM bars WHERE isin IS NOT NULL
        GROUP BY symbol HAVING count(DISTINCT isin) > 1
        ORDER BY isin_count DESC
        """,
    )
    return Finding("symbol_isin_changes", "Symbols whose ISIN changed", count, sample)


def isin_symbol_changes(conn) -> Finding:
    """The rename case: one ISIN appearing under several ticker symbols."""
    count, sample = _rows(
        conn,
        """
        SELECT isin, count(DISTINCT symbol) AS symbols,
               string_agg(DISTINCT symbol, ', ') AS names
        FROM bars WHERE isin IS NOT NULL
        GROUP BY isin HAVING count(DISTINCT symbol) > 1
        ORDER BY symbols DESC
        """,
    )
    return Finding("isin_symbol_changes", "ISINs traded under more than one symbol", count, sample)


def delistings(conn, quiet_days: int = 60) -> Finding:
    """Symbols that stopped appearing well before the warehouse's last day."""
    count, sample = _rows(
        conn,
        f"""
        WITH last_day AS (SELECT max(trade_date) AS d FROM bars)
        SELECT symbol, max(trade_date) AS last_traded,
               datediff('day', max(trade_date), (SELECT d FROM last_day)) AS days_quiet
        FROM bars
        GROUP BY symbol
        HAVING datediff('day', max(trade_date), (SELECT d FROM last_day)) > {quiet_days}
        ORDER BY last_traded DESC
        """,
    )
    return Finding(
        "delistings", f"Symbols absent for more than {quiet_days} days", count, sample
    )


def breadth_outliers(conn) -> Finding:
    """Days whose symbol count is far from the local norm — a truncated file."""
    count, sample = _rows(
        conn,
        """
        WITH b AS (SELECT trade_date, symbols FROM daily_breadth),
        stats AS (SELECT median(symbols) AS med FROM b)
        SELECT trade_date, symbols, (SELECT med FROM stats) AS median_symbols
        FROM b WHERE symbols < (SELECT med FROM stats) * 0.5
        ORDER BY symbols
        """,
    )
    return Finding(
        "breadth_outliers", "Days with less than half the median symbol count", count, sample
    )


ALL_CHECKS = (
    missing_trading_days,
    price_continuity,
    ohlc_consistency,
    zero_volume_with_turnover,
    symbol_isin_changes,
    isin_symbol_changes,
    delistings,
    breadth_outliers,
)


def run_all(conn) -> list[Finding]:
    return [check(conn) for check in ALL_CHECKS]
