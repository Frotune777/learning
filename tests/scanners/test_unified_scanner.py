import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd

from src.core.signal import Signal
from src.scanners.unified_scanner import (
    SCANNER_GROUPS,
    compile_signals_to_dataframe,
    get_display_name_for_strategy,
    get_group_for_strategy,
    run_unified_scanner,
)


class TestUnifiedScanner(unittest.TestCase):
    def setUp(self):
        # Create some sample Signal objects
        self.now = datetime.now()
        self.signal_minervini = Signal(
            symbol="RELIANCE",
            strategy_name="minervini_screener",
            action=1,
            conviction=0.85,
            timestamp=self.now,
            meta={"template_score": 9, "rs_rating": 85.5, "stage2": True, "rvol": 1.5},
        )
        self.signal_darvas = Signal(
            symbol="TCS",
            strategy_name="darvas_box",
            action=1,
            conviction=1.0,
            timestamp=self.now,
            meta={"raw_signal": "Breakout (Volume Confirmed)", "box_high": 150.0, "box_low": 140.0, "box_days": 10},
        )
        self.signal_squeeze = Signal(
            symbol="^NSEI",
            strategy_name="momentum_squeeze",
            action=1,
            conviction=0.5,
            timestamp=self.now,
            meta={"close": 22000.0, "momentum": 5.4, "squeeze_on": True, "raw_signal": "SQUEEZE | ↑ Bullish"},
        )
        self.signal_rsi = Signal(
            symbol="INFY",
            strategy_name="rsi_scanner",
            action=1,
            conviction=0.8,
            timestamp=self.now,
            meta={"rsi_value": 28.5, "cmp": 1600.0, "step_hint": "Step 2 (Average < 30)", "in_nifty50": True},
        )
        self.signal_pair = Signal(
            symbol="SBIN",
            strategy_name="pair_scanner",
            action=-1,
            conviction=0.6,
            timestamp=self.now,
            meta={"pair_symbol": "BANKBARODA", "trade_type": "SELL A / BUY B", "z_score": 2.15},
        )
        self.signal_etf = Signal(
            symbol="GOLDBEES",
            strategy_name="etf_screener",
            action=1,
            conviction=0.9,
            timestamp=self.now,
            meta={"category": "GOLD", "underlying": "Gold Prices", "weight": 5000000.0, "cmp": 60.5},
        )

    def test_get_group_for_strategy(self):
        self.assertEqual(get_group_for_strategy("minervini_screener"), "Bull Trend")
        self.assertEqual(get_group_for_strategy("darvas_box"), "Bull Trend")
        self.assertEqual(get_group_for_strategy("momentum_squeeze"), "Momentum")
        self.assertEqual(get_group_for_strategy("rsi_scanner"), "Mean Reversion")
        self.assertEqual(get_group_for_strategy("pair_scanner"), "Mean Reversion")
        self.assertEqual(get_group_for_strategy("etf_screener"), "Asset Allocation")
        self.assertEqual(get_group_for_strategy("unknown_strategy"), "Other")

    def test_get_display_name_for_strategy(self):
        self.assertEqual(get_display_name_for_strategy("minervini_screener"), "Mark Minervini Template")
        self.assertEqual(get_display_name_for_strategy("darvas_box"), "Darvas Box Breakout")
        self.assertEqual(get_display_name_for_strategy("momentum_squeeze"), "Momentum Squeeze")
        self.assertEqual(get_display_name_for_strategy("rsi_scanner"), "RSI Oversold (<35)")
        self.assertEqual(get_display_name_for_strategy("pair_scanner"), "Cointegration Pair Spread")
        self.assertEqual(get_display_name_for_strategy("etf_screener"), "Liquid ETF Screener")
        self.assertEqual(get_display_name_for_strategy("unknown_strategy"), "unknown_strategy")

    def test_compile_signals_to_dataframe(self):
        signals = [
            self.signal_minervini,
            self.signal_darvas,
            self.signal_squeeze,
            self.signal_rsi,
            self.signal_pair,
            self.signal_etf,
        ]
        df = compile_signals_to_dataframe(signals)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 6)
        
        # Verify columns exist
        expected_cols = ["Symbol", "Scanner Group", "Strategy", "Direction", "Conviction", "Details", "Timestamp"]
        self.assertTrue(all(col in df.columns for col in expected_cols))

        # Check values
        self.assertEqual(df.loc[df["Symbol"] == "RELIANCE", "Scanner Group"].values[0], "Bull Trend")
        self.assertEqual(df.loc[df["Symbol"] == "RELIANCE", "Direction"].values[0], "BUY")
        self.assertEqual(df.loc[df["Symbol"] == "RELIANCE", "Conviction"].values[0], "85%")
        self.assertIn("Score: 9/9", df.loc[df["Symbol"] == "RELIANCE", "Details"].values[0])

        self.assertEqual(df.loc[df["Symbol"] == "SBIN", "Direction"].values[0], "SELL")
        self.assertIn("BANKBARODA", df.loc[df["Symbol"] == "SBIN", "Details"].values[0])

    @patch("src.scanners.unified_scanner.get_latest_analyzed_csv")
    @patch("src.scanners.unified_scanner.run_minervini_cli")
    @patch("src.scanners.unified_scanner.scan_darvas_breakouts")
    @patch("src.scanners.unified_scanner.run_squeeze_cli")
    @patch("src.scanners.unified_scanner.scan_rsi_signals")
    @patch("src.scanners.unified_scanner.run_pair_scanner_cli")
    @patch("src.scanners.unified_scanner.run_liquid_etf_screener")
    @patch("pandas.read_csv")
    def test_run_unified_scanner_all(
        self,
        mock_read_csv,
        mock_etf,
        mock_pair,
        mock_rsi,
        mock_squeeze,
        mock_darvas,
        mock_minervini,
        mock_csv,
    ):
        mock_csv.return_value = "dummy.csv"
        mock_read_csv.return_value = pd.DataFrame({"SYMBOL": ["TCS"]})
        mock_minervini.return_value = [self.signal_minervini]
        mock_darvas.return_value = [self.signal_darvas]
        mock_squeeze.return_value = [self.signal_squeeze]
        mock_rsi.return_value = [self.signal_rsi]
        mock_pair.return_value = [self.signal_pair]
        mock_etf.return_value = [self.signal_etf]

        # Call under test
        signals = run_unified_scanner("All")

        self.assertEqual(len(signals), 10)  # 1 (minervini) + 1 (darvas) + 5 (squeeze) + 1 (rsi) + 1 (pair) + 1 (etf)
        mock_minervini.assert_called_once()
        mock_darvas.assert_called_once()
        self.assertEqual(mock_squeeze.call_count, 5)  # 5 symbols tested for squeeze
        mock_rsi.assert_called_once()
        mock_pair.assert_called_once()
        mock_etf.assert_called_once()

    @patch("src.scanners.unified_scanner.get_latest_analyzed_csv")
    @patch("src.scanners.unified_scanner.run_minervini_cli")
    @patch("src.scanners.unified_scanner.scan_darvas_breakouts")
    @patch("pandas.read_csv")
    def test_run_unified_scanner_bull_trend(
        self,
        mock_read_csv,
        mock_darvas,
        mock_minervini,
        mock_csv,
    ):
        mock_csv.return_value = "dummy.csv"
        mock_read_csv.return_value = pd.DataFrame({"SYMBOL": ["TCS"]})
        mock_minervini.return_value = [self.signal_minervini]
        mock_darvas.return_value = [self.signal_darvas]

        # Call under test
        signals = run_unified_scanner("Bull Trend")

        self.assertEqual(len(signals), 2)
        mock_minervini.assert_called_once()
        mock_darvas.assert_called_once()

