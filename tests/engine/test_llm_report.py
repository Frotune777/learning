from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.engine.llm_report import generate_symbol_llm_dossier
from src.nse_bhavcopy.ta_indicators import add_ta_indicators


def test_llm_report_recomputes_stale_trailing_nan_ta(tmp_path: Path):
    """
    Build a dataframe with 250 rows, calculate full TA indicators, then
    append 5 rows where TA indicators are NaN (mirroring the post-sync state).
    Verify generate_symbol_llm_dossier recomputes TA indicators and section 6
    does not print 'nan' for key indicators.
    """
    n_base = 250
    dates = pd.date_range("2025-01-01", periods=n_base, freq="B")
    price = 1000.0 + np.cumsum(np.random.normal(0, 5, n_base))
    df = pd.DataFrame(
        {
            "Open": price - 2.0,
            "High": price + 5.0,
            "Low": price - 5.0,
            "Close": price,
            "Volume": 100000.0,
        },
        index=dates,
    )
    df = add_ta_indicators(df)

    # Append 5 more rows where indicator columns are present but NaN
    n_extra = 5
    extra_dates = pd.date_range(dates[-1] + pd.Timedelta(days=1), periods=n_extra, freq="B")
    extra_price = price[-1] + np.cumsum(np.random.normal(0, 5, n_extra))
    extra_df = pd.DataFrame(
        {
            "Open": extra_price - 2.0,
            "High": extra_price + 5.0,
            "Low": extra_price - 5.0,
            "Close": extra_price,
            "Volume": 120000.0,
        },
        index=extra_dates,
    )
    for col in df.columns:
        if col not in extra_df.columns:
            extra_df[col] = np.nan

    full_df = pd.concat([df, extra_df])
    # Confirm last row has NaN RSI_14 before saving
    assert pd.isna(full_df["RSI_14"].iloc[-1])

    symbol = "TESTSYM"
    tf_dir = tmp_path / "1d"
    tf_dir.mkdir(parents=True, exist_ok=True)
    full_df.to_parquet(tf_dir / f"{symbol}.parquet")

    dossier = generate_symbol_llm_dossier(symbol, hist_dir=str(tmp_path), timeframe="1d")

    # Extract lines for RSI, ADX, ATR, SMA_200
    for line in dossier.splitlines():
        if any(term in line for term in ["RSI (14):", "ADX (14):", "ATR (14):", "200 SMA:"]):
            assert "nan" not in line.lower(), f"Line contains nan: {line}"


def test_reconciliation_section_present():
    """Verify Section 7 is Lens Reconciliation and Section 8 is LLM Prompting."""
    dossier = generate_symbol_llm_dossier("TCS", hist_dir="data/historical")
    assert "## 7. Quantitative Lens Reconciliation" in dossier
    assert "## 8. Instructions for LLM Prompting / Strategy Formulation" in dossier

    # Ensure Section 7 precedes Section 8
    idx_sec7 = dossier.index("## 7. Quantitative Lens Reconciliation")
    idx_sec8 = dossier.index("## 8. Instructions for LLM Prompting / Strategy Formulation")
    assert idx_sec7 < idx_sec8


def test_reconciliation_names_disagreement():
    """Verify divergent lenses (Stage 4 + SMC Bullish) explicitly state counter-trend bounce."""
    dossier = generate_symbol_llm_dossier("TCS", hist_dir="data/historical")
    sec7_text = dossier.split("## 7. Quantitative Lens Reconciliation")[1].split("## 8. Instructions for LLM Prompting")[0]
    assert "Stage 4" in sec7_text
    assert "counter-trend" in sec7_text.lower()


def test_reconciliation_does_not_invent_signals():
    """Verify Section 7 does not invent phantom signals like accumulation/distribution/smart money."""
    dossier = generate_symbol_llm_dossier("TCS", hist_dir="data/historical")
    sec7_text = dossier.split("## 7. Quantitative Lens Reconciliation")[1].split("## 8. Instructions for LLM Prompting")[0]

    for forbidden in ["smart money", "accumulation", "distribution"]:
        assert forbidden not in sec7_text.lower(), f"Section 7 contains forbidden phrase: {forbidden}"


def test_weinstein_label_matches_parameter():
    """Verify Section 1 correctly displays 10W MA and includes the explanatory footnote."""
    dossier = generate_symbol_llm_dossier("TCS", hist_dir="data/historical")
    sec1_text = dossier.split("## 1. Executive Summary & Market Snapshot")[1].split("## 2. Actionable SMC Trading Setup")[0]

    assert "10W MA:" in sec1_text
    assert "30W MA:" not in sec1_text
    assert "Classifier uses a 10W MA, faster than Weinstein's original 30W." in sec1_text

