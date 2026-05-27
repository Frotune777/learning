"""
File: scratch/check_yfinance_fixed.py
Purpose: FIXED version of yfinance data acquisition with multiple fallback strategies.

This script demonstrates the working solutions for yfinance empty DataFrame issues:
1. Using curl_cffi backend (most reliable in 2025-2026)
2. Using custom session with proper headers
3. Using NSE official API as ultimate fallback

Last Modified: 2026-05-27
"""

import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("yfinance_fix")


def check_yf_curl_cffi() -> None:
    """
    FIX 1: Use curl_cffi backend (most reliable for 2025-2026)

    yfinance 0.2.50+ supports curl_cffi which bypasses Yahoo's bot detection.
    Install: pip install curl_cffi
    """
    print("\n=== FIX 1: curl_cffi Backend ===")
    try:
        import yfinance as yf

        print(f"yfinance version: {yf.__version__}")

        # curl_cffi is used automatically if installed
        data = yf.download("TCS.NS", period="5d", progress=False, threads=False)

        if data.empty:
            print("FAILED: Still empty with curl_cffi")
        else:
            print(f"SUCCESS: {len(data)} rows fetched")
            print(data)
            return True
    except ImportError:
        print("curl_cffi not installed. Run: pip install curl_cffi")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
    return False


def check_yf_custom_session() -> None:
    """
    FIX 2: Custom session with browser-like headers and cookies

    Yahoo Finance blocks requests without proper cookies/session.
    We first visit the main page to get cookies, then fetch data.
    """
    print("\n=== FIX 2: Custom Session with Cookies ===")
    try:
        import yfinance as yf

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;" "q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
            }
        )

        # Step 1: Get cookies from Yahoo Finance main page
        print("Fetching cookies from Yahoo Finance...")
        resp = session.get("https://finance.yahoo.com", timeout=15)
        print(f"Main page status: {resp.status_code}")
        time.sleep(1)

        # Step 2: Now download with the session
        data = yf.download(
            "TCS.NS",
            period="5d",
            session=session,
            progress=False,
            threads=False,
            timeout=30,
        )

        if data.empty:
            print("FAILED: Still empty with custom session")
        else:
            print(f"SUCCESS: {len(data)} rows fetched")
            print(data)
            return True

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
    return False


def check_nse_api() -> pd.DataFrame:
    """
    FIX 3: NSE Official API (most reliable for Indian stocks)

    When yfinance fails completely, use NSE's own historical data API.
    This is the ULTIMATE fallback for Indian stocks.
    """
    print("\n=== FIX 3: NSE Official API ===")

    symbol = "TCS"
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    try:
        # Step 1: Get cookies from NSE main page
        print("Fetching cookies from NSE India...")
        resp = session.get("https://www.nseindia.com", timeout=10)
        print(f"NSE main page status: {resp.status_code}")
        time.sleep(0.5)

        # Step 2: Fetch historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        url = "https://www.nseindia.com/api/historical/cm/equity"
        params = {
            "symbol": symbol,
            "series": '["EQ"]',
            "from": start_date.strftime("%d-%m-%Y"),
            "to": end_date.strftime("%d-%m-%Y"),
        }

        print(f"Fetching data for {symbol}...")
        resp = session.get(url, params=params, timeout=30)
        print(f"API status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                df = pd.DataFrame(data["data"])
                df = df.rename(
                    columns={
                        "CH_OPENING_PRICE": "Open",
                        "CH_TRADE_HIGH_PRICE": "High",
                        "CH_TRADE_LOW_PRICE": "Low",
                        "CH_CLOSING_PRICE": "Close",
                        "CH_TOT_TRADED_QTY": "Volume",
                        "CH_TIMESTAMP": "Date",
                    }
                )
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.set_index("Date").sort_index()

                for col in ["Open", "High", "Low", "Close", "Volume"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

                print(f"SUCCESS: {len(df)} rows from NSE API")
                print(df.tail())
                return df
            else:
                print("FAILED: NSE API returned empty data")
        else:
            print(f"FAILED: NSE API returned status {resp.status_code}")

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

    return pd.DataFrame()


def main() -> None:
    """
    Run all fixes in order of preference.
    Stops at the first successful method.
    """
    print("=" * 70)
    print("YFINANCE FIX TESTER")
    print("=" * 70)
    print("\nThis script tries multiple methods to fetch TCS.NS data:")
    print("1. curl_cffi backend (best for 2025-2026)")
    print("2. Custom session with cookies")
    print("3. NSE Official API (ultimate fallback)")
    print("=" * 70)

    # Try Fix 1
    if check_yf_curl_cffi():
        print("\n✅ RECOMMENDED: Use curl_cffi backend")
        print("   Install: pip install curl_cffi")
        return

    # Try Fix 2
    if check_yf_custom_session():
        print("\n✅ WORKAROUND: Use custom session with cookie warmup")
        return

    # Try Fix 3
    df = check_nse_api()
    if not df.empty:
        print("\n✅ FALLBACK: Use NSE Official API for Indian stocks")
        print("   This is the most reliable source for NSE data")
        return

    print("\n❌ ALL METHODS FAILED")
    print("   Possible causes:")
    print("   - Your IP is rate-limited by Yahoo/NSE")
    print("   - Network firewall blocking financial APIs")
    print("   - Corporate proxy interfering with HTTPS")
    print("\n   Solutions:")
    print("   - Wait 1-2 hours and retry")
    print("   - Use a different network (mobile hotspot)")
    print("   - Use a VPN with Indian exit node")
    print("   - Contact your network admin about firewall rules")


if __name__ == "__main__":
    main()
