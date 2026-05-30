import pandas as pd
from src.core.signal import Signal

def signals_to_dataframe(signals: list[Signal]) -> pd.DataFrame:
    """Temporary adapter until presentation layer is migrated"""
    return pd.DataFrame([
        {
            "symbol": s.symbol,
            "strategy": s.strategy_name,
            "action": s.action,
            "conviction": s.conviction,
            "score": s.weighted_score,
            **{f"meta_{k}": v for k, v in s.meta.items()}
        }
        for s in signals
    ])
