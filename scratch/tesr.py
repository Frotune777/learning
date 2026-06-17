"""
File: debug_index_api.py
Purpose: Debug the NSE index constituents API to see raw response.

This replicates your EXACT browser request and shows what's happening.
"""

import json
import time

import requests


def debug_index_api(index_name: str = "NIFTY 50") -> None:
    """
    Replicate the exact browser request and inspect raw response.
    """
    session = requests.Session()

    # Step 1: Visit NSE India main page (exact headers from your trace)
    print("Step 1: Visiting nseindia.com...")
    resp1 = session.get(
        "https://www.nseindia.com",
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
    print(f"  Status: {resp1.status_code}")
    print(f"  Cookies: {dict(session.cookies)}")
    time.sleep(0.5)

    # Step 2: Visit market data page (exact Referer from your trace)
    print("\nStep 2: Visiting market data page...")
    resp2 = session.get(
        "https://www.nseindia.com/market-data/live-equity-market?symbol=NIFTY%2050",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) "
                "Gecko/20100101 Firefox/150.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.nseindia.com/",
            "Connection": "keep-alive",
        },
        timeout=15,
    )
    print(f"  Status: {resp2.status_code}")
    print(f"  Cookies after: {dict(session.cookies)}")
    time.sleep(0.5)

    # Step 3: Call the API (exact headers from your trace)
    print(f"\nStep 3: Calling index API for {index_name}...")

    url = "https://www.nseindia.com/api/equity-stock-indices"
    params = {"index": index_name}

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) " "Gecko/20100101 Firefox/150.0"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://www.nseindia.com/market-data/live-equity-market?symbol=NIFTY%2050",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "TE": "trailers",
    }

    print(f"  URL: {url}")
    print(f"  Params: {params}")
    print(f"  Headers: {json.dumps(headers, indent=2)}")

    resp3 = session.get(url, params=params, headers=headers, timeout=30)

    print(f"\n  Status: {resp3.status_code}")
    print(f"  Content-Type: {resp3.headers.get('content-type', 'unknown')}")
    print(f"  Content-Length: {len(resp3.content)} bytes")
    print(f"  Content-Encoding: {resp3.headers.get('content-encoding', 'none')}")

    # Inspect raw response
    print("\n  Raw response (first 500 chars):")
    print(resp3.text[:500])

    # Try to parse JSON
    print("\n  Trying JSON parse...")
    try:
        data = resp3.json()
        print("  JSON parsed successfully!")
        print(f"  Type: {type(data).__name__}")
        if isinstance(data, dict):
            print(f"  Keys: {list(data.keys())}")
            if "data" in data:
                print(f"  Data count: {len(data['data'])}")
                if data["data"]:
                    print(
                        f"  First item: {json.dumps(data['data'][0], indent=2)[:300]}"
                    )
        return data
    except json.JSONDecodeError as e:
        print(f"  JSON ERROR: {e}")
        print("  This means the response is NOT valid JSON.")
        print("  It might be HTML, empty, or compressed incorrectly.")
        return None


if __name__ == "__main__":
    import sys

    index = sys.argv[1] if len(sys.argv) > 1 else "NIFTY 50"
    debug_index_api(index)
