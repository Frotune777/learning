"""
File: src/engine/lux_volume_profile.py
Purpose: Structure-based Volume Profile (POC, VAH, VAL) ported from LuxAlgo Pine Script v6.
Features:
  - Calculates horizontal Volume Distribution across user-defined price bins.
  - Identifies Point of Control (POC - highest traded volume node).
  - Determines Value Area (VAH & VAL) containing 70% of volume.
  - High performance calculation via Polars and NumPy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import polars as pl


@dataclass
class VolumeProfileBin:
    price_low: float
    price_high: float
    price_mid: float
    volume: float
    is_poc: bool = False
    in_value_area: bool = False


@dataclass
class VolumeProfileResult:
    poc_price: float
    vah_price: float
    val_price: float
    total_volume: float
    bins: list[VolumeProfileBin] = field(default_factory=list)
    df: pl.DataFrame | None = None


def calculate_volume_profile(
    data: pl.DataFrame | pd.DataFrame,
    lookback: int = 120,
    rows: int = 30,
    va_percent: float = 70.0,
) -> VolumeProfileResult:
    """
    Compute Structure Volume Profile for the lookback window.

    Parameters:
        data: DataFrame containing 'high', 'low', 'close', 'volume'.
        lookback: Number of recent candles to profile (default 120).
        rows: Number of horizontal price histogram bins (default 30).
        va_percent: Target percentage of volume for Value Area (default 70.0%).

    Returns:
        VolumeProfileResult with POC, VAH, VAL, and price-bin distribution.
    """
    if isinstance(data, pd.DataFrame):
        p_df = pl.from_pandas(data)
    else:
        p_df = data

    cols = {c.lower(): c for c in p_df.columns}
    for req in ("high", "low", "close"):
        if req not in cols:
            raise ValueError(f"Input DataFrame must contain '{req}' column.")

    vol_col = cols.get("volume", None)

    tail_df = p_df.tail(lookback)
    highs = tail_df[cols["high"]].to_numpy().astype(float)
    lows = tail_df[cols["low"]].to_numpy().astype(float)
    closes = tail_df[cols["close"]].to_numpy().astype(float)

    if vol_col and vol_col in tail_df.columns:
        volumes = tail_df[vol_col].to_numpy().astype(float)
    else:
        volumes = np.ones(len(closes), dtype=float)

    n = len(closes)
    if n == 0:
        return VolumeProfileResult(poc_price=0.0, vah_price=0.0, val_price=0.0, total_volume=0.0)

    p_min = float(np.min(lows))
    p_max = float(np.max(highs))

    if p_min >= p_max:
        return VolumeProfileResult(poc_price=p_min, vah_price=p_min, val_price=p_min, total_volume=float(np.sum(volumes)))

    # Construct price bins
    bin_edges = np.linspace(p_min, p_max, rows + 1)
    bin_vols = np.zeros(rows, dtype=float)

    # Distribute bar volume across the price range it traversed
    for i in range(n):
        b_low, b_high, b_vol = lows[i], highs[i], volumes[i]
        if b_high <= b_low:
            idx = min(rows - 1, max(0, int((b_low - p_min) / (p_max - p_min) * rows)))
            bin_vols[idx] += b_vol
            continue

        # Overlapping bins
        for r in range(rows):
            r_low = bin_edges[r]
            r_high = bin_edges[r + 1]
            # Calculate overlap length
            overlap = max(0.0, min(b_high, r_high) - max(b_low, r_low))
            if overlap > 0:
                fraction = overlap / (b_high - b_low)
                bin_vols[r] += b_vol * fraction

    # Identify POC (Point of Control)
    poc_idx = int(np.argmax(bin_vols))
    poc_price = 0.5 * (bin_edges[poc_idx] + bin_edges[poc_idx + 1])
    total_vol = float(np.sum(bin_vols))

    # Identify Value Area (70% total volume radiating from POC)
    target_va_vol = total_vol * (va_percent / 100.0)
    curr_va_vol = bin_vols[poc_idx]
    in_va = np.zeros(rows, dtype=bool)
    in_va[poc_idx] = True

    up_idx = poc_idx + 1
    dn_idx = poc_idx - 1

    while curr_va_vol < target_va_vol and (up_idx < rows or dn_idx >= 0):
        up_vol = bin_vols[up_idx] if up_idx < rows else -1.0
        dn_vol = bin_vols[dn_idx] if dn_idx >= 0 else -1.0

        if up_vol >= dn_vol and up_idx < rows:
            curr_va_vol += up_vol
            in_va[up_idx] = True
            up_idx += 1
        elif dn_idx >= 0:
            curr_va_vol += dn_vol
            in_va[dn_idx] = True
            dn_idx -= 1
        else:
            break

    va_indices = np.where(in_va)[0]
    val_price = bin_edges[va_indices[0]]
    vah_price = bin_edges[va_indices[-1] + 1]

    # Build detailed bin list
    bins_list = []
    for r in range(rows):
        mid = 0.5 * (bin_edges[r] + bin_edges[r + 1])
        bins_list.append(
            VolumeProfileBin(
                price_low=round(bin_edges[r], 2),
                price_high=round(bin_edges[r + 1], 2),
                price_mid=round(mid, 2),
                volume=round(bin_vols[r], 2),
                is_poc=(r == poc_idx),
                in_value_area=bool(in_va[r]),
            )
        )

    # Annotated dataframe column with POC, VAH, VAL
    res_df = p_df.with_columns(
        [
            pl.lit(round(poc_price, 2)).alias("vp_poc"),
            pl.lit(round(vah_price, 2)).alias("vp_vah"),
            pl.lit(round(val_price, 2)).alias("vp_val"),
        ]
    )

    return VolumeProfileResult(
        poc_price=round(poc_price, 2),
        vah_price=round(vah_price, 2),
        val_price=round(val_price, 2),
        total_volume=round(total_vol, 2),
        bins=bins_list,
        df=res_df,
    )
