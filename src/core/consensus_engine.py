from collections import defaultdict

from src.core.signal import Signal


def aggregate_signals(signals: list[Signal]) -> dict[str, float]:
    """
    Returns {symbol: consensus_score} where:
    -1.0 = unanimous sell, 0.0 = neutral, +1.0 = unanimous buy
    """
    scores: defaultdict[str, list[float]] = defaultdict(list)

    for sig in signals:
        scores[sig.symbol].append(sig.weighted_score)

    return {
        symbol: sum(vals) / len(vals)
        for symbol, vals in scores.items()
        if vals  # skip empty
    }


def get_consensus_recommendation(score: float) -> str:
    if score > 0.3:
        return "STRONG_BUY"
    elif score > 0.1:
        return "BUY"
    elif score < -0.3:
        return "STRONG_SELL"
    elif score < -0.1:
        return "SELL"
    else:
        return "HOLD"
