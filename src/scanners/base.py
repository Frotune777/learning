from abc import ABC, abstractmethod
from typing import Any, Dict

import pandas as pd


class BaseStrategy(ABC):
    """
    Abstract Base Class for all screening strategies.
    """

    def __init__(self, config: dict[str, Any] = None):
        self.config = config or {}
        self.description = "Base Strategy"
        self.reason = ""

    def get_reason(self) -> str:
        """Return the explanation for the last analysis result."""
        return self.reason

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> bool:
        """
        Analyze the dataframe and return True if the stock passes the strategy.
        The dataframe is expected to have all necessary indicators already calculated.
        """
        pass

    def get_description(self) -> str:
        return self.description
