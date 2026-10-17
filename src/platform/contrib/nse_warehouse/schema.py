# Vendored from nse-warehouse (MIT License - Copyright (c) 2026 Siddharth Gaur)
"""Three eras of NSE bhavcopy, normalised to one row shape.

The spec warned that format changes would ambush this project in week two. They
were mapped up front instead, by fetching real files across two decades. What
follows is what NSE actually served on 2026-08-06, not what its docs claim.

## Era 1 — legacy, no ISIN (archive start .. ~2011)

    SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,
    3MINDIA,EQ,584,585,580,581.1,581,575.55,1387,808306.35,3-JAN-2005,

11 columns. **No TOTALTRADES and no ISIN.** Note the unpadded day in the date
(`3-JAN-2005`) and the trailing comma, which yields a phantom empty column.
Verified present for 1996-01-02.

## Era 2 — legacy + ISIN (~2012 .. 2024-11)

    SYMBOL,...,TIMESTAMP,TOTALTRADES,ISIN,
    20MICRONS,EQ,78,81.5,...,01-MAR-2012,637,INE144J01019,

13 columns. Day is now zero-padded. Verified 2012-03-01 through 2024-07-01;
returns 404 from 2024-12 onwards.

## Era 3 — UDiFF (2024-01 .. present)

34 columns, ISO dates, and a `FinInstrmTp` discriminator that mixes cash
equities (`STK`) with derivatives in one file. Verified 2024-01-02 to
2026-08-05.

**The eras overlap.** Both formats serve 2024-01 through 2024-11. The fetcher
prefers UDiFF where available because it carries strictly more information.

The absence of ISIN before ~2012 is not cosmetic: ISIN is the only stable
identity across a symbol rename, so symbol-change tracking simply cannot be
done on era-1 data. That limitation is stated rather than papered over.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

# The normalised row. Deliberately narrow: what every era can actually supply,
# plus the two fields only later eras have, left null when unavailable.
COLUMNS = (
    "trade_date",   # date
    "symbol",       # str
    "series",       # str  EQ / BE / SM / ...
    "isin",         # str | None  — absent before ~2012
    "open",
    "high",
    "low",
    "close",
    "last",
    "prev_close",
    "volume",       # int
    "turnover",     # float
    "trades",       # int | None — absent before ~2012
)

# Cash-equity series. Everything else in the file is a treasury bill (TB),
# debenture (NC/NE), gold bond (GB) or similar. Keeping them would silently
# corrupt any cross-sectional equity statistic.
EQUITY_SERIES = frozenset({"EQ", "BE", "BZ", "SM", "ST", "IL"})

ERA1_HEADER = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP"
ERA2_EXTRA = ("TOTALTRADES", "ISIN")


class FormatError(ValueError):
    """The file did not match any known era. Never guessed around."""


@dataclass(frozen=True)
class Bar:
    trade_date: date
    symbol: str
    series: str
    isin: str | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    last: float | None
    prev_close: float | None
    volume: int | None
    turnover: float | None
    trades: int | None


def _f(raw: str | None) -> float | None:
    raw = (raw or "").strip()
    if not raw or raw in {"-", "N.A."}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _i(raw: str | None) -> int | None:
    value = _f(raw)
    return None if value is None else int(value)


def parse_legacy_date(raw: str) -> date:
    """`3-JAN-2005` and `01-MAR-2012` both. %d accepts an unpadded day."""
    return datetime.strptime(raw.strip(), "%d-%b-%Y").date()


def detect_era(header: list[str]) -> str:
    """Identify the era from the header alone. Raises rather than guessing."""
    upper = [h.strip().upper() for h in header if h.strip()]
    if "TRADDT" in upper and "FININSTRMTP" in upper:
        return "udiff"
    if upper[:11] == ERA1_HEADER.split(","):
        return "era2" if all(c in upper for c in ERA2_EXTRA) else "era1"
    raise FormatError(f"Unrecognised bhavcopy header: {','.join(upper[:6])}...")


def normalise_legacy(row: dict[str, str]) -> Bar:
    """Era 1 and era 2 share a layout; era 1 simply lacks two columns."""
    return Bar(
        trade_date=parse_legacy_date(row["TIMESTAMP"]),
        symbol=row["SYMBOL"].strip(),
        series=row["SERIES"].strip(),
        isin=(row.get("ISIN") or "").strip() or None,
        open=_f(row.get("OPEN")),
        high=_f(row.get("HIGH")),
        low=_f(row.get("LOW")),
        close=_f(row.get("CLOSE")),
        last=_f(row.get("LAST")),
        prev_close=_f(row.get("PREVCLOSE")),
        volume=_i(row.get("TOTTRDQTY")),
        turnover=_f(row.get("TOTTRDVAL")),
        trades=_i(row.get("TOTALTRADES")),
    )


def normalise_udiff(row: dict[str, str]) -> Bar | None:
    """Era 3. Returns None for rows that are not cash-segment stocks."""
    if (row.get("FinInstrmTp") or "").strip() != "STK":
        return None
    return Bar(
        trade_date=date.fromisoformat(row["TradDt"].strip()),
        symbol=(row.get("TckrSymb") or "").strip(),
        series=(row.get("SctySrs") or "").strip(),
        isin=(row.get("ISIN") or "").strip() or None,
        open=_f(row.get("OpnPric")),
        high=_f(row.get("HghPric")),
        low=_f(row.get("LwPric")),
        close=_f(row.get("ClsPric")),
        last=_f(row.get("LastPric")),
        prev_close=_f(row.get("PrvsClsgPric")),
        volume=_i(row.get("TtlTradgVol")),
        turnover=_f(row.get("TtlTrfVal")),
        trades=_i(row.get("TtlNbOfTxsExctd")),
    )
