"""
File: src/data/fetcher/symbols/resolver.py
Purpose: Ticker-to-token mappings resolution and local cache persistence.

Dependencies:
External:
- None
Internal:
- None

Key Components:
Classes:
- SymbolResolver: Maps and saves token indexes for the charting API.
Functions:
- None

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [HIGH] Implement live search fallback for unresolved symbols

Related Files:
- src/data/fetcher/prices/nse_charts.py: Looks up mapping tokens before fetching.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


class SymbolResolver:
    """
    NSE EQUITY TICKER SYMBOL TO CHARTING TOKEN MAPPER.

    Design Pattern: Registry / Data Access Object - Resolves symbol codes
    to their unique charting tokens using localized JSON storage.

    Attributes:
        cache_path (str): Filepath for tokens cache. | Default nse_tokens.json
        tokens (dict[str, str]): Local in-memory token registry.

    Public Methods:
        - get_token(symbol): Fetch token for symbol.
        - add_token(symbol, token): Add token mapping to in-memory registry and save.

    Private Methods:
        - _load_cache(): Reads tokens from local storage.
        - _save_cache(): Writes tokens to local storage.

    Usage Flow:
        1. Instantiate SymbolResolver.
        2. Resolve symbol token by calling get_token().
        3. Register missing symbols dynamically via add_token().

    Example:
        >>> resolver = SymbolResolver(cache_path="/tmp/tokens.json")
        >>> print(resolver.get_token("RELIANCE"))
        2885

    State Management:
        - Valid states: Memory registry map synced to disk.
        - State transitions: Modifies states on add_token() executions.

    Thread Safety: Partial - File writes are synchronous but not thread-locked.

    Dependencies:
        External: None
        Internal: None
    """

    def __init__(self, cache_path: str = "data/metadata/nse_tokens.json") -> None:
        """Initialize the resolver and load cached token indexes from disk."""
        self.cache_path = cache_path
        self.tokens: dict[str, str] = {
            "RELIANCE": "2885",
            "TCS": "11536",
            "INFY": "1594",
            "ITC": "1660",
            "SBIN": "3045",
        }
        self._load_cache()

    def _load_cache(self) -> None:
        """
        LOAD PREVIOUSLY SAVED TOKEN MAPPING REGISTRY FROM STORAGE.

        Logic:
            Step 1: Check if cache file exists. If no, exit silently.
            Step 2: Read file contents and parse JSON payload.
            Step 3: Update local tokens dictionary with loaded keys.

        Parameters:
            None

        Returns:
            None

        Raises:
            None

        Example:
            >>> # Called automatically during class instantiation

        Performance:
            Time Complexity: O(M) [Loading M stored entries from disk]
            Space Complexity: O(M) [Registry memory allocation]

        Edge Cases Handled:
            - Gracefully ignores missing files and corrupted JSON structures.
        """
        if not os.path.exists(self.cache_path):
            return

        try:
            with open(self.cache_path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.tokens.update(
                        {str(k).upper(): str(v) for k, v in data.items()}
                    )
                    logger.info(
                        "Loaded %d token mappings from %s", len(data), self.cache_path
                    )
        except Exception as ex:
            logger.warning(
                "Failed to load tokens cache from %s: %s", self.cache_path, ex
            )

    def _save_cache(self) -> None:
        """
        WRITE CURRENT TOKEN REGISTRY ENTRIES TO LOCAL STORAGE.

        Logic:
            Step 1: Ensure parent folder directories exist on disk.
            Step 2: Write tokens dictionary cleanly formatted as JSON to file.

        Parameters:
            None

        Returns:
            None

        Raises:
            None

        Example:
            >>> # Called internally upon adding mappings

        Performance:
            Time Complexity: O(K) [Writing K items to disk]
            Space Complexity: O(1) [Static writing overheads]

        Edge Cases Handled:
            - Handles directory structure creation recursively.
        """
        try:
            parent = os.path.dirname(self.cache_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.tokens, f, indent=4)
        except Exception as ex:
            logger.warning("Failed to save tokens cache to %s: %s", self.cache_path, ex)

    def get_token(self, symbol: str) -> str | None:
        """
        RESOLVE A TICKER SYMBOL CODE TO ITS UNIQUE CHARTING TOKEN.

        Logic:
            Step 1: Convert symbol name to clean uppercase.
            Step 2: Lookup symbol mapping key in local memory cache dictionary.
            Step 3: Return token string if found, otherwise return None.

        Parameters:
            symbol (str): Target stock ticker. | Must be non-empty string.

        Returns:
            Optional[str]: Char mapping token if resolved.

        Raises:
            None

        Example:
            >>> resolver = SymbolResolver()
            >>> print(resolver.get_token("TCS"))
            11536

        Performance:
            Time Complexity: O(1) [Instant dictionary key lookup]
            Space Complexity: O(1) [No allocations]

        Edge Cases Handled:
            - Case-insensitive string search normalization.
            - Strip white spaces dynamically.

        TODO:
            - None

        Notes:
            None
        """
        key = symbol.strip().upper()
        return self.tokens.get(key)

    def add_token(self, symbol: str, token: str) -> None:
        """
        REGISTER AND SAVE A NEW SYMBOL MAPPING MANUALLY.

        Logic:
            Step 1: Clean and uppercase symbol and token inputs.
            Step 2: Insert into local memory cache registry.
            Step 3: Persist new updates to disk storage.

        Parameters:
            symbol (str): Target stock ticker. | Must be non-empty string.
            token (str): Associated charting index token. | String.

        Returns:
            None

        Raises:
            None

        Example:
            >>> resolver = SymbolResolver()
            >>> resolver.add_token("HDFCBANK", "1333")

        Performance:
            Time Complexity: O(K) [Synchronous write disk write out]
            Space Complexity: O(1) [No memory growths]

        Edge Cases Handled:
            - Overwrites prior assignments defensively.
        """
        key = symbol.strip().upper()
        val = token.strip()
        self.tokens[key] = val
        self._save_cache()
