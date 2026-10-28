"""Schema adapter for Modern Bhavcopy era (2012-2019, 13 columns with ISIN)."""

from typing import Any
import pandas as pd
from src.platform.adapters.base import SchemaAdapter

MODERN_HEADERS = {
    "SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE",
    "LAST", "PREVCLOSE", "TOTTRDQTY", "TOTTRDVAL", "TIMESTAMP",
    "TOTALTRADES", "ISIN"
}


class EraModernAdapter(SchemaAdapter):
    """Adapter for modern NSE Bhavcopy files (2012-2019, 13 columns)."""

    @property
    def name(self) -> str:
        return "bhavcopy_era_modern"

    @property
    def category(self) -> str:
        return "price"

    def match(self, headers: list[str]) -> bool:
        clean = {h.strip().upper() for h in headers if not h.strip().startswith("Unnamed")}
        has_modern = MODERN_HEADERS.issubset(clean)
        no_sec = "TTL_TRD_QNTY" not in clean and "DELIV_QTY" not in clean
        return has_modern and no_sec

    def parse(self, df: pd.DataFrame, source_meta: dict[str, Any]) -> pd.DataFrame:
        df = df.copy()
        df.columns = [c.strip().upper() for c in df.columns]

        df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip().str.upper()
        df["SERIES"] = df["SERIES"].astype(str).str.strip().str.upper()
        df["ISIN"] = df["ISIN"].astype(str).str.strip()

        allowed_series = source_meta.get("allowed_series", ["EQ", "BE", "SZ"])
        df = df[df["SERIES"].isin(allowed_series)].copy()

        for col in ["OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY", "TOTTRDVAL", "TOTALTRADES"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

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
            "trades": df["TOTALTRADES"].fillna(0).astype("int64"),
            "isin": df["ISIN"].replace({"": None, "NAN": None}),
            "source_ref": source_meta.get("source_key", "bhavcopy_modern"),
        })
        return out.reset_index(drop=True)
