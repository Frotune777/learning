#!/usr/bin/env python3
"""
Historical Data Download Manager
Download and manage historical data for all stocks
"""

import os
import sys
from datetime import datetime

from src.data.DataRepository import DataRepository
from src.data.Fetcher import Fetcher
from src.ui.StockUniverseSelector import StockUniverseSelector


def download_historical_data(
    symbols=None, universe="1", period="2y", timeframes=None, force=False
):
    """Download historical data"""
    fetcher = Fetcher()

    if timeframes is None:
        timeframes = ["1d"]

    # Get symbols
    if symbols is None:
        selector = StockUniverseSelector()
        symbols = selector.get_stocks(universe)

    if not symbols:
        print("❌ No stocks found")
        return

    print("\n" + "=" * 80)
    print("HISTORICAL DATA DOWNLOAD")
    print("=" * 80)
    print(f"\nSymbols: {len(symbols)}")
    print(f"Period: {period}")
    print(f"Timeframes: {', '.join(timeframes)}")
    print(f"Force refresh: {force}")

    results = {"success": [], "skipped": [], "failed": []}

    print(f"\n{'='*80}")
    print("DOWNLOADING...")
    print(f"{'='*80}\n")

    # Import tqdm
    from tqdm import tqdm

    total_downloads = len(symbols) * len(timeframes)

    # Create main progress bar
    with tqdm(
        total=total_downloads,
        desc="🚀 Total Progress",
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
    ) as pbar:
        for symbol in symbols:
            # Update desc to show current symbol
            pbar.set_description(f"📥 {symbol:10s}")

            for tf in timeframes:
                try:
                    # Check if already exists
                    if not force:
                        repo = DataRepository(timeframe=tf)
                        existing = repo.load_data(symbol)

                        if existing is not None and not existing.empty:
                            last_date = existing.index[-1]
                            days_old = (datetime.now() - last_date).days

                            if (
                                days_old < 1
                            ):  # Only skip if less than 1 day old (e.g. same day)
                                # But we want to ensure we capture the full day candle if we ran midday
                                # So let's only skip if it's REALLY recent (like 0 days) AND market is closed?
                                # Simpler: Just allow re-download if it's 1 day old to catch final candle
                                if days_old == 0:
                                    results["skipped"].append(f"{symbol}_{tf}")
                                    pbar.update(1)
                                    continue

                            # If we are here, we might have data up to yesterday.
                            # We should fetch starting from last_date to ensure we get the latest full candle/adjustments
                            pass

                    # Download
                    data = fetcher.fetch_data(symbol, tf, period, force_refresh=force)

                    if not data.empty:
                        results["success"].append(f"{symbol}_{tf}")
                    else:
                        results["failed"].append(f"{symbol}_{tf}")

                    pbar.update(1)

                except Exception as e:
                    print(f"Error downloading {symbol}: {e}")
                    import traceback

                    traceback.print_exc()
                    results["failed"].append(f"{symbol}_{tf}")
                    pbar.update(1)

    # Summary
    print(f"\n{'='*80}")
    print("DOWNLOAD SUMMARY")
    print(f"{'='*80}\n")

    print(f"✅ Success: {len(results['success'])}/{total_downloads}")
    print(f"⏭️  Skipped: {len(results['skipped'])}/{total_downloads}")
    print(f"❌ Failed: {len(results['failed'])}/{total_downloads}")

    if results["failed"]:
        print("\nFailed downloads:")
        for item in results["failed"][:10]:
            print(f"  {item}")
        if len(results["failed"]) > 10:
            print(f"  ... and {len(results['failed']) - 10} more")

    print(f"\n{'='*80}\n")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Historical Data Download Manager")
    parser.add_argument(
        "--universe",
        "-u",
        default="1",
        help="Stock universe (1=Nifty50, 2=Nifty100, etc.)",
    )
    parser.add_argument(
        "--symbols", "-s", nargs="+", help="Specific symbols to download"
    )
    parser.add_argument("--period", "-p", default="2y", help="Period (1y, 2y, 5y, max)")
    parser.add_argument(
        "--timeframes", "-t", nargs="+", default=["1d"], help="Timeframes (1d, 1h, 15m)"
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force refresh (re-download existing data)",
    )

    args = parser.parse_args()

    download_historical_data(
        symbols=args.symbols,
        universe=args.universe,
        period=args.period,
        timeframes=args.timeframes,
        force=args.force,
    )
