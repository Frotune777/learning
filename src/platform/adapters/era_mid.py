"""Schema adapter for Mid Bhavcopy era (2007-2011, 11-12 columns)."""

from typing import Any
import pandas as pd
from src.platform.adapters.base import SchemaAdapter

CORE_HEADERS = {
    "SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE",
    "LAST", "PREVCLOSE", "TOTTRDQTY", "TOTTRDVAL", "TIMESTAMP"
}


class EraMidAdapter(SchemaAdapter):
    """Adapter for mid-era NSE Bhavcopy files (2007-2011).
    
    Matches files with core Bhavcopy columns that include TOTALTRADES without ISIN,
    or can parse standard 11-col files as an alias to Legacy.
    """

    @property
    def name(self) -> str:
        return "bhavcopy_era_mid"

    @property
    def category(self) -> str:
        return "price"

    def match(self, headers: list[str]) -> bool:
        clean = {h.strip().upper() for h in headers if not h.strip().startswith("Unnamed")}
        # Specifically matches transitional mid-era files having TOTALTRADES but NOT ISIN
        has_core = CORE_HEADERS.issubset(clean)
        has_trades = "TOTALTRADES" in clean
        no_isin = "ISIN" not in clean
        no_sec = "TTL_TRD_QNTY" not in clean and "DELIV_QTY" not in clean
        return has_core and has_trades and no_isin and no_sec

    def parse(self, df: pd.DataFrame, source_meta: dict[str, Any]) -> pd.DataFrame:
        df = df.copy()
        df.columns = [c.strip().upper() for c in df.columns]

        df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip().str.upper()
        df["SERIES"] = df["SERIES"].astype(str).str.strip().str.upper()

        allowed_series = source_meta.get("allowed_series", ["EQ", "BE", "SZ"])
        df = df[df["SERIES"].isin(allowed_series)].copy()

        for col in ["OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY", "TOTTRDVAL"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if "TOTALTRADES" in df.columns:
            df["TOTALTRADES"] = pd.to_numeric(df["TOTALTRADES"], errors="coerce")
        else:
            df["TOTALTRADES"] = None

        df = df[df["CLOSE"].notna() & (df["CLOSE"] > 0)].copy()

        trade_dates = pd.to_datetime(df["TIMESTAMP"], format="%d-%b-%Y", errors="coerce").dt.date
        df["trade_date"] = trade_dates
        df = df[df["trade_date"].notna()].copy()

        out = pd.DataFrame({
            "symbol": df["SYMBOL"],
            "series": df["SERIES"],
            "trade_date": df["trade_date"],
            "open": df["OPEN"].astype(float),
            "high": df["HIGH"].astype(float),
            "low": df["LOW"].astype(float),
            "close": df["CLOSE"].astype(float),
            "volume": df["TOTTRDQTY"].fillna(0).astype("int64"),
            "turnover": df["TOTTRDVAL"].astype(float),
            "trades": df["TOTALTRADES"],
            "source_ref": source_meta.get("source_key", "bhavcopy_mid"),
        })
        return out.reset_index(drop=True)
