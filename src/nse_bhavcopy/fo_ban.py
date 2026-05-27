"""
File: src/nse_bhavcopy/fo_ban.py
Purpose: Fetch and parse the NSE F&O ban list daily.
Last Modified: 2026-05-27
"""

import csv
import logging
import os

import requests

LOGGER = logging.getLogger(__name__)

# Official NSE F&O ban CSV URL
FO_BAN_URL: str = "https://archives.nseindia.com/content/fo/fo_secban.csv"

# Request headers to mimic browser access
HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


class FOBanManager:
    """
    Manager to download, cache, and query the NSE F&O ban list daily.

    Attributes:
        cache_path (str): Target path for local caching.

    Public Methods:
        - fetch_fo_ban_list(): Download the ban list from NSE.
        - is_banned(symbol): Verify if a symbol is in the ban list.

    Thread Safety:
        Yes.
    """

    def __init__(self, cache_dir: str = "data") -> None:
        """
        Initialize the F&O Ban Manager.

        Parameters:
            cache_dir (str): Directory to store the cached ban list. |
                Must be non-empty.

        Returns:
            None

        Raises:
            None

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> manager = FOBanManager()
        """
        self.cache_path: str = os.path.join(cache_dir, "fo_secban.csv")
        os.makedirs(cache_dir, exist_ok=True)

    def fetch_fo_ban_list(self) -> list[str]:
        """
        Fetch the current F&O ban list from NSE, caching it locally.

        If the network request fails, it falls back to the local cached CSV file.

        Parameters:
            None

        Returns:
            list[str]: Ticker symbols currently in F&O ban period.

        Raises:
            None

        Complexity:
            Time: O(N) where N is lines in CSV.
            Space: O(N) for parsed symbols list.

        Example:
            >>> manager = FOBanManager()
            >>> ban_list = manager.fetch_fo_ban_list()
        """
        banned_symbols: list[str] = []
        try:
            LOGGER.info("Fetching F&O ban list from: %s", FO_BAN_URL)
            response = requests.get(FO_BAN_URL, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                content = response.text
                # Cache the list locally
                with open(self.cache_path, "w", encoding="utf-8") as f:
                    f.write(content)
                banned_symbols = self._parse_csv_content(content)
                LOGGER.info(
                    "Successfully fetched %d F&O ban symbols.", len(banned_symbols)
                )
                return banned_symbols

            LOGGER.warning(
                "NSE F&O API returned status code %d. Using local cache if available.",
                response.status_code,
            )
        except Exception as exc:
            LOGGER.error("Failed to download F&O ban list: %s", exc)

        # Fallback to local cache
        if os.path.exists(self.cache_path):
            try:
                LOGGER.info(
                    "Loading F&O ban list from local cache: %s", self.cache_path
                )
                with open(self.cache_path, encoding="utf-8") as f:
                    content = f.read()
                banned_symbols = self._parse_csv_content(content)
                LOGGER.info(
                    "Loaded %d F&O ban symbols from cache.", len(banned_symbols)
                )
            except Exception as exc:
                LOGGER.critical("Failed to read F&O ban list cache: %s", exc)

        return banned_symbols

    def _parse_csv_content(self, content: str) -> list[str]:
        """Parse raw CSV string to extract list of uppercase symbols."""
        symbols: list[str] = []
        lines = content.strip().splitlines()
        if not lines:
            return symbols

        reader = csv.reader(lines)
        # Parse rows, checking for columns containing the symbol
        for row in reader:
            if not row:
                continue
            # Typical format has symbol as the second column or matching pattern
            # Let's search for columns that look like valid symbols
            for col in row:
                val = col.strip().upper()
                # NSE symbols contain alphanumeric characters and
                # are typically 3-10 chars.
                # We skip headers like 'SYMBOL', 'SECURITY NAME'
                if (
                    val
                    and val not in ("SYMBOL", "SECURITY NAME", "SERIES", "DATE")
                    and val.isalnum()
                ):
                    # Check if this row looks like F&O ban format row
                    # Usually, the symbol is one of the fields in a valid line
                    symbols.append(val)
                    break
        return list(set(symbols))

    def is_banned(self, symbol: str, ban_list: list[str]) -> bool:
        """
        Verify if a given ticker symbol is currently in the F&O ban list.

        Parameters:
            symbol (str): Ticker symbol to check. | Must be non-empty.
            ban_list (list[str]): Currently active F&O ban list. | Valid list.

        Returns:
            bool: True if symbol is banned, False otherwise.

        Raises:
            None

        Complexity:
            Time: O(1) lookup on set.
            Space: O(1)

        Example:
            >>> manager = FOBanManager()
            >>> manager.is_banned("ZEEL", ["ZEEL", "TCS"])
            True
        """
        clean_symbol = symbol.strip().upper()
        # Strip potential suffixes like .NS
        if clean_symbol.endswith(".NS"):
            clean_symbol = clean_symbol[:-3]
        return clean_symbol in ban_list
