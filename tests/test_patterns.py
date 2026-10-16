import pandas as pd
import pytest
from src.analysis.patterns import SMCPatterns, WilliamsFractals


def test_order_blocks_no_lookahead():
    """
    Ensure detect_order_blocks does not use future bars to confirm an OB.
    Bar 0 has a normal move (<2%). Bar 1 jumps by 10%.
    Under lookahead logic, bar 0 would be marked as Bullish OB.
    Under non-lookahead same-bar logic, bar 0 is NOT an OB.
    """
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 110.0],
            "High": [101.0, 111.0, 112.0],
            "Low": [99.5, 100.5, 109.0],
            "Close": [100.5, 110.5, 111.0],
        },
        index=[
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-01-02"),
            pd.Timestamp("2026-01-03"),
        ],
    )

    obs = SMCPatterns.detect_order_blocks(df, threshold=0.05)
    # Bar 0 (2026-01-01) must NOT be detected as an OB
    if not obs.empty:
        assert pd.Timestamp("2026-01-01") not in obs["Date"].values


def test_fvg_3bar_past_window():
    """
    Ensure detect_fvg operates strictly on 3-bar past window (i-2, i-1, i) with no shift(-1).
    Construct 3 bars that form a gap: Low[i] > High[i-2].
    """
    df_gap = pd.DataFrame(
        {
            "Open": [100.0, 105.0, 112.0],
            "High": [102.0, 110.0, 115.0],
            "Low": [99.0, 104.0, 108.0],  # Low[2] = 108 > High[0] = 102 -> Gap [102, 108]
            "Close": [101.0, 109.0, 114.0],
        },
        index=[
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-01-02"),
            pd.Timestamp("2026-01-03"),
        ],
    )
    fvgs = SMCPatterns.detect_fvg(df_gap)
    assert not fvgs.empty
    assert (fvgs["Type"] == "Bullish FVG").any()
    row = fvgs.iloc[0]
    assert row["Date"] == pd.Timestamp("2026-01-03")
    assert row["Gap_Bottom"] == 102.0
    assert row["Gap_Top"] == 108.0

    # Series where a future bar would form a gap, but past bars (i-2, i-1, i) do not
    df_no_gap = pd.DataFrame(
        {
            "Open": [100.0, 102.0, 103.0],
            "High": [105.0, 104.0, 104.0],
            "Low": [99.0, 101.0, 102.0],  # Low[2] = 102 <= High[0] = 105 -> No gap
            "Close": [101.0, 103.0, 103.5],
        },
        index=[
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-01-02"),
            pd.Timestamp("2026-01-03"),
        ],
    )
    fvgs_none = SMCPatterns.detect_fvg(df_no_gap)
    assert fvgs_none.empty


def test_williams_fractals_last_2_rows_unconfirmed():
    """
    Ensure detect_fractals places values at confirmation bar (i+2) and
    has no value in the last 2 rows because candidate peaks in the last 2 bars cannot be confirmed.
    """
    # Peak at index 2 (High = 25.0) in a 7-bar series
    df = pd.DataFrame(
        {
            "High": [10.0, 15.0, 25.0, 18.0, 12.0, 30.0, 22.0],
            "Low": [5.0, 8.0, 12.0, 10.0, 6.0, 14.0, 11.0],
        }
    )
    f_highs, f_lows = WilliamsFractals.detect_fractals(df)

    # Index 2 is confirmed at index 4 (i + 2)
    assert f_highs.iloc[4] == 25.0

    # Index 5 (High = 30.0) cannot be confirmed within 7 bars (needs index 7)
    # Index 6 (High = 22.0) cannot be confirmed within 7 bars (needs index 8)
    # Therefore, the last 2 rows (indices 5 and 6) cannot contain confirmed peaks
    assert pd.isna(f_highs.iloc[-1])
    assert pd.isna(f_highs.iloc[-2])
