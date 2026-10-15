#!/usr/bin/env python3
"""
Data Health Monitor
Monitor data health across all caches with configurable checks
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DataHealthMonitor:
    """
    Monitor data health with configurable checks

    Features:
    - Configurable gap tolerance per timeframe
    - Duplicate detection
    - Ordering validation
    - Null value checks
    - Minimum row requirements
    - Staleness checks
    """

    def __init__(self, config_file="config/data_health_config.json"):
        self.config = self._load_config(config_file)
        logger.info("Initialized DataHealthMonitor")

    def _load_config(self, config_file: str) -> Dict:
        """Load configuration with defaults"""
        default_config = {
            "gap_tolerance": {"1d": 3, "1h": 5, "15m": 10},
            "staleness_threshold": {"1d": 2, "1h": 6, "15m": 30},
            "min_rows": {"1d": 100, "1h": 500, "15m": 1000},
        }

        config_path = Path(config_file)
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
                logger.info(f"Loaded config from {config_file}")
            except Exception as e:
                logger.warning(f"Error loading config: {e}. Using defaults.")

        return default_config

    def generate_report(self, symbols: List[str], timeframe: str = "1d") -> Dict:
        """Generate comprehensive data health report"""
        import os
        import sys

        sys.path.append(os.path.join(os.getcwd(), "src"))

        from src.data.DataRepository import DataRepository

        report = {
            "timestamp": datetime.now(),
            "timeframe": timeframe,
            "total_symbols": len(symbols),
            "status": {},
            "issues": [],
        }

        repo = DataRepository(timeframe=timeframe)

        for symbol in symbols:
            status = self._check_ohlcv(symbol, timeframe, repo)
            report["status"][symbol] = status

            if status["status"] != "OK":
                report["issues"].append(
                    {
                        "symbol": symbol,
                        "type": "OHLCV",
                        "status": status["status"],
                        "issues": status.get(
                            "issues", [status.get("issue", "Unknown")]
                        ),
                    }
                )

        return report

    def _check_ohlcv(self, symbol: str, timeframe: str, repo) -> Dict:
        """Enhanced OHLCV check with configurable tolerance"""
        data = repo.load_data(symbol)

        if data is None or data.empty:
            return {"status": "MISSING", "issue": "No data"}

        issues = []

        # Staleness check
        last_date = data.index[-1]
        staleness = self._calculate_staleness(last_date, timeframe)
        threshold = self.config["staleness_threshold"].get(timeframe, 2)

        if staleness > threshold:
            issues.append(f"Stale: {staleness} periods old")

        # Gap check
        gaps = self._find_gaps(data.index, timeframe)
        if gaps:
            issues.append(f"{len(gaps)} gaps found")

        # Duplicate check
        duplicates = data.index.duplicated().sum()
        if duplicates > 0:
            issues.append(f"{duplicates} duplicate timestamps")

        # Ordering check
        if not data.index.is_monotonic_increasing:
            issues.append("Timestamps not in order")

        # Minimum rows check
        min_rows = self.config["min_rows"].get(timeframe, 100)
        if len(data) < min_rows:
            issues.append(f"Only {len(data)} rows (need {min_rows})")

        # Data quality checks
        null_counts = data.isnull().sum()
        if null_counts.any():
            null_cols = [col for col, count in null_counts.items() if count > 0]
            issues.append(f"Null values in: {', '.join(null_cols)}")

        if issues:
            return {
                "status": "ISSUES",
                "issues": issues,
                "rows": len(data),
                "last_date": last_date,
                "staleness": staleness,
            }

        return {
            "status": "OK",
            "rows": len(data),
            "last_date": last_date,
            "staleness": staleness,
        }

    def _calculate_staleness(self, last_date: pd.Timestamp, timeframe: str) -> int:
        """Calculate staleness in periods"""
        now = pd.Timestamp.now()

        if timeframe == "1d":
            return (now - last_date).days
        elif timeframe == "1h":
            return int((now - last_date).total_seconds() / 3600)
        elif timeframe == "15m":
            return int((now - last_date).total_seconds() / 900)
        else:
            return int((now - last_date).total_seconds())

    def _find_gaps(self, dates: pd.DatetimeIndex, timeframe: str) -> List[Dict]:
        """Find gaps with configurable tolerance"""
        tolerance = self.config["gap_tolerance"].get(timeframe, 3)
        gaps = []

        for i in range(len(dates) - 1):
            diff = self._calculate_period_diff(dates[i], dates[i + 1], timeframe)

            if diff > tolerance:
                gaps.append(
                    {"from": dates[i], "to": dates[i + 1], "periods_missing": diff}
                )

        return gaps

    def _calculate_period_diff(
        self, date1: pd.Timestamp, date2: pd.Timestamp, timeframe: str
    ) -> int:
        """Calculate period difference based on timeframe"""
        if timeframe == "1d":
            return (date2 - date1).days
        elif timeframe == "1h":
            return int((date2 - date1).total_seconds() / 3600)
        elif timeframe == "15m":
            return int((date2 - date1).total_seconds() / 900)
        else:
            return int((date2 - date1).total_seconds())
