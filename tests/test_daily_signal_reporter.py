"""
File: tests/test_daily_signal_reporter.py
Purpose: Unit tests for daily_signal_reporter module.
Last Modified: 2026-05-29
"""

import os

import pandas as pd

from src.presentation.daily_signal_reporter import generate_daily_report


def test_generate_daily_report_handles_missing_files(tmp_path: str) -> None:
    """generate_daily_report works and handles missing files gracefully."""
    # No CSV files exist in tmp_path
    report = generate_daily_report(
        signals_dir=str(tmp_path), output_dir=str(tmp_path), date_str="20260529"
    )

    assert "No oversold stocks" in report
    assert "No new Bull Run Variant A candidates" in report
    assert "No active swing buy candidates" in report
    assert "No volume-confirmed Darvas Box" in report

    # Verify report was written to file
    out_file = os.path.join(str(tmp_path), "daily_20260529.txt")
    assert os.path.isfile(out_file)


def test_generate_daily_report_populates_sections(tmp_path: str) -> None:
    """Section text is correctly populated with CSV signal values."""
    date_str = "20260529"

    # Mock RSI Signals
    df_rsi = pd.DataFrame(
        [
            {
                "NSE Code": "IRFC",
                "RSI": 25.0,
                "CMP": 120.00,
                "Prev Close": 123.00,
                "AMO Price": 122.99,
                "Step Hint": "Step 2 (Average < 30)",
            }
        ]
    )
    df_rsi.to_csv(
        os.path.join(str(tmp_path), f"rsi_signals_{date_str}.csv"), index=False
    )

    # Mock DMA-DMA Signals
    df_dma = pd.DataFrame(
        [
            {
                "NSE Code": "INFY",
                "CMP": 1400.0,
                "%Diff 200 DMA": 4.5,
                "CAR": "Buy/Average Out",
            }
        ]
    )
    df_dma.to_csv(
        os.path.join(str(tmp_path), f"dma_bull_nosl_{date_str}.csv"), index=False
    )
    df_dma.to_csv(
        os.path.join(str(tmp_path), f"dma_bull_sl_{date_str}.csv"), index=False
    )

    # Mock Swing Signals
    df_swing = pd.DataFrame(
        [
            {
                "NSE Code": "RELIANCE",
                "CMP": 2400.0,
                "GTT Trigger": 2350.0,
                "GTT Target (20%)": 2820.0,
                "Swing Signal": "Start GTT",
                "Action": "Buy",
            }
        ]
    )
    df_swing.to_csv(
        os.path.join(str(tmp_path), f"swing_target_{date_str}.csv"), index=False
    )

    # Mock Darvas Signals
    df_darvas = pd.DataFrame(
        [
            {
                "NSE Code": "SBIN",
                "Signal": "Breakout (Volume Confirmed)",
                "CMP": 750.0,
                "Box High": 740.0,
                "Box Low": 710.0,
                "Box Days": 12,
            }
        ]
    )
    df_darvas.to_csv(
        os.path.join(str(tmp_path), f"darvas_signals_{date_str}.csv"), index=False
    )

    report = generate_daily_report(
        signals_dir=str(tmp_path), output_dir=str(tmp_path), date_str=date_str
    )

    assert "TODAY'S PRIMARY BUY SELECTION" in report
    assert "IRFC" in report
    assert "INFY" in report
    assert "RELIANCE" in report
    assert "SBIN" in report
    assert "Breakout (Volume Confirmed)" in report
