"""
File: test_nse_charting.py
Purpose: Test the exact NSE Charting API endpoint from browser network trace.

This script replicates the exact request from your Firefox network trace:
  GET https://charting.nseindia.com/v1/charts/symbolHistoricalData
  with the exact headers and cookies.

Usage:
    python test_nse_charting.py
"""

import json
import time
from datetime import datetime, timedelta

import requests


def test_nse_charting(symbol: str = "TCS") -> None:
    """
    Replicate the exact browser request to NSE Charting API.
    """
    session = requests.Session()

    # Step 1: Visit charting page to get cookies
    print("Step 1: Getting cookies from charting.nseindia.com...")
    resp = session.get(
        "https://charting.nseindia.com/",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) "
                "Gecko/20100101 Firefox/150.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        },
        timeout=15,
    )
    print(f"  Status: {resp.status_code}")
    print(f"  Cookies: {dict(session.cookies)}")
    time.sleep(0.5)

    # Step 2: Visit symbol page
    print(f"\nStep 2: Visiting symbol page for {symbol}...")
    resp2 = session.get(
        f"https://charting.nseindia.com/?symbol={symbol}-EQ",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) "
                "Gecko/20100101 Firefox/150.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://charting.nseindia.com/",
        },
        timeout=15,
    )
    print(f"  Status: {resp2.status_code}")
    print(f"  Cookies after symbol page: {dict(session.cookies)}")
    time.sleep(0.5)

    # Step 3: Call the API
    print(f"\nStep 3: Calling API for {symbol}...")

    to_date = int(datetime.now().timestamp())
    from_date = int((datetime.now() - timedelta(days=30)).timestamp())

    url = "https://charting.nseindia.com/v1/charts/symbolHistoricalData"
    params = {
        "token": "11536",
        "fromDate": str(from_date),
        "toDate": str(to_date),
        "symbol": f"{symbol}-EQ",
        "symbolType": "Equity",
        "chartType": "I",
        "timeInterval": "1",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) " "Gecko/20100101 Firefox/150.0"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": f"https://charting.nseindia.com/?symbol={symbol}-EQ",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    print(f"  URL: {url}")
    print(f"  Params: {params}")

    resp3 = session.get(url, params=params, headers=headers, timeout=30)

    print(f"\n  Status: {resp3.status_code}")
    print(f"  Content-Type: {resp3.headers.get('content-type', 'unknown')}")
    print(f"  Content-Length: {len(resp3.content)} bytes")

    if resp3.status_code == 200:
        try:
            data = resp3.json()
            print(f"\n  Response type: {type(data).__name__}")

            if isinstance(data, dict):
                print(f"  Top-level keys: {list(data.keys())}")

                # Show first key's structure
                for key, val in data.items():
                    print(f"\n  Key '{key}':")
                    print(f"    Type: {type(val).__name__}")
                    if isinstance(val, list) and val:
                        print(f"    Length: {len(val)}")
                        print(f"    First item type: {type(val[0]).__name__}")
                        if isinstance(val[0], dict):
                            print(f"    First item keys: {list(val[0].keys())}")
                            print(
                                f"    First item: {json.dumps(val[0], indent=2)[:500]}"
                            )
                    elif isinstance(val, dict):
                        print(f"    Sub-keys: {list(val.keys())}")
                    break  # Only show first key

            elif isinstance(data, list):
                print(f"  Length: {len(data)}")
                if data:
                    print(f"  First item type: {type(data[0]).__name__}")
                    if isinstance(data[0], dict):
                        print(f"  First item keys: {list(data[0].keys())}")
                        print(f"  First item: {json.dumps(data[0], indent=2)[:500]}")

            # Save raw response for inspection
            with open(f"nse_charting_response_{symbol}.json", "w") as f:
                json.dump(data, f, indent=2)
            print(f"\n  Saved full response to: nse_charting_response_{symbol}.json")

        except json.JSONDecodeError as e:
            print(f"\n  JSON decode error: {e}")
            print(f"  Raw response (first 1000 chars):")
            print(resp3.text[:1000])
    else:
        print(f"\n  Error response (first 500 chars):")
        print(resp3.text[:500])


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "TCS"
    test_nse_charting(symbol)
