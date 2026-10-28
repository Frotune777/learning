"""Base contract for schema adapters."""

from abc import ABC, abstractmethod
from typing import Any
import pandas as pd


class SchemaAdapter(ABC):
    """Abstract base class for data source schema adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter name identifier."""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """Category: 'price' or 'price_and_delivery' or 'delivery_only'."""
        ...

    @abstractmethod
    def match(self, headers: list[str]) -> bool:
        """Return True if this adapter can parse the given headers.
        
        Header names should already be stripped of whitespace and uppercase.
        Match must be CONFIRMATORY, not speculative.
        """
        ...

    @abstractmethod
    def parse(
        self, df: pd.DataFrame, source_meta: dict[str, Any]
    ) -> pd.DataFrame:
        """Parse raw DataFrame into canonical representation.
        
        Required canonical columns:
            symbol, trade_date, open, high, low, close, volume, source_ref
        Optional columns:
            turnover, trades, isin, series, delivery_qty, delivery_pct
            
        Invariants:
        - trade_date: datetime.date
        - prices/volume: numeric, no NaN, close > 0
        - symbol: uppercase stripped string
        - series: filtered to EQ/BE/SZ by default
        - source_ref: from source_meta['source_key']
        """
        ...
