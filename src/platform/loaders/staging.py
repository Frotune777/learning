"""Staging layer loader for canonical typed Parquet transformation."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd

from src.platform.exceptions import PlatformError, SchemaValidationError
from src.platform.schemas import load


class StagingLoader:
    """Transforms raw landed files into validated canonical staging Parquets."""

    CANONICAL_COLUMNS: ClassVar[list[str]] = [
        "symbol",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "turnover",
        "trades",
        "vwap",
        "source_batch_id",
        "ingested_at",
    ]

    def __init__(
        self,
        landing_root: Path | str = "data/landing",
        staging_root: Path | str = "data/staging",
    ) -> None:
        self.landing_root = Path(landing_root)
        self.staging_root = Path(staging_root)

    def _find_batch_dir(self, batch_id: str) -> Path:
        matches = list(self.landing_root.glob(f"*/*/{batch_id}"))
        if not matches:
            raise PlatformError(f"Landing batch not found: {batch_id}")
        return matches[0]

    def stage(self, batch_id: str, schema_name: str = "price_daily") -> int:
        """Parse landing batch, validate schema/integrity, and write partitioned Parquet."""
        schema = load(schema_name)
        batch_dir = self._find_batch_dir(batch_id)
        payload_file = batch_dir / "bhavcopy.csv"
        manifest_file = batch_dir / "manifest.json"

        if not payload_file.is_file():
            raise PlatformError(f"Missing payload file: {payload_file}")

        with open(manifest_file, encoding="utf-8") as f:
            manifest = json.load(f)

        trade_date_str = manifest.get("trade_date")
        if not trade_date_str:
            raise SchemaValidationError("Manifest missing 'trade_date'")

        rows: list[dict] = []
        with open(payload_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = (row.get("TckrSymb") or row.get("symbol") or "").strip()
                t_date = (row.get("TradDt") or row.get("trade_date") or trade_date_str).strip()

                if not sym:
                    raise SchemaValidationError("Row contains empty symbol")
                if not t_date:
                    raise SchemaValidationError("Row contains empty trade_date")

                try:
                    opn = float(row.get("OpnPric") or row.get("open", 0.0))
                    hgh = float(row.get("HghPric") or row.get("high", 0.0))
                    low = float(row.get("LwPric") or row.get("low", 0.0))
                    cls = float(row.get("ClsPric") or row.get("close", 0.0))
                    vol = int(float(row.get("TtlTradgVol") or row.get("volume", 0)))
                    trn = float(row.get("TtlTrfVal") or row.get("turnover", 0.0))
                    txs = int(float(row.get("TtlNbOfTxsExctd") or row.get("trades", 0)))
                except (ValueError, TypeError) as exc:
                    msg = f"Invalid numeric value in bar for {sym}: {exc}"
                    raise SchemaValidationError(msg) from exc

                if hgh < low:
                    msg = f"OHLC violation for {sym}: high ({hgh}) < low ({low})"
                    raise SchemaValidationError(msg)
                if cls <= 0:
                    msg = f"OHLC violation for {sym}: close ({cls}) <= 0"
                    raise SchemaValidationError(msg)

                vwap = (trn / vol) if vol > 0 else cls

                rows.append({
                    "symbol": sym,
                    "trade_date": t_date,
                    "open": opn,
                    "high": hgh,
                    "low": low,
                    "close": cls,
                    "volume": vol,
                    "turnover": trn,
                    "trades": txs,
                    "vwap": vwap,
                    "source_batch_id": batch_id,
                    "ingested_at": datetime.now(UTC).isoformat(),
                })

        df = pd.DataFrame(rows)
        # Ensure schema column mapping is honored
        for col in self.CANONICAL_COLUMNS:
            if col not in df.columns:
                raise SchemaValidationError(f"Missing canonical column: {col}")

        df = df[self.CANONICAL_COLUMNS]

        out_dir = self.staging_root / schema.name / f"dt={trade_date_str}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{batch_id}.parquet"
        df.to_parquet(out_path, index=False)

        return len(df)

    def validate_staging_parquet(self, parquet_path: Path | str) -> bool:
        """Validate staging Parquet columns, nullability, and types."""
        p = Path(parquet_path)
        if not p.is_file():
            return False
        df = pd.read_parquet(p)
        if not set(self.CANONICAL_COLUMNS).issubset(set(df.columns)):
            return False
        if df["symbol"].isna().any() or df["trade_date"].isna().any():
            return False
        if (df["high"] < df["low"]).any() or (df["close"] <= 0).any():
            return False
        return True

    def stage_equity_master(self, batch_id: str | None = None) -> int:
        """Parse landed EQUITY_L.csv into canonical staging/equity_master Parquet."""
        if batch_id:
            batch_dir = self._find_batch_dir(batch_id)
        else:
            candidates = sorted(self.landing_root.glob("nse_equity_l/*/*"))
            if not candidates:
                raise PlatformError("No landed nse_equity_l batches found")
            batch_dir = candidates[-1]

        csv_file = batch_dir / "equity_l.csv"
        manifest_file = batch_dir / "manifest.json"
        if not csv_file.is_file():
            raise PlatformError(f"Missing equity_l.csv in {batch_dir}")

        trade_date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        if manifest_file.is_file():
            with open(manifest_file, encoding="utf-8") as f:
                manifest = json.load(f)
                trade_date_str = manifest.get("trade_date", trade_date_str)
                batch_id = manifest.get("batch_id", batch_dir.name)
        else:
            batch_id = batch_dir.name

        rows: list[dict[str, Any]] = []
        with open(csv_file, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k}
                sym = row.get("SYMBOL", "").upper()
                if not sym:
                    continue
                srs = row.get("SERIES", "EQ").upper()
                rows.append({
                    "symbol": sym,
                    "isin": row.get("ISIN NUMBER", ""),
                    "company_name": row.get("NAME OF COMPANY", sym),
                    "series": srs,
                    "sector": None,
                    "macro_sector": None,
                    "is_active": True,
                    "classification": "HEALTHY",
                    "as_of_date": trade_date_str,
                    "batch_id": batch_id,
                })

        df = pd.DataFrame(rows)
        out_dir = self.staging_root / "equity_master" / f"dt={trade_date_str}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{batch_id}.parquet"
        df.to_parquet(out_path, index=False)
        return len(df)

    def stage_index_membership(self, batch_id: str | None = None) -> int:
        """Parse landed index constituent CSVs into canonical staging/index_membership Parquet."""
        if batch_id:
            batch_dir = self._find_batch_dir(batch_id)
        else:
            candidates = sorted(self.landing_root.glob("nse_index_constituents/*/*"))
            if not candidates:
                raise PlatformError("No landed nse_index_constituents batches found")
            batch_dir = candidates[-1]

        manifest_file = batch_dir / "manifest.json"
        trade_date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        if manifest_file.is_file():
            with open(manifest_file, encoding="utf-8") as f:
                manifest = json.load(f)
                trade_date_str = manifest.get("trade_date", trade_date_str)
                batch_id = manifest.get("batch_id", batch_dir.name)
        else:
            batch_id = batch_dir.name

        rows: list[dict[str, Any]] = []
        for csv_path in sorted(batch_dir.glob("*.csv")):
            index_code = csv_path.stem.upper()
            with open(csv_path, encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for raw_row in reader:
                    row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k}
                    sym = row.get("Symbol", "").upper()
                    if not sym:
                        continue
                    rows.append({
                        "index_code": index_code,
                        "symbol": sym,
                        "isin": row.get("ISIN Code", ""),
                        "weight": None,
                        "valid_from": trade_date_str,
                        "valid_to": None,
                        "batch_id": batch_id,
                    })

        df = pd.DataFrame(rows)
        out_dir = self.staging_root / "index_membership" / f"dt={trade_date_str}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{batch_id}.parquet"
        df.to_parquet(out_path, index=False)
        return len(df)

    def stage_fo_flags(self, batch_id: str | None = None) -> int:
        """Parse landed F&O market lots CSV into staging Parquet."""
        if batch_id:
            batch_dir = self._find_batch_dir(batch_id)
        else:
            candidates = sorted(self.landing_root.glob("nse_fo_mktlots/*/*"))
            if not candidates:
                raise PlatformError("No landed nse_fo_mktlots batches found")
            batch_dir = candidates[-1]

        csv_file = batch_dir / "fo_mktlots.csv"
        trade_date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        batch_id = batch_dir.name

        rows: list[dict[str, Any]] = []
        if csv_file.is_file():
            with open(csv_file, encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for parts in reader:
                    if len(parts) >= 2 and parts[1].strip():
                        sym = parts[1].strip().upper()
                        if sym != "SYMBOL":
                            rows.append({
                                "symbol": sym,
                                "is_fo": True,
                                "batch_id": batch_id,
                            })

        df = pd.DataFrame(rows).drop_duplicates(subset=["symbol"])
        out_dir = self.staging_root / "fo_mktlots" / f"dt={trade_date_str}"
        out_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_dir / f"{batch_id}.parquet", index=False)
        return len(df)

    def stage_delivery_daily(self, batch_id: str | None = None) -> int:
        """Parse sec_bhavdata_full into canonical staging/delivery_daily Parquet."""
        if batch_id:
            batch_dir = self._find_batch_dir(batch_id)
        else:
            candidates = sorted(self.landing_root.glob("nse_sec_bhavdata_full/*/*"))
            if not candidates:
                raise PlatformError("No landed nse_sec_bhavdata_full batches found")
            batch_dir = candidates[-1]

        csv_file = batch_dir / "sec_bhavdata_full.csv"
        manifest_file = batch_dir / "manifest.json"
        trade_date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        if manifest_file.is_file():
            with open(manifest_file, encoding="utf-8") as f:
                manifest = json.load(f)
                trade_date_str = manifest.get("trade_date", trade_date_str)
                batch_id = manifest.get("batch_id", batch_dir.name)
        else:
            batch_id = batch_dir.name

        rows: list[dict[str, Any]] = []
        with open(csv_file, encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                row = {k.strip(): (v.strip() if v else "") for k, v in raw_row.items() if k}
                sym = row.get("SYMBOL", "").upper()
                if not sym:
                    continue
                srs = row.get("SERIES", "EQ").upper()
                d_str = row.get("DATE1", trade_date_str)
                try:
                    t_date = pd.to_datetime(d_str).strftime("%Y-%m-%d")
                except Exception:
                    t_date = trade_date_str

                def _parse_int(val: str) -> int | None:
                    try:
                        return int(float(val)) if val and val != "-" else None
                    except Exception:
                        return None

                def _parse_float(val: str) -> float | None:
                    try:
                        return float(val) if val and val != "-" else None
                    except Exception:
                        return None

                rows.append({
                    "trade_date": t_date,
                    "symbol": sym,
                    "series": srs,
                    "traded_qty": _parse_int(row.get("TTL_TRD_QNTY", "0")) or 0,
                    "deliverable_qty": _parse_int(row.get("DELIV_QTY", "")),
                    "delivery_pct": _parse_float(row.get("DELIV_PER", "")),
                    "batch_id": batch_id,
                })

        df = pd.DataFrame(rows)
        out_dir = self.staging_root / "delivery_daily" / f"dt={trade_date_str}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{batch_id}.parquet"
        df.to_parquet(out_path, index=False)
        return len(df)

