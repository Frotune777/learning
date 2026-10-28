"""Schema adapter for Legacy Bhavcopy era (2000-2006/2011, 11 columns)."""

from typing import Any
import pandas as pd
from src.platform.adapters.base import SchemaAdapter

LEGACY_HEADERS = {
    "SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE",
    "LAST", "PREVCLOSE", "TOTTRDQTY", "TOTTRDVAL", "TIMESTAMP"
}
EXCLUDED_COLS = {"TOTALTRADES", "ISIN", "DELIV_QTY", "TTL_TRD_QNTY", "DELIV_PER"}


class EraLegacyAdapter(SchemaAdapter):
    """Adapter for legacy NSE Bhavcopy files (11 columns)."""

    @property
    def name(self) -> str:
        return "bhavcopy_era_legacy"

    @property
    def category(self) -> str:
        return "price"

    def match(self, headers: list[str]) -> bool:
        clean = {h.strip().upper() for h in headers if not h.strip().startswith("Unnamed")}
        return LEGACY_HEADERS.issubset(clean) and not (clean & EXCLUDED_COLS)

    def parse(self, df: pd.DataFrame, source_meta: dict[str, Any]) -> pd.DataFrame:
        df = df.copy()
        # Clean headers
        df.columns = [c.strip().upper() for c in df.columns]
        
        # Strip string columns
        df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip().str.upper()
        df["SERIES"] = df["SERIES"].astype(str).str.strip().str.upper()

        # Series filter (EQ, BE, SZ by default)
        allowed_series = source_meta.get("allowed_series", ["EQ", "BE", "SZ"])
        df = df[df["SERIES"].isin(allowed_series)].copy()

        # Parse numeric columns
        for col in ["OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY", "TOTTRDVAL"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Reject invalid close prices
        df = df[df["CLOSE"].notna() & (df["CLOSE"] > 0)].copy()

        # Parse date
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
            "source_ref": source_meta.get("source_key", "bhavcopy_legacy"),
        })
        return out.reset_index(drop=True)
