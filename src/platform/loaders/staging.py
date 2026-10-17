"""Staging layer loader for canonical typed Parquet transformation."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

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
