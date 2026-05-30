"""
File: src/nse_bhavcopy/equity_master.py
Purpose: Build and update the NSE Equity Master table with index membership flags.

Dependencies:
External:
- pandas>=2.2.3: DataFrame operations and CSV parsing
- requests>=2.32.3: HTTP session with retry adapter
Internal:
- None

Key Components:
Classes:
- NSEEquityMasterBuilder: Downloads sec_list + index constituents and saves Parquet.
Functions:
- None

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Add sector/industry via /api/quote-equity in a separate enrichment pass [4h]

Related Files:
- src/nse_bhavcopy/historical_sync.py: Consumes the master symbol list for history sync.
- main.py: CLI entry point calling build_and_save().
"""

import logging
import os
import time
from datetime import datetime
from io import StringIO
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------
INDICES: list[str] = [
    "NIFTY 50",
    "NIFTY 100",
    "NIFTY 200",
    "NIFTY 500",
    "NIFTY NEXT 50",
    "NIFTY MIDCAP 50",
    "NIFTY MIDCAP 100",
    "NIFTY MIDCAP 150",
    "NIFTY SMALLCAP 50",
    "NIFTY SMALLCAP 100",
    "NIFTY SMALLCAP 250",
    "NIFTY BANK",
    "NIFTY IT",
    "NIFTY PSU BANK",
    "NIFTY FMCG",
    "NIFTY PHARMA",
    "NIFTY AUTO",
    "NIFTY METAL",
    "NIFTY REALTY",
    "NIFTY MEDIA",
    "NIFTY INFRA",
    "NIFTY ENERGY",
    "NIFTY COMMODITIES",
    "NIFTY CONSUMPTION",
    "NIFTY FIN SERVICE",
    "NIFTY PVT BANK",
]

SEC_LIST_URL: str = "https://nsearchives.nseindia.com/content/equities/sec_list.csv"
INDEX_API_URL: str = "https://www.nseindia.com/api/equity-stock-indices"


def _make_session() -> requests.Session:
    """
    Create a requests Session with browser headers and retry adapter.

    Logic:
        Step 1: Instantiate Session.
        Step 2: Mount HTTPAdapter with exponential back-off retries.
        Step 3: Set Firefox User-Agent and NSE-compatible headers.

    Parameters:
        None

    Returns:
        requests.Session: Configured session ready for NSE API calls.

    Raises:
        None

    Example:
        >>> session = _make_session()

    Performance:
        Time Complexity: O(1)
        Space Complexity: O(1)

    Edge Cases Handled:
        - Retry on 403/429/5xx responses.

    Notes:
        Token is irrelevant to the charting API — symbol drives the response.
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(403, 429, 500, 502, 503, 504),
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) "
                "Gecko/20100101 Firefox/150.0"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
    )
    return session


class NSEEquityMasterBuilder:
    """
    Downloads and merges NSE security list with all index membership flags.

    Design Pattern: Facade - wraps multiple NSE API calls into a single build().

    Attributes:
        output_dir (str): Directory to write master Parquet/CSV. | "data"
        cache_dir (str): Intermediate cache directory. | "data/cache"
        session (requests.Session): Shared HTTP session.

    Public Methods:
        - build_and_save(): Full pipeline — fetch, merge, save.
        - get_symbols(): Return list of EQ symbols from saved master.

    Private Methods:
        - _warmup_cookies(): Visit NSE home to acquire session cookies.
        - _fetch_sec_list(): Download base security CSV.
        - _fetch_index(index_name): Fetch one index constituent list.
        - _derive_market_cap(row): Categorize as Large/Mid/Small/Other.

    Usage Flow:
        1. Instantiate NSEEquityMasterBuilder(output_dir, cache_dir).
        2. Call build_and_save() to get the saved Parquet path.
        3. Call get_symbols() to retrieve the equity symbol list.

    State Management:
        - Valid states: Uninitialized, CookiesReady, Built.
        - State transitions: Uninitialized -> CookiesReady -> Built.

    Thread Safety: No - single-threaded sequential API calls.

    Dependencies:
        External: pandas, requests
        Internal: None
    """

    def __init__(
        self,
        output_dir: str = "data",
        cache_dir: str = "data/cache",
    ) -> None:
        """
        Initialize builder with output and cache directories.

        Logic:
            Step 1: Store directory paths and create them if absent.
            Step 2: Build a retrying HTTP session.

        Parameters:
            output_dir (str): Where Parquet/CSV master files are written.
                | Writable path.
            cache_dir (str): Intermediate cache storage. | Writable path.

        Returns:
            None

        Raises:
            OSError: If directories cannot be created.

        Example:
            >>> builder = NSEEquityMasterBuilder()

        Performance:
            Time Complexity: O(1)
            Space Complexity: O(1)

        Edge Cases Handled:
            - Directories created if missing.
        """
        self.output_dir: str = output_dir
        self.cache_dir: str = cache_dir
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)
        self.session: requests.Session = _make_session()
        self._cookies_ready: bool = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _warmup_cookies(self, force: bool = False) -> bool:
        """
        Acquire NSE session cookies by visiting the home and market pages.

        Logic:
            Step 1: Skip if already warmed up and force=False.
            Step 2: GET nseindia.com home page.
            Step 3: GET live-equity-market page for deeper cookie set.

        Parameters:
            force (bool): Re-warm even if already initialized. | Default False.

        Returns:
            bool: True if cookies acquired, False on failure.

        Raises:
            None

        Example:
            >>> builder._warmup_cookies()
            True

        Performance:
            Time Complexity: O(1) [Two HTTP round trips]
            Space Complexity: O(1)

        Edge Cases Handled:
            - Any network exception is caught and logged as warning.
        """
        if self._cookies_ready and not force:
            return True
        try:
            LOGGER.info("Warming up NSE cookies...")
            self.session.cookies.clear()
            self.session.get(
                "https://www.nseindia.com",
                timeout=15,
                headers={
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,*/*;q=0.8"
                    )
                },
            )
            time.sleep(0.5)
            self.session.get(
                "https://www.nseindia.com/market-data/live-equity-market",
                timeout=15,
                headers={
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Referer": "https://www.nseindia.com/",
                },
            )
            self._cookies_ready = True
            time.sleep(0.5)
            LOGGER.info("NSE cookies ready.")
            return True
        except Exception as exc:
            LOGGER.warning("Cookie warmup failed: %s", exc)
            return False

    def _fetch_sec_list(self) -> pd.DataFrame:
        """
        Download the base EQ security list from NSE Archives.

        Logic:
            Step 1: GET sec_list.csv from nsearchives.nseindia.com.
            Step 2: Parse CSV into DataFrame.
            Step 3: Standardize column names.
            Step 4: Filter to EQ series only.

        Parameters:
            None

        Returns:
            pd.DataFrame: Columns: Symbol, Series, SecurityName, Band, Remarks.

        Raises:
            None

        Example:
            >>> df = builder._fetch_sec_list()

        Performance:
            Time Complexity: O(N) [N = number of rows in sec_list.csv]
            Space Complexity: O(N)

        Edge Cases Handled:
            - Returns empty DataFrame on any HTTP or parse failure.
        """
        LOGGER.info("Fetching sec_list.csv from NSE Archives...")
        try:
            resp = self.session.get(SEC_LIST_URL, timeout=30)
            if resp.status_code != 200:
                LOGGER.error("sec_list.csv HTTP %d", resp.status_code)
                return pd.DataFrame()
            df = pd.read_csv(StringIO(resp.text))
            # Standardize column names
            col_map = {
                "SYMBOL": "Symbol",
                "symbol": "Symbol",
                "SERIES": "Series",
                "series": "Series",
                "SECURITY": "SecurityName",
                "SECURITY NAME": "SecurityName",
                "Security Name": "SecurityName",
                "NAME OF COMPANY": "SecurityName",
                "BAND": "Band",
                "PRICE BAND": "Band",
                "REMARKS": "Remarks",
            }
            df = df.rename(
                columns={k: v for k, v in col_map.items() if k in df.columns}
            )
            if "Series" in df.columns:
                df = df[df["Series"].astype(str).str.strip() == "EQ"].copy()
            LOGGER.info("sec_list: %d EQ securities loaded.", len(df))
            return df
        except Exception as exc:
            LOGGER.error("sec_list fetch error: %s", exc)
            return pd.DataFrame()

    def _fetch_index(self, index_name: str) -> tuple[list[str], list[dict[str, Any]]]:
        """
        Fetch constituent symbols and enriched data for one NSE index.

        Logic:
            Step 1: Ensure cookies are ready.
            Step 2: GET /api/equity-stock-indices?index=<name>.
            Step 3: Retry once with fresh cookies on 401/403.
            Step 4: Extract symbol list and price/ffmc record per constituent.

        Parameters:
            index_name (str): NSE index name. | e.g. "NIFTY 50"

        Returns:
            tuple[list[str], list[dict]]:
                - List of uppercase symbols.
                - List of enriched record dicts (price, ffmc, etc.).

        Raises:
            None

        Example:
            >>> syms, recs = builder._fetch_index("NIFTY 50")

        Performance:
            Time Complexity: O(K) [K = index size]
            Space Complexity: O(K)

        Edge Cases Handled:
            - Re-warms cookies on 403 and retries once.
            - Returns empty lists on any failure.
        """
        if not self._warmup_cookies():
            return [], []

        hdrs = {
            "Referer": ("https://www.nseindia.com/market-data/live-equity-market"),
            "Accept": "application/json, text/plain, */*",
        }

        def _do_get() -> requests.Response:
            return self.session.get(
                INDEX_API_URL,
                params={"index": index_name},
                headers=hdrs,
                timeout=30,
            )

        try:
            resp = _do_get()
            if resp.status_code in (401, 403):
                LOGGER.warning(
                    "Got %d for %s — re-warming cookies...",
                    resp.status_code,
                    index_name,
                )
                self._warmup_cookies(force=True)
                resp = _do_get()

            if resp.status_code != 200:
                LOGGER.warning("Index API %d for %s", resp.status_code, index_name)
                return [], []

            raw_list: list[dict[str, Any]] = resp.json().get("data", [])
            symbols: list[str] = []
            records: list[dict[str, Any]] = []
            for item in raw_list:
                sym = item.get("symbol") or item.get("Symbol") or item.get("SYMBOL")
                if not sym:
                    continue
                sym = str(sym).strip().upper()
                symbols.append(sym)
                records.append(
                    {
                        "symbol": sym,
                        "last_price": item.get("lastPrice"),
                        "change": item.get("change"),
                        "p_change": item.get("pChange"),
                        "ffmc": item.get("ffmc"),
                        "total_traded_value": item.get("totalTradedValue"),
                        "total_traded_volume": item.get("totalTradedVolume"),
                        "year_high": item.get("yearHigh"),
                        "year_low": item.get("yearLow"),
                        "day_high": item.get("dayHigh"),
                        "day_low": item.get("dayLow"),
                        "open": item.get("open"),
                        "previous_close": item.get("previousClose"),
                        "near_wkh": item.get("nearWKH"),
                        "near_wkl": item.get("nearWKL"),
                    }
                )
            LOGGER.info("  %s → %d constituents", index_name, len(symbols))
            return symbols, records
        except Exception as exc:
            LOGGER.error("Index fetch error for %s: %s", index_name, exc)
            return [], []

    @staticmethod
    def _derive_market_cap(row: pd.Series) -> str:
        """
        Categorize a security by market cap using its index membership flags.

        Logic:
            Step 1: Check Large Cap flags (Nifty 50/100/200/500/Next50).
            Step 2: Check Mid Cap flags (Midcap 50/100/150).
            Step 3: Check Small Cap flags (Smallcap 50/100/250).
            Step 4: Return "Other" if no flag matched.

        Parameters:
            row (pd.Series): Single row of the master DataFrame.

        Returns:
            str: One of "Large", "Mid", "Small", "Other".

        Raises:
            None

        Example:
            >>> cat = NSEEquityMasterBuilder._derive_market_cap(row)

        Performance:
            Time Complexity: O(1)
            Space Complexity: O(1)

        Edge Cases Handled:
            - Missing columns treated as False.
        """
        large_flags = [
            "is_nifty_50",
            "is_nifty_100",
            "is_nifty_200",
            "is_nifty_500",
            "is_nifty_next_50",
        ]
        if any(row.get(c, False) for c in large_flags if c in row.index):
            return "Large"
        mid_flags = [
            "is_nifty_midcap_50",
            "is_nifty_midcap_100",
            "is_nifty_midcap_150",
        ]
        if any(row.get(c, False) for c in mid_flags if c in row.index):
            return "Mid"
        small_flags = [
            "is_nifty_smallcap_50",
            "is_nifty_smallcap_100",
            "is_nifty_smallcap_250",
        ]
        if any(row.get(c, False) for c in small_flags if c in row.index):
            return "Small"
        return "Other"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build_and_save(self, delay: float = 1.0) -> str:
        """
        Execute the full master-table build pipeline and persist output.

        Logic:
            Step 1: Fetch base EQ security list from sec_list.csv.
            Step 2: Iterate all INDICES fetching membership and price data.
            Step 3: Merge enriched data and derive market-cap categories.
            Step 4: Stamp metadata columns and save Parquet + CSV.

        Parameters:
            delay (float): Polite sleep between index API calls in seconds. | >= 0.0

        Returns:
            str: Absolute path to the saved Parquet master file.

        Raises:
            RuntimeError: If the base security list cannot be fetched.

        Example:
            >>> path = builder.build_and_save()

        Performance:
            Time Complexity: O(N * I) [N securities, I indices]
            Space Complexity: O(N)

        Edge Cases Handled:
            - Raises RuntimeError if sec_list is empty (cannot proceed).
            - Individual index failures are logged; master continues.

        TODO:
            - [ ] Add incremental mode: only update changed memberships [MEDIUM, 3h]
        """
        LOGGER.info("=" * 60)
        LOGGER.info("BUILDING NSE EQUITY MASTER TABLE")
        LOGGER.info("=" * 60)

        df = self._fetch_sec_list()
        if df.empty:
            raise RuntimeError(
                "Failed to fetch NSE security list. Cannot build master."
            )

        all_records: list[dict[str, Any]] = []

        for index_name in INDICES:
            col = "is_" + index_name.lower().replace(" ", "_").replace("-", "_")
            members, records = self._fetch_index(index_name)
            df[col] = df["Symbol"].isin(members)
            all_records.extend(records)
            time.sleep(delay)

        # Merge enriched price/ffmc data
        if all_records:
            df_enr = pd.DataFrame(all_records)
            df_enr["ffmc"] = pd.to_numeric(df_enr["ffmc"], errors="coerce")
            df_enr = df_enr.sort_values("ffmc", ascending=False).drop_duplicates(
                "symbol", keep="first"
            )

            merge_cols = [
                c
                for c in [
                    "symbol",
                    "last_price",
                    "change",
                    "p_change",
                    "ffmc",
                    "total_traded_value",
                    "total_traded_volume",
                    "year_high",
                    "year_low",
                    "day_high",
                    "day_low",
                    "open",
                    "previous_close",
                    "near_wkh",
                    "near_wkl",
                ]
                if c in df_enr.columns
            ]
            df = df.merge(
                df_enr[merge_cols],
                left_on="Symbol",
                right_on="symbol",
                how="left",
            )
            if "symbol" in df.columns:
                df = df.drop(columns=["symbol"])

        df["market_cap_category"] = df.apply(self._derive_market_cap, axis=1)
        df["data_source"] = "nse_api"
        df["updated_at"] = datetime.now().isoformat()

        stamp = datetime.now().strftime("%Y%m%d")
        parquet_path = os.path.join(
            self.output_dir, f"nse_equity_master_{stamp}.parquet"
        )
        csv_path = os.path.join(self.output_dir, f"nse_equity_master_{stamp}.csv")
        df.to_parquet(parquet_path, index=False)
        df.to_csv(csv_path, index=False)

        LOGGER.info("Master saved: %d securities → %s", len(df), parquet_path)
        return parquet_path

    def get_symbols(self, master_path: str) -> list[str]:
        """
        Load a saved master Parquet and return the EQ symbol list.

        Logic:
            Step 1: Read Parquet file into DataFrame.
            Step 2: Return the sorted list of Symbol strings.

        Parameters:
            master_path (str): Path to master Parquet file. | Valid file path.

        Returns:
            list[str]: Sorted uppercase NSE equity symbols.

        Raises:
            FileNotFoundError: If master_path does not exist.

        Example:
            >>> symbols = builder.get_symbols("data/nse_equity_master_20260527.parquet")

        Performance:
            Time Complexity: O(N)
            Space Complexity: O(N)

        Edge Cases Handled:
            - Returns empty list if Symbol column is missing.
        """
        df = pd.read_parquet(master_path)
        if "Symbol" not in df.columns:
            LOGGER.warning("No Symbol column found in %s", master_path)
            return []
        return sorted(df["Symbol"].dropna().str.strip().str.upper().tolist())
