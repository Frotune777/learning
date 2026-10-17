"""NSE surveillance measure fetchers (ASM, GSM, ESM)."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import requests

LOGGER = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def fetch_asm_list(session: requests.Session | None = None) -> pd.DataFrame:
    """Fetch Additional Surveillance Measure (ASM) list."""
    cols = ["symbol", "is_asm", "stage", "from_date"]
    sess = session or _get_session()
    url = "https://www.nseindia.com/api/live-analysis-asm-list"
    try:
        resp = sess.get(url, timeout=5)
        if resp.status_code == 200 and resp.json():
            data = resp.json().get("data", [])
            rows = []
            for item in data:
                sym = item.get("symbol", "").strip().upper()
                if sym:
                    rows.append({
                        "symbol": sym,
                        "is_asm": True,
                        "stage": item.get("stage", "STAGE_1"),
                        "from_date": item.get("effectiveDate") or date.today().isoformat(),
                    })
            if rows:
                return pd.DataFrame(rows)
    except Exception as exc:
        LOGGER.debug("Failed to fetch ASM list from %s: %s", url, exc)

    return pd.DataFrame(columns=cols)


def fetch_gsm_list(session: requests.Session | None = None) -> pd.DataFrame:
    """Fetch Graded Surveillance Measure (GSM) list."""
    cols = ["symbol", "is_gsm", "stage", "from_date"]
    sess = session or _get_session()
    url = "https://www.nseindia.com/api/live-analysis-gsm-list"
    try:
        resp = sess.get(url, timeout=5)
        if resp.status_code == 200 and resp.json():
            data = resp.json().get("data", [])
            rows = []
            for item in data:
                sym = item.get("symbol", "").strip().upper()
                if sym:
                    rows.append({
                        "symbol": sym,
                        "is_gsm": True,
                        "stage": item.get("stage", "STAGE_1"),
                        "from_date": item.get("effectiveDate") or date.today().isoformat(),
                    })
            if rows:
                return pd.DataFrame(rows)
    except Exception as exc:
        LOGGER.debug("Failed to fetch GSM list from %s: %s", url, exc)

    return pd.DataFrame(columns=cols)


def fetch_esm_list(session: requests.Session | None = None) -> pd.DataFrame:
    """Fetch Enhanced Surveillance Measure (ESM) list."""
    cols = ["symbol", "is_esm", "stage", "from_date"]
    sess = session or _get_session()
    url = "https://www.nseindia.com/api/live-analysis-esm-list"
    try:
        resp = sess.get(url, timeout=5)
        if resp.status_code == 200 and resp.json():
            data = resp.json().get("data", [])
            rows = []
            for item in data:
                sym = item.get("symbol", "").strip().upper()
                if sym:
                    rows.append({
                        "symbol": sym,
                        "is_esm": True,
                        "stage": item.get("stage", "STAGE_1"),
                        "from_date": item.get("effectiveDate") or date.today().isoformat(),
                    })
            if rows:
                return pd.DataFrame(rows)
    except Exception as exc:
        LOGGER.debug("Failed to fetch ESM list from %s: %s", url, exc)

    return pd.DataFrame(columns=cols)
