"""
File: yfinance_diagnostic.py
Purpose: Diagnose why yfinance is returning empty DataFrames and provide fixes.

This script tests multiple yfinance configurations and provides the working
solution for your environment.
"""

import ssl
import sys
import urllib.request
from datetime import datetime, timedelta

import requests

print("=" * 70)
print("YFINANCE DIAGNOSTIC TOOL")
print("=" * 70)

# Step 1: Check Python environment
print("\n[1] PYTHON ENVIRONMENT")
print(f"    Executable: {sys.executable}")
print(f"    Version: {sys.version}")

# Step 2: Check installed packages
print("\n[2] INSTALLED PACKAGES")
try:
    import yfinance

    print(f"    yfinance: {yfinance.__version__} at {yfinance.__file__}")
except ImportError:
    print("    yfinance: NOT INSTALLED")

try:
    import pandas

    print(f"    pandas: {pandas.__version__}")
except ImportError:
    print("    pandas: NOT INSTALLED")

try:
    import requests

    print(f"    requests: {requests.__version__}")
except ImportError:
    print("    requests: NOT INSTALLED")

try:
    import numpy

    print(f"    numpy: {numpy.__version__}")
except ImportError:
    print("    numpy: NOT INSTALLED")

# Step 3: Test basic connectivity to Yahoo Finance
print("\n[3] NETWORK CONNECTIVITY TEST")

try:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        "https://finance.yahoo.com/quote/TCS.NS", headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
        print(f"    Yahoo Finance HTTP Status: {response.status}")
        html = response.read().decode("utf-8")
        if "Tata Consultancy" in html or "TCS" in html:
            print("    Yahoo Finance page: ACCESSIBLE (TCS.NS found)")
        else:
            print("    Yahoo Finance page: ACCESSIBLE but TCS.NS not in response")
except Exception as e:
    print(f"    Yahoo Finance: FAILED - {type(e).__name__}: {e}")

# Step 4: Test yfinance with different approaches
print("\n[4] YFINANCE DOWNLOAD TESTS")

if "yfinance" not in sys.modules:
    print("    SKIPPED: yfinance not available")
else:
    import yfinance as yf

    # Test 4a: Basic download
    print("\n    [4a] Basic yf.download('TCS.NS', period='5d')")
    try:
        data = yf.download("TCS.NS", period="5d", progress=False)
        print(f"         Shape: {data.shape}, Empty: {data.empty}")
        if not data.empty:
            print(f"         Last close: {data['Close'].iloc[-1]}")
        else:
            print("         >>> EMPTY DATAFRAME - THIS IS THE PROBLEM <<<")
    except Exception as e:
        print(f"         ERROR: {type(e).__name__}: {e}")

    # Test 4b: With custom session
    print("\n    [4b] With custom requests.Session()")
    try:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " "AppleWebKit/537.36"
                )
            }
        )
        data = yf.download(
            "TCS.NS", period="5d", session=session, progress=False, threads=False
        )
        print(f"         Shape: {data.shape}, Empty: {data.empty}")
        if not data.empty:
            print(f"         Last close: {data['Close'].iloc[-1]}")
    except Exception as e:
        print(f"         ERROR: {type(e).__name__}: {e}")

    # Test 4c: Using Ticker.history()
    print("\n    [4c] Using yf.Ticker('TCS.NS').history()")
    try:
        t = yf.Ticker("TCS.NS")
        hist = t.history(period="5d")
        print(f"         Shape: {hist.shape}, Empty: {hist.empty}")
        if not hist.empty:
            print(f"         Last close: {hist['Close'].iloc[-1]}")
    except Exception as e:
        print(f"         ERROR: {type(e).__name__}: {e}")

    # Test 4d: With start/end dates
    print("\n    [4d] Using explicit start/end dates")
    try:
        end = datetime.now()
        start = end - timedelta(days=30)
        data = yf.download("TCS.NS", start=start, end=end, progress=False)
        print(f"         Shape: {data.shape}, Empty: {data.empty}")
    except Exception as e:
        print(f"         ERROR: {type(e).__name__}: {e}")

    # Test 4e: Test with a US stock
    print("\n    [4e] Testing with US stock AAPL")
    try:
        data = yf.download("AAPL", period="5d", progress=False)
        print(f"         Shape: {data.shape}, Empty: {data.empty}")
        if not data.empty:
            print(f"         Last close: {data['Close'].iloc[-1]}")
    except Exception as e:
        print(f"         ERROR: {type(e).__name__}: {e}")

# Step 5: Summary and recommendations
print("\n" + "=" * 70)
print("DIAGNOSIS SUMMARY")
print("=" * 70)

print("""
COMMON CAUSES OF EMPTY DATAFRAME:

1. RATE LIMITING / IP BLOCK
   Yahoo Finance blocks IPs that make too many requests.
   Solution: Wait 1-2 hours, use a different network, or add delays.

2. YFINANCE VERSION ISSUE
   Older versions (< 0.2.50) may break when Yahoo changes their API.
   Solution: pip install --upgrade yfinance

3. MISSING .NS SUFFIX
   Indian stocks need .NS suffix on Yahoo Finance.
   Correct: "TCS.NS" | Incorrect: "TCS"

4. MARKET CLOSED / NO DATA
   If the market was closed (weekend/holiday), no new data exists.
   Solution: Use period="1mo" or longer to get historical data.

5. FIREWALL / PROXY BLOCKING
   Corporate networks may block Yahoo Finance.
   Solution: Test on a different network.

6. YAHOO FINANCE API CHANGE (2025-2026)
   Yahoo has tightened anti-bot measures significantly.
   Solution: Use curl_cffi backend or alternative data sources.
""")

print("=" * 70)
print("RECOMMENDED FIXES")
print("=" * 70)

print("""
FIX 1: Upgrade yfinance (MOST COMMON FIX)
   pip install --upgrade yfinance --no-cache-dir

FIX 2: Use curl_cffi backend (BEST FOR 2025-2026)
   pip install curl_cffi
   # yfinance 0.2.50+ uses curl_cffi automatically

FIX 3: Add delays between requests
   import time
   time.sleep(2)  # between each download

FIX 4: Use a proxy/VPN if IP is blocked
   # Or wait 24 hours for rate limit to reset

FIX 5: Alternative data source
   Consider using NSE official data or Alpha Vantage API
   for more reliable Indian stock data.
""")

print("=" * 70)
