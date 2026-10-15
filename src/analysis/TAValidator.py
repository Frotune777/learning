#!/usr/bin/env python3
"""
TA Validation System
Validates that incremental TA calculations match full calculations
Accounts for market holidays and weekends
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TAValidator:
    """
    Validate TA indicator calculations

    Features:
    - Compare incremental vs full calculation
    - Tolerance-based validation
    - Holiday/weekend awareness
    - Detailed error reporting
    """

    def __init__(self, tolerance=0.01):
        """
        Args:
            tolerance: Acceptable difference percentage (default 1%)
        """
        self.tolerance = tolerance
        self.nse_holidays = self._load_nse_holidays()

    def validate_indicators(
        self, symbol: str, incremental: Dict, full: Dict, verbose: bool = True
    ) -> Dict:
        """
        Validate incremental indicators against full calculation

        Args:
            symbol: Stock symbol
            incremental: Indicators from incremental calculation
            full: Indicators from full calculation
            verbose: Show detailed comparison

        Returns:
            Validation report with exact numerical comparisons
        """
        report = {
            "symbol": symbol,
            "timestamp": datetime.now(),
            "passed": True,
            "total_fields_checked": 0,
            "total_differences": 0,
            "max_difference_pct": 0.0,
            "indicators": {},
        }

        # Validate each indicator
        for indicator in ["supertrend", "obv", "rsi", "macd", "bollinger", "vwap"]:
            if indicator in incremental and indicator in full:
                result = self._validate_indicator_detailed(
                    indicator, incremental[indicator], full[indicator], verbose
                )
                report["indicators"][indicator] = result
                report["total_fields_checked"] += result["fields_checked"]
                report["total_differences"] += len(result["differences"])

                if result["max_diff_pct"] > report["max_difference_pct"]:
                    report["max_difference_pct"] = result["max_diff_pct"]

                if not result["passed"]:
                    report["passed"] = False

        return report

    def _validate_indicator_detailed(
        self, name: str, incremental: Dict, full: Dict, verbose: bool
    ) -> Dict:
        """Validate single indicator with detailed comparison"""
        result = {
            "name": name,
            "passed": True,
            "fields_checked": 0,
            "max_diff_pct": 0.0,
            "differences": [],
            "comparisons": [],
        }

        # Compare key values
        for key in incremental.keys():
            if key in full:
                inc_val = incremental[key]
                full_val = full[key]

                # Skip non-numeric values
                if not isinstance(inc_val, (int, float, np.number)):
                    continue

                result["fields_checked"] += 1

                # Calculate exact difference
                abs_diff = abs(inc_val - full_val)

                if full_val != 0:
                    diff_pct = abs((inc_val - full_val) / full_val) * 100
                else:
                    diff_pct = abs_diff * 100  # For zero values

                # Track max difference
                if diff_pct > result["max_diff_pct"]:
                    result["max_diff_pct"] = diff_pct

                # Store comparison
                comparison = {
                    "field": key,
                    "incremental": float(inc_val),
                    "full": float(full_val),
                    "abs_diff": float(abs_diff),
                    "diff_pct": float(diff_pct),
                    "within_tolerance": diff_pct <= self.tolerance,
                }
                result["comparisons"].append(comparison)

                # Check tolerance
                if diff_pct > self.tolerance:
                    result["passed"] = False
                    result["differences"].append(comparison)

        return result

    def print_validation_report(self, report: Dict):
        """Print detailed validation report"""
        print("\n" + "=" * 80)
        print(f"VALIDATION REPORT: {report['symbol']}")
        print("=" * 80)
        print(f"Timestamp: {report['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Overall Status: {'✅ PASSED' if report['passed'] else '❌ FAILED'}")
        print(f"Fields Checked: {report['total_fields_checked']}")
        print(f"Max Difference: {report['max_difference_pct']:.6f}%")
        print(f"Tolerance: {self.tolerance}%")

        if report["total_differences"] > 0:
            print(f"\n⚠️  Differences Found: {report['total_differences']}")

        print("\n" + "-" * 80)
        print("INDICATOR-BY-INDICATOR VALIDATION")
        print("-" * 80)

        for ind_name, ind_result in report["indicators"].items():
            status = "✅ PASS" if ind_result["passed"] else "❌ FAIL"
            print(f"\n{ind_name.upper()}: {status}")
            print(f"  Fields Checked: {ind_result['fields_checked']}")
            print(f"  Max Difference: {ind_result['max_diff_pct']:.6f}%")

            # Show all comparisons
            if ind_result["comparisons"]:
                print("\n  Field-by-Field Comparison:")
                for comp in ind_result["comparisons"]:
                    status_icon = "✅" if comp["within_tolerance"] else "❌"
                    print(
                        f"    {status_icon} {comp['field']:15s}: "
                        f"Inc={comp['incremental']:12.6f}, "
                        f"Full={comp['full']:12.6f}, "
                        f"Diff={comp['abs_diff']:10.6f} ({comp['diff_pct']:.6f}%)"
                    )

            # Show differences if any
            if ind_result["differences"]:
                print("\n  ⚠️  DIFFERENCES EXCEEDING TOLERANCE:")
                for diff in ind_result["differences"]:
                    print(f"    ❌ {diff['field']}: {diff['diff_pct']:.6f}% difference")
                    print(f"       Incremental: {diff['incremental']:.10f}")
                    print(f"       Full:        {diff['full']:.10f}")
                    print(f"       Abs Diff:    {diff['abs_diff']:.10f}")

        print("\n" + "=" * 80)

    def _load_nse_holidays(self) -> List[datetime]:
        """Load NSE holiday calendar from config/holidays.json"""
        import json
        from pathlib import Path

        try:
            # Try to locate config file relative to project root
            # Assuming CWD is project root
            config_path = Path("config/holidays.json")

            if config_path.exists():
                with open(config_path, "r") as f:
                    config = json.load(f)
                    holidays = config.get("holidays_2026", [])
                    return [pd.to_datetime(d) for d in holidays]
            else:
                # Fallback to hardcoded list if config missing (fail-safe)
                return self._get_fallback_holidays()
        except Exception as e:
            logger.error(f"Error loading holidays: {e}")
            return self._get_fallback_holidays()

    def _get_fallback_holidays(self):
        """Fallback hardcoded holidays"""
        holidays_2026 = [
            "2026-01-26",
            "2026-03-14",
            "2026-03-30",
            "2026-04-02",
            "2026-04-10",
            "2026-04-21",
            "2026-05-01",
            "2026-06-29",
            "2026-08-15",
            "2026-08-16",
            "2026-09-02",
            "2026-10-02",
            "2026-10-20",
            "2026-10-27",
            "2026-10-28",
            "2026-11-16",
            "2026-12-25",
        ]
        return [pd.to_datetime(d) for d in holidays_2026]

    def is_trading_day(self, date: pd.Timestamp) -> bool:
        """Check if date is a trading day (not weekend/holiday)"""
        # Weekend check
        if date.dayofweek >= 5:  # Saturday=5, Sunday=6
            return False

        # Holiday check
        date_only = date.normalize()
        if date_only in self.nse_holidays:
            return False

        return True

    def get_expected_trading_days(
        self, start_date: pd.Timestamp, end_date: pd.Timestamp
    ) -> int:
        """Calculate expected number of trading days between dates"""
        current = start_date
        count = 0

        while current <= end_date:
            if self.is_trading_day(current):
                count += 1
            current += timedelta(days=1)

        return count

    def find_real_gaps(self, dates: pd.DatetimeIndex) -> List[Dict]:
        """
        Find real data gaps (excluding weekends/holidays)

        Returns:
            List of gaps with expected vs actual trading days
        """
        gaps = []

        for i in range(len(dates) - 1):
            start = dates[i]
            end = dates[i + 1]

            # Calculate expected trading days
            expected_days = self.get_expected_trading_days(
                start + timedelta(days=1), end - timedelta(days=1)
            )

            # If we expect trading days but have none, it's a gap
            if expected_days > 0:
                gaps.append(
                    {
                        "from": start,
                        "to": end,
                        "expected_trading_days": expected_days,
                        "calendar_days": (end - start).days,
                    }
                )

        return gaps


class EnhancedDataHealthMonitor:
    """Enhanced data health monitor with holiday awareness"""

    def __init__(self, config_file="config/data_health_config.json"):
        from src.data.DataHealthMonitor import DataHealthMonitor

        self.base_monitor = DataHealthMonitor(config_file)
        self.validator = TAValidator()
        logger.info("Initialized EnhancedDataHealthMonitor with holiday awareness")

    def check_data_with_holidays(self, symbol: str, timeframe: str = "1d") -> Dict:
        """Check data health accounting for holidays"""
        from src.data.DataRepository import DataRepository

        repo = DataRepository(timeframe=timeframe)
        data = repo.load_data(symbol)

        if data is None or data.empty:
            return {"status": "MISSING", "issue": "No data"}

        issues = []

        # Check staleness (accounting for holidays)
        last_date = data.index[-1]
        today = pd.Timestamp.now().normalize()

        # Count expected trading days since last data
        expected_days = self.validator.get_expected_trading_days(
            last_date + timedelta(days=1), today
        )

        if expected_days > 1:  # Allow 1 day lag
            issues.append(f"Missing {expected_days} trading days")

        # Find real gaps (excluding weekends/holidays)
        real_gaps = self.validator.find_real_gaps(data.index)
        if real_gaps:
            issues.append(f"{len(real_gaps)} real gaps (excluding holidays)")

        # Duplicate check
        duplicates = data.index.duplicated().sum()
        if duplicates > 0:
            issues.append(f"{duplicates} duplicate timestamps")

        # Ordering check
        if not data.index.is_monotonic_increasing:
            issues.append("Timestamps not in order")

        if issues:
            return {
                "status": "ISSUES",
                "issues": issues,
                "rows": len(data),
                "last_date": last_date,
                "real_gaps": real_gaps,
            }

        return {
            "status": "OK",
            "rows": len(data),
            "last_date": last_date,
            "expected_days_lag": expected_days,
        }

    def validate_ta_calculation(self, symbol: str) -> Dict:
        """Validate TA calculations for a symbol"""
        from src.analysis.IncrementalIndicatorCalculator import (
            IncrementalIndicatorCalculator,
        )
        from src.data.Fetcher import Fetcher

        fetcher = Fetcher()
        calculator = IncrementalIndicatorCalculator()

        # Fetch data
        data = fetcher.fetch_data(symbol, "1d", "1y")

        if data is None or data.empty:
            return {"status": "NO_DATA", "symbol": symbol}

        # Get incremental calculation
        incremental = calculator.get_indicators(symbol, data)

        # Force full calculation
        full = calculator._calculate_full(data)

        # Validate
        validation = self.validator.validate_indicators(symbol, incremental, full)

        return validation
