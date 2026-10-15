import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pandas as pd

from src.data.PersistenceService import PersistenceService


class DataHealthCheck:
    """
    Data Completeness & Health Check
    --------------------------------
    Analyzes the state of:
    1. Raw Data (Parquet): Latest dates, gaps, NaNs.
    2. Screening Results (TA/ML): Completeness of latest scan.
    3. Analysis Cache: Freshness of cached analysis.
    """

    def __init__(self):
        self.DATA_DIR = Path("user_data/parquet/1d")
        self.RESULTS_FILE = PersistenceService.PERSISTENCE_FILE
        self.CACHE_DB = Path("analysis_cache.db")
        self.nse_holidays = self._load_nse_holidays()

    def _load_nse_holidays(self):
        """Load NSE holiday calendar from config/holidays.json"""
        import json

        try:
            config_path = Path("config/holidays.json")
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                    holidays = config.get("holidays_2026", [])
                    return [pd.to_datetime(d) for d in holidays]
            else:
                print(
                    "⚠️  Warning: config/holidays.json not found. Using empty holiday list."
                )
                return []
        except Exception as e:
            print(f"⚠️  Error loading holidays: {e}")
            return []

    def is_trading_day(self, date: pd.Timestamp) -> bool:
        """Check if date is a trading day (not weekend/holiday)"""
        if date.dayofweek >= 5:  # Saturday=5, Sunday=6
            return False
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

    def find_real_gaps(self, dates: pd.DatetimeIndex):
        """Find real data gaps (excluding weekends/holidays)"""
        gaps = []
        for i in range(len(dates) - 1):
            start = dates[i]
            end = dates[i + 1]
            # Calculate expected trading days between start+1 and end-1
            expected_days = self.get_expected_trading_days(
                start + timedelta(days=1), end - timedelta(days=1)
            )
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

    def get_raw_data_health(self):
        """Get raw data health status as a dictionary"""
        files = list(self.DATA_DIR.glob("*.parquet"))
        if not files:
            return {
                "status": "NO_FILES",
                "total_files": 0,
                "latest_date": None,
                "outdated_stocks": [],
                "missing_values": 0,
                "total_gaps": 0,
                "stocks_with_gaps": [],
                "details": {},
            }

        def process_file(fpath):
            try:
                df = pd.read_parquet(fpath)
                if df.empty:
                    return {"symbol": fpath.stem, "status": "EMPTY"}

                # Check NaNs
                nans = df.isna().sum().sum()

                # Check Gaps
                real_gaps = self.find_real_gaps(df.index)

                return {
                    "symbol": fpath.stem,
                    "status": "OK" if nans == 0 and not real_gaps else "ISSUES",
                    "last_date": df.index.max(),
                    "rows": len(df),
                    "nans": nans,
                    "gaps": real_gaps,
                }
            except Exception as e:
                return {"symbol": fpath.stem, "status": "ERROR", "error": str(e)}

        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_file, files))

        results = [r for r in results if r is not None]

        # Aggregate
        report = {
            "status": "OK",
            "total_files": len(files),
            "latest_date": None,
            "outdated_stocks": [],
            "missing_values": 0,
            "total_gaps": 0,
            "stocks_with_gaps": [],  # List of detailed objects
            "details": {r["symbol"]: r for r in results},
        }

        if not results:
            return report

        # 1. Latest Date
        valid_dates = [r["last_date"] for r in results if "last_date" in r]
        if valid_dates:
            mode_date = pd.Series(valid_dates).mode()[0]
            report["latest_date"] = mode_date

            for r in results:
                if "last_date" in r and r["last_date"] < mode_date:
                    report["outdated_stocks"].append(r["symbol"])

        # 2. NaNs
        report["missing_values"] = sum(r.get("nans", 0) for r in results)

        # 3. Gaps
        for r in results:
            if r.get("gaps"):
                report["total_gaps"] += len(r["gaps"])
                report["stocks_with_gaps"].append(r)

        if (
            report["outdated_stocks"]
            or report["missing_values"] > 0
            or report["total_gaps"] > 0
        ):
            report["status"] = "ISSUES"

        return report

    def check_raw_data_health(self):
        """Print raw data health report"""
        print(f"\n{'=' * 20} RAW DATA HEALTH (OHLCV) {'=' * 20}")

        report = self.get_raw_data_health()

        if report["status"] == "NO_FILES":
            print("❌ No parquet files found.")
            return

        print(f"Found {report['total_files']} stock files.")

        # Latest Date
        if report["latest_date"]:
            print(f"\n📅 Latest Data Date: {report['latest_date']}")

            if report["outdated_stocks"]:
                print(f"⚠️  {len(report['outdated_stocks'])} stocks outdated.")
            else:
                print("✅ All stocks up to date.")

        # NaNs
        if report["missing_values"] > 0:
            print(f"\n📉 Missing Values (NaNs): {report['missing_values']} found.")
        else:
            print("\n✅ Zero NaNs (missing values) in data.")

        # Gaps
        print("\n🔍 Gap Analysis (Business Days):")

        if report["total_gaps"] == 0:
            print("✅ No gaps found! (Checking against Indian Holidays)")
        else:
            print(
                f"⚠️  Found {report['total_gaps']} gaps across {len(report['stocks_with_gaps'])} stocks."
            )
            print("Top stocks with gaps:")
            for item in report["stocks_with_gaps"][:5]:
                print(f"  - {item['symbol']}: {len(item['gaps'])} gaps")
                first_gap = item["gaps"][0]
                print(
                    f"    Sample Gap: {first_gap['from'].date()} -> {first_gap['to'].date()} "
                    f"({first_gap['expected_trading_days']} missing trading days)"
                )

    def check_screening_results(self):
        print(f"\n{'=' * 20} SCREENING RESULTS (TA/ML) {'=' * 20}")
        if not self.RESULTS_FILE.exists():
            print(f"❌ {self.RESULTS_FILE} not found. No recent screening results.")
            return

        try:
            df = pd.read_parquet(self.RESULTS_FILE)
            print(f"Loaded results for {len(df)} stocks.")

            # Check for NaNs/Blanks in TA/ML columns
            # Assuming all columns except 'Stock' (index) are relevant

            nan_counts = df.isna().sum()
            empty_counts = (df == "").sum()

            summary = pd.DataFrame({"NaNs": nan_counts, "EmptyStrings": empty_counts})
            summary = summary[(summary["NaNs"] > 0) | (summary["EmptyStrings"] > 0)]

            if not summary.empty:
                print("\n⚠️  Some TA/ML columns have missing data:")
                print(summary)
            else:
                print("✅ No missing values in screening results.")

        except Exception as e:
            print(f"❌ Error reading screening results: {e}")

    def check_analysis_cache(self):
        print(f"\n{'=' * 20} ANALYSIS CACHE {'=' * 20}")
        if not self.CACHE_DB.exists():
            print("❌ Analysis cache DB not found.")
            return

        try:
            conn = sqlite3.connect(self.CACHE_DB)
            cursor = conn.cursor()

            # Check table
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_cache'"
            )
            if not cursor.fetchone():
                print("❌ 'analysis_cache' table not found in DB.")
                return

            # Count rows
            cursor.execute("SELECT COUNT(*) FROM analysis_cache")
            count = cursor.fetchone()[0]
            print(f"📦 Cached Analysis Entries: {count}")

            # Check freshness
            cursor.execute("PRAGMA table_info(analysis_cache)")
            columns = [info[1] for info in cursor.fetchall()]

            if "timestamp" in columns or "date" in columns:
                col = "timestamp" if "timestamp" in columns else "date"
                cursor.execute(f"SELECT MAX({col}) FROM analysis_cache")
                latest = cursor.fetchone()[0]
                print(f"   🕒 Latest Cache Entry: {latest}")

        except Exception as e:
            print(f"❌ Error inspecting cache: {e}")
        finally:
            if conn:
                conn.close()

    def generate_report(self):
        self.check_raw_data_health()
        self.check_screening_results()
        self.check_analysis_cache()
        print("\n" + "=" * 60 + "\n")
