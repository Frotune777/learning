"""Schema adapter for modern NSE sec_bhavdata_full archives (2020+)."""

from typing import Any
import pandas as pd
from src.platform.adapters.base import SchemaAdapter

SEC_HEADERS = {"OPEN_PRICE", "HIGH_PRICE", "LOW_PRICE", "CLOSE_PRICE", "TTL_TRD_QNTY"}


class SecBhavdataAdapter(SchemaAdapter):
    """Adapter for NSE sec_bhavdata_full daily archives (2020+).
    
    Contains price and delivery data.
    """

    @property
    def name(self) -> str:
        return "sec_bhavdata"

    @property
    def category(self) -> str:
        return "price_and_delivery"

    def match(self, headers: list[str]) -> bool:
        clean = {h.strip().upper() for h in headers if not h.strip().startswith("Unnamed")}
        return SEC_HEADERS.issubset(clean)

    def parse(self, df: pd.DataFrame, source_meta: dict[str, Any]) -> pd.DataFrame:
        df = df.copy()
        df.columns = [c.strip().upper() for c in df.columns]

        # Support alias columns if present
        sym_col = "SYMBOL" if "SYMBOL" in df.columns else "TCKRSYMB"
        series_col = "SERIES" if "SERIES" in df.columns else "SCTYSRS"

        df["symbol"] = df[sym_col].astype(str).str.strip().str.upper()
        df["series"] = df[series_col].astype(str).str.strip().str.upper()

        allowed_series = source_meta.get("allowed_series", ["EQ", "BE", "SZ"])
        df = df[df["series"].isin(allowed_series)].copy()

        def _to_num(c: str) -> pd.Series:
            if c not in df.columns:
                return pd.Series(0.0, index=df.index)
            return pd.to_numeric(df[c].astype(str).str.strip().replace({"-": "0", "": "0"}), errors="coerce").fillna(0.0)

        df["open"] = _to_num("OPEN_PRICE")
        df["high"] = _to_num("HIGH_PRICE")
        df["low"] = _to_num("LOW_PRICE")
        df["close"] = _to_num("CLOSE_PRICE")
        df["last"] = _to_num("LAST_PRICE")
        df["prev_close"] = _to_num("PREV_CLOSE")
        df["volume"] = _to_num("TTL_TRD_QNTY").astype("int64")
        df["turnover"] = _to_num("TURNOVER_LACS") * 100000.0
        df["trades"] = _to_num("NO_OF_TRADES").astype("int64")
        df["vwap"] = _to_num("AVG_PRICE")

        if "DELIV_QTY" in df.columns:
            df["delivery_qty"] = _to_num("DELIV_QTY").astype("int64")
        if "DELIV_PER" in df.columns:
            df["delivery_pct"] = _to_num("DELIV_PER")

        # Sanity check: valid close and high >= low
        valid_mask = (df["close"] > 0) & (df["high"] >= df["low"])
        df = df[valid_mask].copy()

        # Date parsing
        date_col = "DATE1" if "DATE1" in df.columns else [c for c in df.columns if "DATE" in c][0]
        # Format can be DD-Mon-YYYY or DD-MM-YYYY
        raw_dates = df[date_col].astype(str).str.strip()
        parsed_dates = pd.to_datetime(raw_dates, errors="coerce").dt.date
        df["trade_date"] = parsed_dates
        df = df[df["trade_date"].notna()].copy()

        out = pd.DataFrame({
            "symbol": df["symbol"],
            "series": df["series"],
            "trade_date": df["trade_date"],
            "open": df["open"].astype(float),
            "high": df["high"].astype(float),
            "low": df["low"].astype(float),
            "close": df["close"].astype(float),
            "last": df["last"].astype(float),
            "prev_close": df["prev_close"].astype(float),
            "volume": df["volume"].astype("int64"),
            "turnover": df["turnover"].astype(float),
            "trades": df["trades"].astype("int64"),
            "vwap": df["vwap"].astype(float),
            "delivery_qty": df.get("delivery_qty", None),
            "delivery_pct": df.get("delivery_pct", None),
            "source_ref": source_meta.get("source_key", "sec_bhavdata"),
        })
        return out.reset_index(drop=True)
