# Vendored from nse-warehouse (MIT License - Copyright (c) 2026 Siddharth Gaur)
"""Corporate-action adjustment — the part most people get silently wrong.

## Why this is inferred rather than looked up

NSE publishes a corporate-actions feed, but the endpoint sits behind the same
edge block as its quote API (403 to non-browser clients). Defeating that is out
of scope. So adjustment factors are **inferred from the price series itself**.

## The measurement that shaped the method

The obvious hope is that the bhavcopy's `PrvsClsgPric` is already adjusted, in
which case `prev_close[t] != close[t-1]` would flag an action exactly. It is
not. Checked against Reliance's 1:1 bonus, ex-date 2024-10-28:

    2024-10-25   close = 2655.70   prev_close = 2679.60
    2024-10-28   close = 1334.35   prev_close = 2655.70    <- raw prior close

`prev_close` on the ex-date is the unadjusted previous close, so it carries no
signal at all. The only usable signal is the discontinuity in the close series:
1334.35 / 2655.70 = 0.5024, i.e. a factor of 1/2.

## The method, and what it cannot do

A candidate action is a single-day close ratio that (a) lies outside a plausible
trading band and (b) sits within tolerance of a simple rational fraction. Real
splits and bonuses produce ratios like 1/2, 1/3, 2/3, 1/5, 1/10; genuine market
moves almost never land that precisely on a small fraction.

This is a heuristic. State its failure modes plainly:

* **False negative.** A 5:4 bonus (ratio 0.8) is inside the plausible trading
  band and is not flagged. Small ratios are indistinguishable from ordinary
  volatility without an external feed.
* **False positive.** A genuine ~50% single-day collapse on bad news that lands
  near 0.5 would be misread as a 1:1 bonus. Circuit limits make this rare but
  not impossible; `min_ratio_move` and `tolerance` control the trade-off.
* **Dividends are not handled at all.** Ordinary dividend drops are far too
  small to separate from noise this way. These are therefore
  *capital-adjusted*, not *total-return*, prices, and any strategy that depends
  on dividend reinvestment will be wrong. Said out loud rather than implied.

Detected actions are written to the warehouse so they can be reviewed, and any
run can be re-done with an external feed later without rebuilding the raw layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from itertools import pairwise

# Ratios a split or bonus can actually produce, as close[t] / close[t-1].
# Derived from the common corporate-action forms rather than picked by taste:
# an N:M bonus gives M/(N+M); a face-value split from A to B gives B/A.
CANDIDATE_FACTORS: tuple[Fraction, ...] = tuple(
    sorted(
        {
            Fraction(1, 2), Fraction(1, 3), Fraction(1, 4), Fraction(1, 5),
            Fraction(1, 10), Fraction(1, 20), Fraction(1, 100),
            Fraction(2, 3), Fraction(2, 5), Fraction(3, 4), Fraction(3, 5),
            Fraction(4, 5), Fraction(5, 6), Fraction(2, 7), Fraction(3, 10),
        }
    )
)


@dataclass(frozen=True)
class Action:
    symbol: str
    ex_date: date
    observed_ratio: float
    factor: float          # the simple fraction the ratio snapped to
    inferred: str          # human-readable guess, e.g. "1:1 bonus or 2-for-1 split"


def _describe(factor: Fraction) -> str:
    numerator, denominator = factor.numerator, factor.denominator
    bonus = f"{denominator - numerator}:{numerator} bonus"
    split = f"{denominator}-for-{numerator} split"
    return f"{bonus} or {split}"


def detect(
    symbol: str,
    series: list[tuple[date, float]],
    tolerance: float = 0.03,
    min_ratio_move: float = 0.20,
    max_gap_days: int = 7,
) -> list[Action]:
    """Find candidate corporate actions in one symbol's close series.

    `series` must be (date, close) sorted ascending, with no null closes.
    `min_ratio_move` is the plausible-trading band: ratios strictly within 20%
    of 1.0 are left alone, which is what makes 5:4-style small bonuses (ratio
    0.8, exactly on the boundary) borderline rather than reliably detected.

    `max_gap_days` skips pairs of observations more than a week apart. Two
    prices either side of a long gap are not a day-over-day move, and treating
    them as one manufactures splits out of nothing. This matters in two real
    situations:

    * a **suspended** stock resuming months later at a very different price, and
    * a **sampled** warehouse built from non-contiguous date ranges, where the
      seam between blocks otherwise produces ratios like 80x.

    The second was not hypothetical: it produced hundreds of spurious actions on
    the first real run of this code.
    """
    actions: list[Action] = []
    for (previous_day, previous_close), (day, close) in pairwise(series):
        if not previous_close or not close:
            continue
        if (day - previous_day).days > max_gap_days:
            continue
        ratio = close / previous_close
        if abs(ratio - 1.0) < min_ratio_move:
            continue
        for candidate in CANDIDATE_FACTORS:
            target = float(candidate)
            # Relative tolerance: a 1/100 action needs far tighter absolute
            # agreement than a 1/2 action to be believable.
            if abs(ratio - target) <= tolerance * target:
                actions.append(
                    Action(symbol, day, ratio, target, _describe(candidate))
                )
                break
    return actions


def back_adjustment_factors(
    dates: list[date], actions: list[Action]
) -> dict[date, float]:
    """Cumulative multiplier to apply to each date's raw price.

    Back-adjustment convention: the most recent price is left untouched and
    history is scaled to meet it, so the newest bar always equals what actually
    traded. Walking backwards, every bar strictly before an ex-date is
    multiplied by that action's factor.

    The alternative — forward adjustment — rewrites today's price, which breaks
    every join against anything quoting real prices. Not used.
    """
    by_ex_date = {a.ex_date: a.factor for a in actions}
    factors: dict[date, float] = {}
    running = 1.0
    for day in sorted(dates, reverse=True):
        factors[day] = running
        # A bar dated strictly before the ex-date needs this action applied, so
        # the multiplier changes as we step past the ex-date going backwards.
        if day in by_ex_date:
            running *= by_ex_date[day]
    return factors


def adjust_bar(
    factor: float,
    open_: float | None,
    high: float | None,
    low: float | None,
    close: float | None,
    volume: int | None,
) -> tuple[float | None, float | None, float | None, float | None, int | None]:
    """Apply one factor to a bar. Prices scale down; volume scales up.

    Volume must move inversely or turnover stops reconciling: after a 1:1 bonus
    there are twice as many shares, each worth half as much.
    """
    scale = lambda v: None if v is None else v * factor  # noqa: E731
    adjusted_volume = None if volume is None else int(round(volume / factor))
    return scale(open_), scale(high), scale(low), scale(close), adjusted_volume
