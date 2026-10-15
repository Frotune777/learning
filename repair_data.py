#!/usr/bin/env python3
"""
Professional Data Repair Tool with Progress Bars
Shows exactly what's being fixed with ETAs
"""

import argparse

from tqdm import tqdm

from src.analysis.SmartDataRepairer import SmartDataRepairer
from src.data.DataHealthCheck import DataHealthCheck
from src.ui.StockUniverseSelector import StockUniverseSelector


def repair_data(universe="1", timeframe="1d", dry_run=False, interactive=True):
    """Repair data with professional progress bars"""

    print("\n" + "=" * 80)
    print("🔧 PROFESSIONAL DATA REPAIR TOOL")
    print("=" * 80)

    # Get stocks
    selector = StockUniverseSelector()
    stocks = selector.get_stocks(universe)

    if not stocks:
        print("❌ No stocks found!")
        return

    print(f"\n📊 Checking {len(stocks)} stocks for issues...")

    # Initialize
    monitor = DataHealthCheck()
    repairer = SmartDataRepairer()

    # Phase 1: Scan for issues
    print("\n" + "=" * 80)
    print("PHASE 1: SCANNING FOR ISSUES")
    print("=" * 80 + "\n")

    print("Running DataHealthCheck scan...")
    report = monitor.get_raw_data_health()

    issues_found = {}

    available_data = set(report["details"].keys())
    selected_targets = set(stocks).intersection(available_data)

    print(f"Analyzing {len(selected_targets)} relevant stocks...")

    for symbol in selected_targets:
        if symbol in report["details"]:
            data = report["details"][symbol]
            if data["status"] == "ISSUES":
                issues_found[symbol] = {
                    "status": "ISSUES",
                    "real_gaps": data.get("gaps", []),
                    "issues": [],  # compat with old logic
                }
                if data.get("gaps"):
                    issues_found[symbol]["issues"].append(f"{len(data['gaps'])} gaps")

    if not issues_found:
        print("\n✅ No issues found! All data is healthy.\n")
        return

    print(f"\n⚠️  Found issues in {len(issues_found)} stocks")

    # Count issue types
    gaps = sum(1 for h in issues_found.values() if h.get("real_gaps"))

    print(f"   - {gaps} stocks with data gaps")

    if dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made")
        print("\nIssues that would be fixed:")
        for symbol, health in list(issues_found.items())[:10]:
            print(f"  • {symbol}: {', '.join(health.get('issues', [])[:2])}")
        if len(issues_found) > 10:
            print(f"  ... and {len(issues_found) - 10} more")
        return

    # Phase 2: Repair
    print("\n" + "=" * 80)
    print("PHASE 2: REPAIRING ISSUES")
    print("=" * 80 + "\n")

    total_repaired = 0
    total_rows_added = 0

    with tqdm(
        issues_found.items(),
        desc="🔧 Repairing",
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
    ) as pbar:
        for symbol, health in pbar:
            pbar.set_description(f"🔧 Repairing {symbol:12s}")

            # Repair gaps
            if health.get("real_gaps"):
                report = repairer.repair_gaps(symbol, health["real_gaps"], "1d")
                total_repaired += report["gaps_repaired"]
                total_rows_added += report["rows_added"]

            # Repair duplicates
            if "duplicate" in str(health.get("issues", [])).lower():
                repairer.repair_duplicates(symbol, "1d")

            # Repair ordering
            if "order" in str(health.get("issues", [])).lower():
                repairer.repair_ordering(symbol, "1d")

    # Summary
    print("\n" + "=" * 80)
    print("✅ REPAIR COMPLETE")
    print("=" * 80)
    print(f"\nRepaired {total_repaired} gaps across {len(issues_found)} stocks")
    print(f"Added {total_rows_added} rows of data")
    print("\n" + "=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Professional Data Repair Tool")
    parser.add_argument("--universe", "-u", default="1", help="Stock universe")
    parser.add_argument(
        "--dry-run", "-d", action="store_true", help="Preview without making changes"
    )

    args = parser.parse_args()

    repair_data(universe=args.universe, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
