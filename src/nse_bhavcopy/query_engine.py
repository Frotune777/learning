"""
File: src/nse_bhavcopy/query_engine.py
Purpose: DuckDB-powered query engine for EOD Parquet files.
Last Modified: 2026-05-27
"""

import logging
import os
from typing import Any

import duckdb
import pandas as pd

LOGGER = logging.getLogger(__name__)


class DuckDBQueryEngine:
    """
    DuckDB engine for running direct, zero-copy SQL queries on historical Parquet files.

    Attributes:
        data_dir (str): Directory containing EOD Parquet files.
        conn (duckdb.DuckDBPyConnection): DuckDB connection instance.

    Public Methods:
        - query(sql): Execute arbitrary SQL query against registered tables.
        - get_prices(symbol, start_date, end_date): Retrieve EOD OHLCV data.
        - get_latest_prices(): Retrieve the most recent price row for all symbols.
        - close(): Close the connection.

    Thread Safety:
        Yes — uses distinct in-memory connection instance per engine object.
    """

    def __init__(self, data_dir: str = "data/historical/1d") -> None:
        """
        Initialize the DuckDB connection and register standard views.

        Parameters:
            data_dir (str): Directory containing parquet files. | Non-empty.

        Returns:
            None

        Raises:
            FileNotFoundError: If data_dir does not exist.

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> engine = DuckDBQueryEngine(data_dir="data/historical/1d")
        """
        self.data_dir: str = data_dir
        if not os.path.exists(data_dir):
            LOGGER.warning("Data directory %s does not exist yet.", data_dir)

        # Connect to in-memory database
        self.conn: duckdb.DuckDBPyConnection = duckdb.connect(database=":memory:")
        self._register_views()

    def _register_views(self) -> None:
        """Register the prices view pointing to the parquet path."""
        # Use regexp_extract to parse symbol from the parquet file path
        # E.g. data/historical/1d/TCS.parquet -> TCS
        pattern = os.path.join(self.data_dir, "*.parquet")
        escaped_pattern = pattern.replace("'", "''")

        # We construct the SQL query to create a view
        # The filename column contains the full path of the parquet file
        sql_create_view = f"""
        CREATE OR REPLACE VIEW prices AS
        SELECT
            regexp_extract(filename, '([^/\\\\]+)\\.parquet$', 1) AS symbol,
            *
        FROM read_parquet('{escaped_pattern}', filename=True)
        """
        try:
            self.conn.execute(sql_create_view)
            LOGGER.info("Registered 'prices' view in DuckDB.")
        except Exception as exc:
            LOGGER.warning("Could not register 'prices' view: %s", exc)

    def query(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        """
        Execute an arbitrary SQL query on the registered views.

        Parameters:
            sql (str): SQL statement to execute. | Valid SQL string.
            params (list[Any] | None): Bind parameters. | Default None.

        Returns:
            pd.DataFrame: Pandas DataFrame containing query results.

        Raises:
            Exception: If query execution fails.

        Complexity:
            Time: O(N) where N is data returned by query.
            Space: O(N) for storing the pandas DataFrame.

        Example:
            >>> engine = DuckDBQueryEngine()
            >>> df = engine.query("SELECT * FROM prices LIMIT 5")
        """
        try:
            relation = self.conn.execute(sql, params)
            return relation.df()
        except Exception as exc:
            LOGGER.error("DuckDB query failed: %s\nSQL: %s", exc, sql)
            raise exc

    def get_prices(
        self,
        symbol: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Retrieve historical prices with optional filters for symbol and dates.

        Parameters:
            symbol (str | None): Filter by ticker symbol. | Default None.
            start_date (str | None): Start date 'YYYY-MM-DD'. | Default None.
            end_date (str | None): End date 'YYYY-MM-DD'. | Default None.

        Returns:
            pd.DataFrame: DataFrame containing historical price rows.

        Raises:
            None

        Complexity:
            Time: O(K) where K is number of matching rows.
            Space: O(K) for pandas DataFrame.

        Example:
            >>> engine = DuckDBQueryEngine()
            >>> df = engine.get_prices("TCS", "2026-01-01")
        """
        sql = "SELECT * FROM prices WHERE 1=1"
        params: list[Any] = []

        if symbol:
            sql += " AND symbol = ?"
            params.append(symbol.strip().upper())

        if start_date:
            sql += " AND Date >= CAST(? AS TIMESTAMP)"
            params.append(start_date)

        if end_date:
            sql += " AND Date <= CAST(? AS TIMESTAMP)"
            params.append(end_date)

        sql += " ORDER BY symbol, Date ASC"

        try:
            return self.query(sql, params)
        except Exception:
            return pd.DataFrame()

    def get_latest_prices(self) -> pd.DataFrame:
        """
        Retrieve the latest available EOD price bar for each symbol.

        Parameters:
            None

        Returns:
            pd.DataFrame: DataFrame of current EOD prices.

        Raises:
            None

        Complexity:
            Time: O(M * log T) where M is symbols, T is date length.
            Space: O(M) for return DataFrame.

        Example:
            >>> engine = DuckDBQueryEngine()
            >>> latest = engine.get_latest_prices()
        """
        sql = """
        WITH ranked AS (
            SELECT *,
                   ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY Date DESC) as rn
            FROM prices
        )
        SELECT * EXCLUDE (rn)
        FROM ranked
        WHERE rn = 1
        """
        try:
            return self.query(sql)
        except Exception:
            return pd.DataFrame()

    def close(self) -> None:
        """
        Close the DuckDB connection.

        Parameters:
            None

        Returns:
            None

        Raises:
            None

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> engine.close()
        """
        try:
            self.conn.close()
        except Exception as exc:
            LOGGER.error("Failed to close DuckDB connection: %s", exc)
