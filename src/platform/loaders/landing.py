"""Landing layer loader for raw downloads and manifest registration."""

from __future__ import annotations

import csv
import shutil
import tempfile
from datetime import date
from pathlib import Path

from powernse import BhavcopyDownloader

from src.platform.exceptions import LineageIntegrityError, PlatformError
from src.platform.lineage import compute_file_sha256, generate_batch_id, write_manifest


class LandingLoader:
    """Manages raw immutable downloads into data/landing/."""

    def __init__(self, landing_root: Path | str = "data/landing") -> None:
        self.landing_root = Path(landing_root)

    def _next_batch_id(self, source: str, trade_date: date) -> str:
        """Scan date folder to generate unique monotonic batch ID."""
        date_dir = self.landing_root / source / trade_date.isoformat()
        if not date_dir.exists():
            return generate_batch_id(source, trade_date, seq=1)
        existing_seqs: list[int] = []
        for p in date_dir.iterdir():
            if p.is_dir() and "_" in p.name:
                try:
                    existing_seqs.append(int(p.name.split("_")[-1]))
                except ValueError:
                    pass
        next_seq = max(existing_seqs, default=0) + 1
        return generate_batch_id(source, trade_date, seq=next_seq)

    def ingest(self, source: str, trade_date: date) -> str:
        """Download raw archive and register manifest. Returns batch_id."""
        if source != "nse_bhavcopy":
            raise PlatformError(f"Unsupported ingestion source: {source}")

        batch_id = self._next_batch_id(source, trade_date)
        batch_dir = self.landing_root / source / trade_date.isoformat() / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            downloader = BhavcopyDownloader(tmpdir)
            try:
                downloaded_path = downloader.download_day(trade_date)
            except Exception as exc:
                raise PlatformError(
                    f"Download failed for {source} on {trade_date.isoformat()}: {exc}"
                ) from exc

            payload_path = batch_dir / "bhavcopy.csv"
            shutil.copy2(downloaded_path, payload_path)

        file_sha256 = compute_file_sha256(payload_path)
        with open(payload_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                raise LineageIntegrityError(f"Downloaded payload {payload_path} is empty")
            row_count = sum(1 for row in reader if any(cell.strip() for cell in row))

        manifest_data = {
            "batch_id": batch_id,
            "source": source,
            "trade_date": trade_date.isoformat(),
            "file_name": "bhavcopy.csv",
            "file_sha256": file_sha256,
            "row_count": row_count,
        }
        write_manifest(batch_dir / "manifest.json", manifest_data)
        return batch_id

    def validate_manifest(self, batch_id: str) -> bool:
        """Verify checksum integrity of a landing batch."""
        matches = list(self.landing_root.glob(f"*/*/{batch_id}"))
        if not matches:
            return False
        batch_dir = matches[0]
        manifest_file = batch_dir / "manifest.json"
        if not manifest_file.is_file():
            return False
        payload_file = batch_dir / "bhavcopy.csv"
        if not payload_file.is_file():
            return False
        import json

        with open(manifest_file, encoding="utf-8") as f:
            manifest = json.load(f)
        return compute_file_sha256(payload_file) == manifest.get("file_sha256")
