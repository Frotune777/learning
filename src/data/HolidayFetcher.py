"""
File: src/classes/HolidayFetcher.py
Purpose: Automated retrieval and local caching of NSE trading holidays.

Dependencies:
External:
- requests>=2.25.0: [fetching holiday data from NSE JSON API]
Internal:
- N/A

Key Components:
Classes:
- HolidayFetcher: Manages the lifecycle of holiday data retrieval and storage.
Functions:
- fetch_nse_holidays: Pulls raw JSON from NSE and extracts 'CM' segment dates.
- update_config: Syncs local 'config/holidays.json' with remote data.

Last Modified: 2026-02-19
Modified By: LLM

Open Tasks:
- [ ] [LOW] Add support for alternate exchange segments (F&O, CD) [6h]
- [ ] [MEDIUM] Implement automatic backup of holidays.json before update [4h]

Related Files:
- src/classes/Fetcher.py: [references holiday list to adjust lookback periods]
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)


class HolidayFetcher:
    """
    Automates the synchronization of NSE trading holidays for market analysis.

    Design Pattern: Data Synchronizer - maintains local state derived from remote API.

    Attributes:
        NSE_HOME_URL (str): Entry point for session cookie generation.
        NSE_HOLIDAY_API (str): Direct endpoint for trading holiday JSON.
        CONFIG_PATH (Path): Local filesystem destination for JSON storage.
        headers (Dict[str, str]): Static HTTP headers for bypass.
        session (requests.Session): Persistent session for cookie management.

    Public Methods:
        - fetch_nse_holidays(): Retrieves list of YYYY-MM-DD strings.
        - update_config(): Commits remote changes to the local config file.

    Usage Flow:
        1. Instantiate HolidayFetcher()
        2. Call update_config()
        3. Verify local config/holidays.json reflects current calendar.

    State Management:
        - Valid states: Initialized
        - State transitions: N/A

    Thread Safety: No - requests.Session is not inherently thread-safe.

    Dependencies:
        External: requests
        Internal: N/A
    """

    NSE_HOME_URL = "https://www.nseindia.com/"
    NSE_HOLIDAY_API = "https://www.nseindia.com/api/holiday-master?type=trading"
    CONFIG_PATH = Path("config/holidays.json")

    def __init__(self) -> None:
        """Initialize headers and session state."""
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Referer": "https://www.nseindia.com/",
        }
        self.session = requests.Session()

    def fetch_nse_holidays(self) -> list[str]:
        """
        Query the NSE holiday master API and parse the CM (Equities) segment.

        Logic:
            Step 1: Obtain session cookies by visiting the NSE home page.
            Step 2: Authenticate and request holiday JSON from the master endpoint.
            Step 3: Flatten the 'CM' list into a list of sorted date strings.

        Returns:
            List[str]: Unique holiday dates in 'YYYY-MM-DD' format.
        """
        print("🔄 Fetching holidays from NSE API...")

        try:
            # 1. Visit Homepage to get cookies
            print("  Connecting to NSE...")
            self.session.get(self.NSE_HOME_URL, headers=self.headers, timeout=10)

            # 2. Call API
            response = self.session.get(
                self.NSE_HOLIDAY_API, headers=self.headers, timeout=10
            )
            response.raise_for_status()

            data: dict[str, Any] = response.json()

            if "CM" in data:
                holidays_data: list[dict[str, str]] = data["CM"]
                print(f"  Found {len(holidays_data)} holidays in CM segment.")

                holiday_dates: list[str] = []
                for h in holidays_data:
                    if "tradingDate" in h:
                        d_str = h["tradingDate"]
                        try:
                            d = datetime.strptime(d_str, "%d-%b-%Y")
                            holiday_dates.append(d.strftime("%Y-%m-%d"))
                        except (ValueError, TypeError):
                            continue

                return sorted(list(set(holiday_dates)))

            print("  ❌ 'CM' key not found in API response.")
            return []

        except Exception as e:
            print(f"  ❌ Error fetching holidays: {e}")
            return []

    def update_config(self) -> bool:
        """
        Update the local holiday configuration file with the latest remote data.

        Returns:
            bool: True if operation completed successfully (with or without changes).
        """
        fetched_holidays = self.fetch_nse_holidays()

        if not fetched_holidays:
            print("⚠️  No holidays fetched. Skipping update.")
            return False

        current_config: dict[str, list[str]] = {}
        if self.CONFIG_PATH.exists():
            try:
                with open(self.CONFIG_PATH, encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict):
                        current_config = content
            except (OSError, json.JSONDecodeError):
                pass

        updates_made = False
        holidays_by_year: dict[str, list[str]] = {}
        for h in fetched_holidays:
            y = h.split("-")[0]
            key = f"holidays_{y}"
            if key not in holidays_by_year:
                holidays_by_year[key] = []
            holidays_by_year[key].append(h)

        for key, dates in holidays_by_year.items():
            if key not in current_config or set(current_config[key]) != set(dates):
                current_config[key] = sorted(dates)
                updates_made = True
                print(f"  📝 Updated {key} with {len(dates)} dates.")
            else:
                print(f"  ✅ {key} is already up to date.")

        if updates_made:
            self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(current_config, f, indent=4)
            print(f"✅ Configuration saved to {self.CONFIG_PATH}")

        return True


if __name__ == "__main__":
    fetcher = HolidayFetcher()
    fetcher.update_config()
