"""Master data and reference entity enrichment loaders for Tier 1 and Tier 2."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import requests

from src.platform.exceptions import IngestionError
from src.platform.lineage import (
    compute_bytes_sha256,
    generate_batch_id,
    write_manifest,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

INDEX_FILENAMES: dict[str, str] = {
    "NIFTY_50": "ind_nifty50list.csv",
    "NIFTY_NEXT_50": "ind_niftynext50list.csv",
    "NIFTY_100": "ind_nifty100list.csv",
    "NIFTY_200": "ind_nifty200list.csv",
    "NIFTY_500": "ind_nifty500list.csv",
    "NIFTY_MIDCAP_50": "ind_niftymidcap50list.csv",
    "NIFTY_MIDCAP_100": "ind_niftymidcap100list.csv",
    "NIFTY_MIDCAP_150": "ind_niftymidcap150list.csv",
    "NIFTY_SMALLCAP_50": "ind_niftysmallcap50list.csv",
    "NIFTY_SMALLCAP_100": "ind_niftysmallcap100list.csv",
    "NIFTY_SMALLCAP_250": "ind_niftysmallcap250list.csv",
    "NIFTY_BANK": "ind_niftybanklist.csv",
    "NIFTY_IT": "ind_niftyitlist.csv",
    "NIFTY_PSU_BANK": "ind_niftypsubanklist.csv",
    "NIFTY_FMCG": "ind_niftyfmcglist.csv",
    "NIFTY_PHARMA": "ind_niftypharmalist.csv",
    "NIFTY_AUTO": "ind_niftyautolist.csv",
    "NIFTY_METAL": "ind_niftymetallist.csv",
    "NIFTY_REALTY": "ind_niftyrealtylist.csv",
    "NIFTY_MEDIA": "ind_niftymedialist.csv",
    "NIFTY_INFRA": "ind_niftyinfralist.csv",
    "NIFTY_ENERGY": "ind_niftyenergylist.csv",
    "NIFTY_COMMODITIES": "ind_niftycommoditieslist.csv",
    "NIFTY_CONSUMPTION": "ind_niftyconsumptionlist.csv",
    "NIFTY_FIN_SERVICE": "ind_niftyfinancelist.csv",
}


class MasterEnrichmentLoader:
    """Manages downloading Tier 1 and Tier 2 reference datasets into landing layer."""

    def __init__(self, landing_root: Path | str = "data/landing") -> None:
        self.landing_root = Path(landing_root)

    def _download(self, url: str, max_retries: int = 3) -> bytes:
        """Download remote content with retries and realistic headers."""
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        for attempt in range(1, max_retries + 1):
            try:
                resp = session.get(url, timeout=15)
                if resp.status_code == 200 and resp.content:
                    return resp.content
                LOGGER.warning("HTTP %d downloading %s (attempt %d/%d)",
                               resp.status_code, url, attempt, max_retries)
            except Exception as exc:
                LOGGER.warning("Error downloading %s (attempt %d/%d): %s",
                               url, attempt, max_retries, exc)
        raise IngestionError(f"Failed to download {url} after {max_retries} attempts")

    def ingest_equity_l(self, as_of: date | None = None) -> int:
        """Download EQUITY_L.csv, write to landing, and record manifest."""
        target_date = as_of or date.today()
        d_str = target_date.strftime("%Y-%m-%d")
        for eb in sorted((self.landing_root / "nse_equity_l" / d_str).glob("*")):
            f = eb / "equity_l.csv"
            if f.is_file() and (eb / "manifest.json").is_file():
                LOGGER.info("Reusing existing landing EQUITY_L: %s", f)
                return max(0, len(f.read_text(errors="ignore").splitlines()) - 1)

        batch_id = generate_batch_id("nse_equity_l", target_date)
        dest_dir = self.landing_root / "nse_equity_l" / d_str / batch_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        content = self._download(url)
        dest_file = dest_dir / "equity_l.csv"
        dest_file.write_bytes(content)

        lines = content.decode("utf-8", errors="ignore").splitlines()
        row_count = max(0, len(lines) - 1)

        write_manifest(
            dest_dir / "manifest.json",
            {
                "batch_id": batch_id,
                "source": "nse_equity_l",
                "trade_date": d_str,
                "row_count": row_count,
                "sha256": compute_bytes_sha256(content),
                "url": url,
            },
        )
        LOGGER.info("Ingested EQUITY_L: %d rows to %s", row_count, dest_file)
        return row_count

    def ingest_index_constituents(self, as_of: date | None = None) -> int:
        """Download all 25 index constituent CSVs into landing layer."""
        target_date = as_of or date.today()
        d_str = target_date.strftime("%Y-%m-%d")
        for eb in sorted((self.landing_root / "nse_index_constituents" / d_str).glob("*")):
            csvs = list(eb.glob("*.csv"))
            if len(csvs) >= 20 and (eb / "manifest.json").is_file():
                LOGGER.info("Reusing %d existing index constituents in %s", len(csvs), eb)
                return sum(max(0, len(p.read_text(errors="ignore").splitlines()) - 1) for p in csvs)

        batch_id = generate_batch_id("nse_index_constituents", target_date)
        dest_dir = self.landing_root / "nse_index_constituents" / d_str / batch_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        base_url = "https://nsearchives.nseindia.com/content/indices/"
        total_rows = 0
        details: dict[str, int] = {}

        for index_code, filename in INDEX_FILENAMES.items():
            url = base_url + filename
            try:
                content = self._download(url)
                (dest_dir / f"{index_code}.csv").write_bytes(content)
                lines = content.decode("utf-8", errors="ignore").splitlines()
                rows = max(0, len(lines) - 1)
                total_rows += rows
                details[index_code] = rows
            except Exception as exc:
                LOGGER.error("Failed to ingest constituent list for %s: %s", index_code, exc)

        write_manifest(
            dest_dir / "manifest.json",
            {
                "batch_id": batch_id,
                "source": "nse_index_constituents",
                "trade_date": d_str,
                "total_rows": total_rows,
                "index_count": len(details),
                "details": details,
            },
        )
        LOGGER.info("Ingested %d index constituents across %d indices", total_rows, len(details))
        return total_rows

    def ingest_fo_mktlots(self, as_of: date | None = None) -> int:
        """Download F&O market lots CSV."""
        target_date = as_of or date.today()
        d_str = target_date.strftime("%Y-%m-%d")
        for eb in sorted((self.landing_root / "nse_fo_mktlots" / d_str).glob("*")):
            f = eb / "fo_mktlots.csv"
            if f.is_file() and (eb / "manifest.json").is_file():
                LOGGER.info("Reusing existing landing fo_mktlots: %s", f)
                return max(0, len(f.read_text(errors="ignore").splitlines()) - 1)

        batch_id = generate_batch_id("nse_fo_mktlots", target_date)
        dest_dir = self.landing_root / "nse_fo_mktlots" / d_str / batch_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        url = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
        content = self._download(url)
        (dest_dir / "fo_mktlots.csv").write_bytes(content)
        lines = content.decode("utf-8", errors="ignore").splitlines()
        row_count = max(0, len(lines) - 1)

        write_manifest(
            dest_dir / "manifest.json",
            {
                "batch_id": batch_id,
                "source": "nse_fo_mktlots",
                "trade_date": d_str,
                "row_count": row_count,
                "sha256": compute_bytes_sha256(content),
            },
        )
        return row_count

    def ingest_sec_list(self, as_of: date | None = None) -> int:
        """Download full securities list CSV."""
        target_date = as_of or date.today()
        d_str = target_date.strftime("%Y-%m-%d")
        for eb in sorted((self.landing_root / "nse_sec_list" / d_str).glob("*")):
            f = eb / "sec_list.csv"
            if f.is_file() and (eb / "manifest.json").is_file():
                LOGGER.info("Reusing existing landing sec_list: %s", f)
                return max(0, len(f.read_text(errors="ignore").splitlines()) - 1)

        batch_id = generate_batch_id("nse_sec_list", target_date)
        dest_dir = self.landing_root / "nse_sec_list" / d_str / batch_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        url = "https://nsearchives.nseindia.com/content/equities/sec_list.csv"
        content = self._download(url)
        (dest_dir / "sec_list.csv").write_bytes(content)
        lines = content.decode("utf-8", errors="ignore").splitlines()
        row_count = max(0, len(lines) - 1)

        write_manifest(
            dest_dir / "manifest.json",
            {
                "batch_id": batch_id,
                "source": "nse_sec_list",
                "trade_date": d_str,
                "row_count": row_count,
                "sha256": compute_bytes_sha256(content),
            },
        )
        return row_count

    def ingest_sec_bhavdata_full(self, trade_date: date) -> int:
        """Download official full bhavcopy with delivery stats for a given trade date."""
        d_str = trade_date.strftime("%Y-%m-%d")
        for eb in sorted((self.landing_root / "nse_sec_bhavdata_full" / d_str).glob("*")):
            f = eb / "sec_bhavdata_full.csv"
            if f.is_file() and (eb / "manifest.json").is_file():
                LOGGER.info("Reusing existing landing sec_bhavdata_full: %s", f)
                return max(0, len(f.read_text(errors="ignore").splitlines()) - 1)

        stamp = trade_date.strftime("%d%m%Y")
        batch_id = generate_batch_id("nse_sec_bhavdata_full", trade_date)
        dest_dir = self.landing_root / "nse_sec_bhavdata_full" / d_str / batch_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{stamp}.csv"
        content = self._download(url)
        (dest_dir / "sec_bhavdata_full.csv").write_bytes(content)
        lines = content.decode("utf-8", errors="ignore").splitlines()
        row_count = max(0, len(lines) - 1)

        write_manifest(
            dest_dir / "manifest.json",
            {
                "batch_id": batch_id,
                "source": "nse_sec_bhavdata_full",
                "trade_date": d_str,
                "row_count": row_count,
                "sha256": compute_bytes_sha256(content),
            },
        )
        return row_count
