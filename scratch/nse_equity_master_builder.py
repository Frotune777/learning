"""
File: nse_equity_master_builder.py
Purpose: Build comprehensive NSE Equity Master table with indices, sectors, and all details.

Uses multiple NSE APIs:
1. sec_list.csv - Base security list
2. /api/equity-stock-indices - Index constituents (from network trace)
3. /api/quote-equity - Individual stock details (sector, industry)
4. CM Security File - ISIN, face value, market lot

Last Modified: 2026-05-27
"""

import json
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


def _retry_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple[int, ...] = (403, 429, 500, 502, 503, 504),
) -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class NSEEquityMasterBuilder:
    """
    Builds comprehensive NSE Equity Master table.

    Network trace shows the working endpoint:
    GET https://www.nseindia.com/api/equity-stock-indices?index=NIFTY%2050

    This fetches index constituents which we use to build membership flags.
    """

    # NSE API endpoints
    INDEX_API_URL: str = "https://www.nseindia.com/api/equity-stock-indices"
    QUOTE_API_URL: str = "https://www.nseindia.com/api/quote-equity"
    SEC_LIST_URL: str = "https://nsearchives.nseindia.com/content/equities/sec_list.csv"

    # All NSE indices to fetch
    INDICES: list[str] = [
        # Broad market indices
        "NIFTY 50",
        "NIFTY 100",
        "NIFTY 200",
        "NIFTY 500",
        "NIFTY NEXT 50",
        # Midcap indices
        "NIFTY MIDCAP 50",
        "NIFTY MIDCAP 100",
        "NIFTY MIDCAP 150",
        # Smallcap indices
        "NIFTY SMALLCAP 50",
        "NIFTY SMALLCAP 100",
        "NIFTY SMALLCAP 250",
        # Sector indices
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

    def __init__(self, cache_dir: str = "data/cache", output_dir: str = "data") -> None:
        self.cache_dir: str = cache_dir
        self.output_dir: str = output_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        self.session: requests.Session = _retry_session()
        # Let requests handle encoding automatically; don't force brotli explicitly
        self.session.headers.update(
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

        self._cookies_ready: bool = False
        self._df_master: pd.DataFrame | None = None

    def _warmup_cookies(self, force: bool = False) -> bool:
        """Get cookies from NSE India main page."""
        if self._cookies_ready and not force:
            return True

        try:
            LOGGER.info("Warming up cookies from nseindia.com...")
            # Clear old cookies to prevent stale session issues
            self.session.cookies.clear()

            resp = self.session.get(
                "https://www.nseindia.com",
                timeout=15,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                },
            )
            LOGGER.info("NSE India status: %d", resp.status_code)

            if resp.status_code == 200:
                # Visit market data page for more cookies
                time.sleep(0.5)
                resp2 = self.session.get(
                    "https://www.nseindia.com/market-data/live-equity-market",
                    timeout=15,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Referer": "https://www.nseindia.com/",
                    },
                )
                LOGGER.info("Market data page status: %d", resp2.status_code)

                self._cookies_ready = True
                time.sleep(0.5)
                return True
        except Exception as e:
            LOGGER.warning("Cookie warmup failed: %s", e)

        return False

    def fetch_sec_list(self) -> pd.DataFrame:
        """Fetch base security list from NSE Archives CSV."""
        LOGGER.info("Fetching security list from: %s", self.SEC_LIST_URL)

        try:
            resp = self.session.get(self.SEC_LIST_URL, timeout=30)
            LOGGER.info("sec_list.csv status: %d", resp.status_code)

            if resp.status_code == 200:
                df = pd.read_csv(StringIO(resp.text))
                LOGGER.info("Loaded %d securities from CSV", len(df))
                return df
        except Exception as e:
            LOGGER.error("sec_list.csv error: %s", e)

        return pd.DataFrame()

    def fetch_index_constituents(
        self, index_name: str
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """
        Fetch constituents for a given index.

        Uses the exact endpoint from the network trace:
        GET /api/equity-stock-indices?index=NIFTY%2050

        Returns:
            Tuple of (symbols_list, raw_data_records)
        """
        if not self._warmup_cookies():
            LOGGER.error("Cannot fetch without cookies")
            return [], []

        LOGGER.info("Fetching constituents for: %s", index_name)

        params = {"index": index_name}
        headers = {
            "Referer": "https://www.nseindia.com/market-data/live-equity-market",
            "Accept": "application/json, text/plain, */*",
        }

        try:
            resp = self.session.get(
                self.INDEX_API_URL,
                params=params,
                headers=headers,
                timeout=30,
            )
            LOGGER.info("Index API status for %s: %d", index_name, resp.status_code)

            # If we get 403, try re-warming cookies once
            if resp.status_code in (401, 403):
                LOGGER.warning(
                    "Got %d for %s, re-warming cookies...", resp.status_code, index_name
                )
                if self._warmup_cookies(force=True):
                    resp = self.session.get(
                        self.INDEX_API_URL,
                        params=params,
                        headers=headers,
                        timeout=30,
                    )
                    LOGGER.info("Retry status for %s: %d", index_name, resp.status_code)

            if resp.status_code == 200:
                data = resp.json()

                symbols = []
                records = []

                if isinstance(data, dict):
                    raw_list = data.get("data") or []
                    for item in raw_list:
                        if not isinstance(item, dict):
                            continue
                        sym = (
                            item.get("symbol")
                            or item.get("Symbol")
                            or item.get("SYMBOL")
                        )
                        if sym:
                            sym = str(sym).strip().upper()
                            symbols.append(sym)
                            # Store enriched record with index context
                            record = {
                                "symbol": sym,
                                "index": index_name,
                                "last_price": item.get("lastPrice"),
                                "change": item.get("change"),
                                "p_change": item.get("pChange"),
                                "ffmc": item.get("ffmc"),  # Free float market cap
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
                            records.append(record)

                    LOGGER.info("Found %d constituents in %s", len(symbols), index_name)

                return symbols, records
            else:
                LOGGER.warning(
                    "Index API returned %d for %s", resp.status_code, index_name
                )

        except Exception as e:
            LOGGER.error("Index API error for %s: %s", index_name, e)

        return [], []

    def fetch_stock_details(self, symbol: str) -> dict[str, Any]:
        """
        Fetch detailed info for a single stock.

        Uses: /api/quote-equity?symbol=TCS
        Returns: Sector, industry, market cap, etc.
        """
        if not self._warmup_cookies():
            return {}

        url = f"{self.QUOTE_API_URL}"
        params = {"symbol": symbol}
        headers = {
            "Referer": f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}",
        }

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()

                details = {}
                if isinstance(data, dict):
                    # Extract relevant fields
                    if "info" in data:
                        info = data["info"]
                        details["sector"] = info.get("sector", "")
                        details["industry"] = info.get("industry", "")
                        details["basic_industry"] = info.get("basicIndustry", "")
                        details["isin"] = info.get("isin", "")

                    if "metadata" in data:
                        meta = data["metadata"]
                        details["face_value"] = meta.get("faceValue", 0)
                        details["issued_size"] = meta.get("issuedSize", 0)

                return details
        except Exception as e:
            LOGGER.warning("Stock details error for %s: %s", symbol, e)

        return {}

    def build_master_table(
        self, skip_details: bool = True, delay: float = 1.0
    ) -> pd.DataFrame:
        """
        Build complete NSE Equity Master table.

        Args:
            skip_details: If True, skip fetching individual stock details
                         (faster, but no sector/industry info)
            delay: Seconds to sleep between index API calls to avoid rate limiting

        Returns:
            DataFrame with comprehensive equity master data
        """
        LOGGER.info("=" * 60)
        LOGGER.info("BUILDING NSE EQUITY MASTER TABLE")
        LOGGER.info("=" * 60)

        # Step 1: Fetch base securities
        LOGGER.info("\n[Step 1/4] Fetching base security list...")
        df = self.fetch_sec_list()

        if df.empty:
            LOGGER.error("Failed to fetch base security list")
            return df

        # Standardize columns
        df = self._standardize_base_columns(df)

        # Filter EQ series only
        if "Series" in df.columns:
            df = df[df["Series"].astype(str).str.strip() == "EQ"].copy()
            LOGGER.info("Filtered to %d EQ series securities", len(df))

        # Step 2: Fetch index memberships and enriched data
        LOGGER.info("\n[Step 2/4] Fetching index constituents...")

        all_index_records = []  # Collect enriched data from all indices

        for index_name in self.INDICES:
            col_name = f"is_{index_name.lower().replace(' ', '_').replace('-', '_')}"

            members, records = self.fetch_index_constituents(index_name)

            if members:
                df[col_name] = df["Symbol"].isin(members)
                count = df[col_name].sum()
                LOGGER.info("  %s: %d members", index_name, count)
                all_index_records.extend(records)
            else:
                df[col_name] = False
                LOGGER.warning("  %s: Failed to fetch", index_name)

            # Polite delay between requests
            time.sleep(delay)

        # Merge enriched index data (latest price, ffmc, etc.) into master
        if all_index_records:
            LOGGER.info("\n[Step 2b] Merging enriched index data...")
            df_enriched = pd.DataFrame(all_index_records)
            # Deduplicate: keep the record with highest ffmc per symbol
            if "ffmc" in df_enriched.columns:
                df_enriched["ffmc"] = pd.to_numeric(
                    df_enriched["ffmc"], errors="coerce"
                )
                df_enriched = df_enriched.sort_values(
                    "ffmc", ascending=False
                ).drop_duplicates("symbol", keep="first")

            # Merge key fields into master
            merge_cols = [
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
            merge_cols = [c for c in merge_cols if c in df_enriched.columns]
            df = df.merge(
                df_enriched[merge_cols], left_on="Symbol", right_on="symbol", how="left"
            )
            # Drop duplicate symbol column from merge
            if "symbol" in df.columns and "Symbol" in df.columns:
                df = df.drop(columns=["symbol"])

        # Step 3: Derive market cap category
        LOGGER.info("\n[Step 3/4] Deriving market cap categories...")
        df["market_cap_category"] = df.apply(self._derive_market_cap, axis=1)

        # Count categories
        cat_counts = df["market_cap_category"].value_counts()
        for cat, count in cat_counts.items():
            LOGGER.info("  %s Cap: %d stocks", cat, count)

        # Step 4: Fetch sector/industry details (optional, slow)
        if not skip_details:
            LOGGER.info("\n[Step 4/4] Fetching sector/industry details...")
            LOGGER.info("  Skipped in this version to avoid rate limiting.")
            LOGGER.info(
                "  Set skip_details=False and implement batch fetching in production."
            )

        # Add metadata
        df["data_source"] = "nse_api"
        df["updated_at"] = datetime.now().isoformat()

        self._df_master = df.copy()

        LOGGER.info("\n" + "=" * 60)
        LOGGER.info("MASTER TABLE BUILT: %d securities", len(df))
        LOGGER.info("=" * 60)

        return df

    def _standardize_base_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names from sec_list.csv."""
        column_map = {
            "SYMBOL": "Symbol",
            "symbol": "Symbol",
            "SERIES": "Series",
            "series": "Series",
            "SECURITY": "SecurityName",
            "SECURITY NAME": "SecurityName",
            "Security Name": "SecurityName",
            "NAME": "SecurityName",
            "NAME OF COMPANY": "SecurityName",
            "BAND": "PriceBand",
            "REMARKS": "Remarks",
            "ISIN": "ISIN",
            "FACE VALUE": "FaceValue",
            "PAID UP VALUE": "PaidUpValue",
            "MARKET LOT": "MarketLot",
        }

        rename_dict = {k: v for k, v in column_map.items() if k in df.columns}
        if rename_dict:
            df = df.rename(columns=rename_dict)

        return df

    def _derive_market_cap(self, row: pd.Series) -> str:
        """
        Derive market cap category from index memberships.

        Priority:
        1. Large Cap: Nifty 100 member (includes Nifty 50, Next 50, 100, 200, 500)
        2. Mid Cap: Nifty Midcap 150 member (not in Nifty 100)
        3. Small Cap: Nifty Smallcap 250 member (not in above)
        4. Micro/Other: Not in any index
        """
        # Check for Large Cap - use specific column names to avoid matching midcap_50
        large_cap_indices = [
            "is_nifty_50",
            "is_nifty_100",
            "is_nifty_200",
            "is_nifty_500",
            "is_nifty_next_50",
        ]
        if any(row.get(c, False) for c in large_cap_indices if c in row.index):
            return "Large"

        # Check for Mid Cap
        mid_cap_indices = [
            "is_nifty_midcap_50",
            "is_nifty_midcap_100",
            "is_nifty_midcap_150",
        ]
        if any(row.get(c, False) for c in mid_cap_indices if c in row.index):
            return "Mid"

        # Check for Small Cap
        small_cap_indices = [
            "is_nifty_smallcap_50",
            "is_nifty_smallcap_100",
            "is_nifty_smallcap_250",
        ]
        if any(row.get(c, False) for c in small_cap_indices if c in row.index):
            return "Small"

        return "Other"

    def save(self, df: pd.DataFrame | None = None) -> dict[str, str]:
        """
        Save master table to multiple formats.

        Returns:
            Dict of format -> filepath
        """
        if df is None:
            df = self._df_master

        if df is None or df.empty:
            LOGGER.error("No data to save")
            return {}

        timestamp = datetime.now().strftime("%Y%m%d")
        files: dict[str, str] = {}

        # Parquet (fast, compressed)
        parquet_path = os.path.join(
            self.output_dir, f"nse_equity_master_{timestamp}.parquet"
        )
        df.to_parquet(parquet_path, index=False)
        files["parquet"] = parquet_path
        LOGGER.info("Saved Parquet: %s", parquet_path)

        # CSV (human-readable)
        csv_path = os.path.join(self.output_dir, f"nse_equity_master_{timestamp}.csv")
        df.to_csv(csv_path, index=False)
        files["csv"] = csv_path
        LOGGER.info("Saved CSV: %s", csv_path)

        # JSON (for APIs)
        json_path = os.path.join(self.output_dir, f"nse_equity_master_{timestamp}.json")
        df.to_json(json_path, orient="records", indent=2)
        files["json"] = json_path
        LOGGER.info("Saved JSON: %s", json_path)

        return files

    def get_summary(self, df: pd.DataFrame | None = None) -> dict[str, Any]:
        """Get summary statistics of the master table."""
        if df is None:
            df = self._df_master

        if df is None or df.empty:
            return {}

        summary = {
            "total_securities": len(df),
            "by_market_cap": df["market_cap_category"].value_counts().to_dict(),
        }

        # Count by index
        index_cols = [c for c in df.columns if c.startswith("is_nifty")]
        for col in index_cols:
            index_name = col.replace("is_", "").replace("_", " ").upper()
            count = df[col].sum()
            if count > 0:
                summary[f"{index_name}_members"] = int(count)

        return summary


# Standalone test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    builder = NSEEquityMasterBuilder()

    print("\n=== Building NSE Equity Master Table ===")
    df = builder.build_master_table(skip_details=True)

    if not df.empty:
        print(f"\n✅ SUCCESS: Built master table with {len(df)} securities")

        # Show sample
        print("\nFirst 10 rows:")
        display_cols = [
            "Symbol",
            "SecurityName",
            "market_cap_category",
            "last_price",
            "ffmc",
        ]
        display_cols = [c for c in display_cols if c in df.columns]
        print(df.head(10)[display_cols].to_string())

        # Show index counts
        print("\nIndex Memberships:")
        index_cols = [c for c in df.columns if c.startswith("is_nifty")]
        for col in sorted(index_cols):
            count = df[col].sum()
            if count > 0:
                print(f"  {col.replace('is_', '').replace('_', ' ').upper()}: {count}")

        # Save
        files = builder.save(df)
        print("\nSaved to:")
        for fmt, path in files.items():
            print(f"  {fmt}: {path}")

        # Summary
        summary = builder.get_summary(df)
        print(f"\nSummary: {json.dumps(summary, indent=2)}")
    else:
        print("\n❌ FAILED: Could not build master table")
