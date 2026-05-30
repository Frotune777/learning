from dataclasses import dataclass
from typing import Literal
from datetime import datetime

@dataclass(frozen=True, slots=True)
class Signal:
    symbol: str
    strategy_name: str
    action: Literal[-1, 0, 1]  # -1=SELL, 0=HOLD, 1=BUY
    conviction: float          # 0.0 to 1.0
    timestamp: datetime
    meta: dict                 # strategy-specific data
    
    def __post_init__(self):
        if not -1 <= self.action <= 1:
            raise ValueError(f"action must be -1, 0, or 1, got {self.action}")
        if not 0.0 <= self.conviction <= 1.0:
            raise ValueError(f"conviction must be 0.0-1.0, got {self.conviction}")
    
    def is_buy(self) -> bool:
        return self.action == 1
    
    def is_sell(self) -> bool:
        return self.action == -1
    
    @property
    def weighted_score(self) -> float:
        return self.action * self.conviction
