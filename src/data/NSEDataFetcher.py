"""
NSE Data Fetcher - Using Working NSE Charting API
Based on existing nse_scraper.py - proven to work!
Fetches insider trading, bulk deals, and block deals
"""

import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests


class NSEDataFetcher:
    """
    Fetch NSE data using the charting API (proven to work!)
    Much better than Selenium - faster and more reliable
    """

    def __init__(self, data_dir="user_data/nse_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()

        # NSE headers (from working scraper)
        self.headers = {
            "authority": "www.nseindia.com",
            "method": "GET",
            "scheme": "https",
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en,en-IN;q=0.9",
            "referer": "https://www.nseindia.com/",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        }

        # Initialize session
        self._init_session()

    def _init_session(self):
        """Initialize session by visiting NSE homepage"""
        try:
            self.session.get(
                "https://www.nseindia.com", headers=self.headers, timeout=10
            )
            time.sleep(1)
        except Exception as e:
            print(f"Warning: Could not initialize NSE session: {e}")

    def fetch_insider_trading(self, symbol=None, from_date=None, to_date=None):
        """
        Fetch insider trading data from NSE

        Args:
            symbol: Stock symbol (optional - if None, fetches all)
            from_date: Start date in DD-MM-YYYY format
            to_date: End date in DD-MM-YYYY format

        Returns:
            DataFrame with insider trading data
        """
        try:
            # NSE Insider Trading API
            url = "https://www.nseindia.com/api/corporates-pit"

            params = {}
            if symbol:
                params["symbol"] = symbol.upper()
            if from_date:
                params["from_date"] = from_date
            if to_date:
                params["to_date"] = to_date

            response = self.session.get(
                url, headers=self.headers, params=params, timeout=15
            )

            if response.status_code == 200:
                data = response.json()

                if "data" in data and len(data["data"]) > 0:
                    df = pd.DataFrame(data["data"])

                    # Save to file
                    filename = (
                        self.data_dir
                        / f"insider_trading_{datetime.now().strftime('%Y%m%d')}.csv"
                    )
                    df.to_csv(filename, index=False)
                    print(f"✅ Saved insider trading data: {len(df)} records")

                    return df

            print("⚠️  No insider trading data available")
            return pd.DataFrame()

        except Exception as e:
            print(f"❌ Error fetching insider trading: {e}")
            return pd.DataFrame()

    def fetch_bulk_deals(self, date=None):
        """
        Fetch bulk deals from NSE

        Args:
            date: Date in DD-MM-YYYY format (default: today)

        Returns:
            DataFrame with bulk deals
        """
        if date is None:
            date = datetime.now().strftime("%d-%m-%Y")

        try:
            # NSE Bulk Deals API
            url = "https://www.nseindia.com/api/historical/bulk-deals"
            params = {"date": date}

            response = self.session.get(
                url, headers=self.headers, params=params, timeout=15
            )

            if response.status_code == 200:
                data = response.json()

                if "data" in data and len(data["data"]) > 0:
                    df = pd.DataFrame(data["data"])

                    # Save to file
                    filename = (
                        self.data_dir
                        / f"bulk_deals_{datetime.now().strftime('%Y%m%d')}.csv"
                    )
                    df.to_csv(filename, index=False)
                    print(f"✅ Saved bulk deals: {len(df)} records")

                    return df

            print(f"⚠️  No bulk deals for {date}")
            return pd.DataFrame()

        except Exception as e:
            print(f"❌ Error fetching bulk deals: {e}")
            return pd.DataFrame()

    def fetch_block_deals(self, date=None):
        """
        Fetch block deals from NSE

        Args:
            date: Date in DD-MM-YYYY format (default: today)

        Returns:
            DataFrame with block deals
        """
        if date is None:
            date = datetime.now().strftime("%d-%m-%Y")

        try:
            # NSE Block Deals API
            url = "https://www.nseindia.com/api/historical/block-deals"
            params = {"date": date}

            response = self.session.get(
                url, headers=self.headers, params=params, timeout=15
            )

            if response.status_code == 200:
                data = response.json()

                if "data" in data and len(data["data"]) > 0:
                    df = pd.DataFrame(data["data"])

                    # Save to file
                    filename = (
                        self.data_dir
                        / f"block_deals_{datetime.now().strftime('%Y%m%d')}.csv"
                    )
                    df.to_csv(filename, index=False)
                    print(f"✅ Saved block deals: {len(df)} records")

                    return df

            print(f"⚠️  No block deals for {date}")
            return pd.DataFrame()

        except Exception as e:
            print(f"❌ Error fetching block deals: {e}")
            return pd.DataFrame()

    def download_all_data(self, days_back=7):
        """
        Download all NSE data (insider trading, bulk deals, block deals)

        Args:
            days_back: Number of days to download bulk/block deals

        Returns:
            dict with results
        """
        print("\n" + "=" * 80)
        print("DOWNLOADING NSE DATA")
        print("=" * 80 + "\n")

        results = {"insider_trading": None, "bulk_deals": [], "block_deals": []}

        # Download insider trading (all symbols)
        print("1. Fetching Insider Trading Data...")
        results["insider_trading"] = self.fetch_insider_trading()
        time.sleep(2)

        # Download bulk deals for last N days
        print(f"\n2. Fetching Bulk Deals (last {days_back} days)...")
        for i in range(days_back):
            date = (datetime.now() - timedelta(days=i)).strftime("%d-%m-%Y")
            print(f"   Day {i + 1}/{days_back}: {date}")
            df = self.fetch_bulk_deals(date)
            if not df.empty:
                results["bulk_deals"].append(df)
            time.sleep(2)

        # Download block deals for last N days
        print(f"\n3. Fetching Block Deals (last {days_back} days)...")
        for i in range(days_back):
            date = (datetime.now() - timedelta(days=i)).strftime("%d-%m-%Y")
            print(f"   Day {i + 1}/{days_back}: {date}")
            df = self.fetch_block_deals(date)
            if not df.empty:
                results["block_deals"].append(df)
            time.sleep(2)

        # Combine bulk/block deals
        if results["bulk_deals"]:
            combined_bulk = pd.concat(results["bulk_deals"], ignore_index=True)
            filename = (
                self.data_dir
                / f"bulk_deals_combined_{datetime.now().strftime('%Y%m%d')}.csv"
            )
            combined_bulk.to_csv(filename, index=False)
            print(f"\n✅ Combined bulk deals: {len(combined_bulk)} records")

        if results["block_deals"]:
            combined_block = pd.concat(results["block_deals"], ignore_index=True)
            filename = (
                self.data_dir
                / f"block_deals_combined_{datetime.now().strftime('%Y%m%d')}.csv"
            )
            combined_block.to_csv(filename, index=False)
            print(f"✅ Combined block deals: {len(combined_block)} records")

        print("\n" + "=" * 80)
        print("DOWNLOAD COMPLETE")
        print("=" * 80)
        print(f"Data saved to: {self.data_dir}")

        return results

    def query_insider_data(self, symbol, days=30):
        """Query insider data for specific symbol from downloaded CSV"""
        # Find latest file
        files = sorted(self.data_dir.glob("insider_trading_*.csv"), reverse=True)

        if not files:
            return pd.DataFrame()

        try:
            df = pd.read_csv(files[0])

            # Filter by symbol
            symbol_col = None
            for col in df.columns:
                if "symbol" in col.lower() or "company" in col.lower():
                    symbol_col = col
                    break

            if symbol_col:
                df_filtered = df[df[symbol_col].str.upper() == symbol.upper()]

                # Filter by date
                date_col = None
                for col in df.columns:
                    if "date" in col.lower():
                        date_col = col
                        break

                if date_col:
                    df_filtered[date_col] = pd.to_datetime(
                        df_filtered[date_col], errors="coerce"
                    )
                    cutoff_date = datetime.now() - timedelta(days=days)
                    df_filtered = df_filtered[df_filtered[date_col] >= cutoff_date]

                return df_filtered

            return pd.DataFrame()
        except Exception as e:
            print(f"Error querying insider data: {e}")
            return pd.DataFrame()

    def query_bulk_deals(self, symbol, days=7):
        """Query bulk deals for specific symbol"""
        files = sorted(self.data_dir.glob("bulk_deals_*.csv"), reverse=True)[:days]

        if not files:
            return pd.DataFrame()

        all_data = []
        for file in files:
            try:
                df = pd.read_csv(file)
                symbol_col = None
                for col in df.columns:
                    if "symbol" in col.lower():
                        symbol_col = col
                        break

                if symbol_col:
                    df_filtered = df[df[symbol_col].str.upper() == symbol.upper()]
                    all_data.append(df_filtered)
            except Exception:
                continue

        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()

    def query_block_deals(self, symbol, days=7):
        """Query block deals for specific symbol"""
        files = sorted(self.data_dir.glob("block_deals_*.csv"), reverse=True)[:days]

        if not files:
            return pd.DataFrame()

        all_data = []
        for file in files:
            try:
                df = pd.read_csv(file)
                symbol_col = None
                for col in df.columns:
                    if "symbol" in col.lower():
                        symbol_col = col
                        break

                if symbol_col:
                    df_filtered = df[df[symbol_col].str.upper() == symbol.upper()]
                    all_data.append(df_filtered)
            except Exception:
                continue

        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()
