#!/usr/bin/env python3
"""
Smart Data Repairer
Repair data with partial fetches and audit logging
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd

from src.data.DataRepository import DataRepository
from src.data.Fetcher import Fetcher
from src.analysis.TAValidator import TAValidator

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/data_repair.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class SmartDataRepairer:
    """
    Repair data with partial fetches and audit logging

    Features:
    - Partial data fetching (only missing ranges)
    - Gap-specific repair
    - Duplicate removal
    - Timestamp ordering fix
    - Persistent audit logging
    """

    def __init__(self, log_file="logs/data_repair.log"):
        self.log_file = log_file
        self.fetcher = Fetcher()
        self.validator = TAValidator()
        logger.info("Initialized SmartDataRepairer")

    def repair_gaps(self, symbol: str, gaps: List[Dict], timeframe: str = "1d") -> Dict:
        """
        Repair gaps with partial fetches

        Args:
            symbol: Stock symbol
            gaps: List of gaps from health monitor
            timeframe: Data timeframe

        Returns:
            Repair report
        """
        repo = DataRepository(timeframe=timeframe)

        logger.info(f"Repairing {len(gaps)} gaps for {symbol} ({timeframe})")

        report = {
            "symbol": symbol,
            "timeframe": timeframe,
            "gaps_found": len(gaps),
            "gaps_repaired": 0,
            "gaps_failed": 0,
            "rows_added": 0,
            "details": [],
        }

        for gap in gaps:
            try:
                start_date = gap["from"]
                end_date = gap["to"]

                logger.info(
                    f"  Repairing gap: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                )

                # Fetch only missing range
                missing_data = self._fetch_date_range(
                    symbol, timeframe, start_date, end_date
                )

                if missing_data is not None and not missing_data.empty:
                    # Load existing data
                    existing = repo.load_data(symbol)

                    # Fix timezone issues before merging
                    if existing.index.tz is not None:
                        existing.index = existing.index.tz_localize(None)
                    if missing_data.index.tz is not None:
                        missing_data.index = missing_data.index.tz_localize(None)

                    # Merge
                    combined = pd.concat([existing, missing_data])
                    combined = combined[~combined.index.duplicated(keep="last")]
                    combined = combined.sort_index()

                    # Save
                    repo.save_data(symbol, combined)

                    rows_added = len(missing_data)
                    report["gaps_repaired"] += 1
                    report["rows_added"] += rows_added

                    logger.info(f"  ✅ Filled gap: {rows_added} rows added")

                    report["details"].append(
                        {
                            "gap": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                            "status": "SUCCESS",
                            "rows_added": rows_added,
                        }
                    )
                else:
                    # Check if this is actually a holiday/weekend
                    is_holiday = self._is_gap_holiday(start_date, end_date)

                    if is_holiday:
                        logger.info("  ℹ️  Gap is a holiday/weekend - no data expected")
                        report["details"].append(
                            {
                                "gap": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                                "status": "HOLIDAY",
                                "rows_added": 0,
                            }
                        )
                    else:
                        report["gaps_failed"] += 1
                        logger.warning(
                            "  ⚠️  No data available (NOT a known holiday - possible data issue)"
                        )

                        report["details"].append(
                            {
                                "gap": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                                "status": "NO_DATA",
                                "rows_added": 0,
                            }
                        )

            except Exception as e:
                report["gaps_failed"] += 1
                logger.error(f"  ❌ Error filling gap: {e}")

                report["details"].append(
                    {
                        "gap": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                        "status": "ERROR",
                        "error": str(e),
                    }
                )

        return report

    def _fetch_date_range(
        self,
        symbol: str,
        timeframe: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pd.DataFrame:
        """Fetch data for specific date range"""
        try:
            import yfinance as yf

            ticker = yf.Ticker(f"{symbol}.NS")
            data = ticker.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval=timeframe,
            )

            # Handle None return (happens on keyboard interrupt)
            if data is None:
                logger.warning(f"yfinance returned None for {symbol}")
                return pd.DataFrame()

            if not data.empty:
                # yfinance returns variable columns (5-7 depending on dividends/splits)
                # We only need OHLCV, so select those columns
                required_cols = ["Open", "High", "Low", "Close", "Volume"]

                # Check if all required columns exist
                if all(col in data.columns for col in required_cols):
                    # Keep only OHLCV columns
                    data = data[required_cols]

                    # Fix timezone issues - convert to timezone-naive
                    if data.index.tz is not None:
                        data.index = data.index.tz_localize(None)
                else:
                    logger.warning(f"Missing required columns for {symbol}")
                    return pd.DataFrame()

            return data

        except Exception as e:
            logger.error(f"Error fetching date range: {e}")
            return pd.DataFrame()

    def _is_gap_holiday(self, start_date: pd.Timestamp, end_date: pd.Timestamp) -> bool:
        """Check if gap is entirely holidays/weekends"""

        current = start_date + timedelta(days=1)  # Start from day after start_date

        # Check all days in the gap
        while current < end_date:
            # If any day is a trading day, gap is NOT a holiday
            if self.validator.is_trading_day(current):
                return False
            current += timedelta(days=1)

        # All days are non-trading days (holidays/weekends)
        return True

    def repair_duplicates(self, symbol: str, timeframe: str = "1d") -> Dict:
        """Remove duplicate timestamps"""
        repo = DataRepository(timeframe=timeframe)
        data = repo.load_data(symbol)

        before_count = len(data)
        duplicates = data.index.duplicated()

        report = {
            "symbol": symbol,
            "timeframe": timeframe,
            "duplicates_found": duplicates.sum(),
            "duplicates_removed": 0,
        }

        if duplicates.any():
            # Keep last occurrence
            data = data[~duplicates]
            repo.save_data(symbol, data)

            removed = before_count - len(data)
            report["duplicates_removed"] = removed

            logger.info(f"✅ Removed {removed} duplicates from {symbol} ({timeframe})")

        return report

    def repair_ordering(self, symbol: str, timeframe: str = "1d") -> Dict:
        """Fix out-of-order timestamps"""
        repo = DataRepository(timeframe=timeframe)
        data = repo.load_data(symbol)

        report = {
            "symbol": symbol,
            "timeframe": timeframe,
            "was_ordered": data.index.is_monotonic_increasing,
            "fixed": False,
        }

        if not data.index.is_monotonic_increasing:
            data = data.sort_index()
            repo.save_data(symbol, data)

            report["fixed"] = True
            logger.info(f"✅ Fixed timestamp ordering for {symbol} ({timeframe})")

        return report

    def repair_all(
        self, symbol: str, health_status: Dict, timeframe: str = "1d"
    ) -> Dict:
        """Repair all issues for a symbol"""
        logger.info(f"\n{'=' * 80}")
        logger.info(f"REPAIRING: {symbol}")
        logger.info(f"{'=' * 80}")

        overall_report = {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now(),
            "repairs": {},
        }

        # Repair duplicates
        if "duplicate" in str(health_status.get("issues", [])).lower():
            dup_report = self.repair_duplicates(symbol, timeframe)
            overall_report["repairs"]["duplicates"] = dup_report

        # Repair ordering
        if "order" in str(health_status.get("issues", [])).lower():
            order_report = self.repair_ordering(symbol, timeframe)
            overall_report["repairs"]["ordering"] = order_report

        # Repair gaps
        if health_status.get("real_gaps"):
            gap_report = self.repair_gaps(symbol, health_status["real_gaps"], timeframe)
            overall_report["repairs"]["gaps"] = gap_report

        return overall_report
