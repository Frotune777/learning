"""
File: src/data/fetcher/prices/base.py
Purpose: Abstract base class definition for market price data acquisition.

Dependencies:
External:
- pandas>=2.2.3: Data structuring and mapping operations
Internal:
- None

Key Components:
Classes:
- AbstractPriceFetcher: Base class enforcing implementation of the fetch signature.
Functions:
- None

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [LOW] Integrate support for order book depth fetches

Related Files:
- src/data/fetcher/prices/nse_charts.py: Main subclass implementation.
- src/data/fetcher/prices/yfinance_fetcher.py: YFinance subclass implementation.
"""

from abc import ABC, abstractmethod

import pandas as pd


class AbstractPriceFetcher(ABC):
    """
    ABSTRACT BASE CLASS ENFORCING COMMON PRICE GETTERS INTERFACES.

    Design Pattern: Template Method / Strategy - Standardizes the interface
    for retrieving historical price series.

    Attributes:
        None

    Public Methods:
        - fetch(symbol, timeframe, period, from_date, to_date): Enforce download logic.
        - fetch_batch(symbols, ...): Batch download with default loop implementation.

    Private Methods:
        None

    Usage Flow:
        1. Subclass AbstractPriceFetcher.
        2. Implement the abstract fetch method.
        3. Call fetch on the instance to get OHLCV data.

    Example:
        >>> # Inherit and implement fetch in subclass
        >>> class MockFetcher(AbstractPriceFetcher):
        ...     def fetch(self, s, tf="1d", p="1y", fd=None, td=None) -> pd.DataFrame:
        ...         return pd.DataFrame()

    State Management:
        - Valid states: Stateless interfaces.
        - State transitions: None.

    Thread Safety: Yes - Stateless base class interfaces are safe.

    Dependencies:
        External: pandas
        Internal: None
    """

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1y",
        from_date: int | None = None,
        to_date: int | None = None,
    ) -> pd.DataFrame:
        """
        ENFORCE IMPLEMENTATION OF HISTORICAL PRICE SERIES RETRIEVAL.

        Logic:
            Step 1: Parse provided timescale values.
            Step 2: Fetch raw prices from the target vendor endpoint.
            Step 3: Normalize to a standard indexed pandas DataFrame.

        Parameters:
            symbol (str): Target ticker code. | Must be non-empty string.
            timeframe (str): Price aggregate interval. | Default '1d'.
            period (str): Total history scope length. | Default '1y'.
            from_date (Optional[int]): Start epoch time. | Default None.
            to_date (Optional[int]): End epoch time. | Default None.

        Returns:
            pd.DataFrame: Normalized OHLCV price series.

        Raises:
            NotImplementedError: Raised when method is not overridden.

        Example:
            >>> # Implemented by active provider subclasses

        Performance:
            Time Complexity: O(N) [Depends on subclasses]
            Space Complexity: O(N) [Depends on subclasses]

        Edge Cases Handled:
            - Handled in subclass implementation.

        TODO:
            - None

        Notes:
            None
        """
        raise NotImplementedError

    def fetch_batch(
        self,
        symbols: list[str],
        timeframe: str = "1d",
        period: str = "1y",
        from_date: int | None = None,
        to_date: int | None = None,
    ) -> pd.DataFrame:
        """
        DEFAULT BATCH IMPLEMENTATION: LOOP OVER FETCH() PER SYMBOL.

        Parameters:
            symbols (list[str]): Target ticker codes. | Non-empty list.
            timeframe (str): Price aggregate interval. | Default '1d'.
            period (str): Total history scope length. | Default '1y'.
            from_date (Optional[int]): Start epoch time. | Default None.
            to_date (Optional[int]): End epoch time. | Default None.

        Returns:
            pd.DataFrame: Combined OHLCV with MultiIndex columns (symbol, metric).

        Raises:
            None
        """
        dfs: list[pd.DataFrame] = []
        for sym in symbols:
            df = self.fetch(
                sym,
                timeframe=timeframe,
                period=period,
                from_date=from_date,
                to_date=to_date,
            )
            if not df.empty:
                df.columns = pd.MultiIndex.from_product([[sym], df.columns])
                dfs.append(df)
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, axis=1)
