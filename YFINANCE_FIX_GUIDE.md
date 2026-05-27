# yfinance Empty DataFrame — Complete Fix Guide
## Why Your `check_yfinance.py` Is Not Working

---

## The Root Cause

Your `yf.download("TCS.NS", period="5d")` is returning an empty DataFrame because **Yahoo Finance is blocking your requests**.

This is a widespread issue since early 2025. Yahoo tightened their anti-bot measures significantly. The error typically manifests as:

```
Empty DataFrame
Columns: [Open, High, Low, Close, Adj Close, Volume]
Index: []

1 Failed download:
['TCS.NS']: JSONDecodeError('Expecting value: line 1 column 1 (char 0)')
```

Or sometimes silently with no error at all — just an empty DataFrame.

---

## Why This Happens (4 Reasons)

| Reason | What Happened | How to Check |
|--------|---------------|--------------|
| **1. Rate Limiting** | Your IP made too many requests to Yahoo | Wait 1-2 hours, try from different network |
| **2. Missing Cookies** | Yahoo now requires session cookies | Check if `requests.get("https://finance.yahoo.com")` returns 200 |
| **3. Bot Detection** | Your User-Agent flagged as scraper | Use browser-like headers + curl_cffi |
| **4. IP Blacklist** | Your IP range is permanently blocked | Try VPN or use NSE API instead |

---

## The 3 Fixes (Try in Order)

### FIX 1: Install curl_cffi (Recommended — Most Reliable)

Yahoo's bot detection specifically targets `requests` library. `curl_cffi` mimics a real browser's TLS fingerprint.

```bash
# Install curl_cffi
pip install curl_cffi

# yfinance will automatically use it if available
```

Then your existing code works:
```python
import yfinance as yf
data = yf.download("TCS.NS", period="5d")  # Should work now
```

**Why this works:** curl_cffi uses the same TLS/JA3 fingerprint as Chrome, making Yahoo think you're a real browser.

---

### FIX 2: Custom Session with Cookie Warmup

If you can't install curl_cffi, manually warm up a session:

```python
import yfinance as yf
import requests
import time

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

# CRITICAL: Visit main page first to get cookies
session.get("https://finance.yahoo.com", timeout=15)
time.sleep(1)  # Let cookies settle

# Now download with the warmed-up session
data = yf.download(
    "TCS.NS",
    period="5d",
    session=session,
    threads=False,  # Disable threading
    progress=False,
)
```

---

### FIX 3: Use NSE Official API (Ultimate Fallback)

For Indian stocks, NSE's own API is actually **more reliable** than Yahoo Finance:

```python
import requests
import pandas as pd
from datetime import datetime, timedelta

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})

# Step 1: Get cookies
session.get("https://www.nseindia.com", timeout=10)

# Step 2: Fetch data
end = datetime.now()
start = end - timedelta(days=30)

url = "https://www.nseindia.com/api/historical/cm/equity"
params = {
    "symbol": "TCS",
    "series": "[\"EQ\"]",
    "from": start.strftime("%d-%m-%Y"),
    "to": end.strftime("%d-%m-%Y"),
}

resp = session.get(url, params=params, timeout=30)
data = resp.json()

# Convert to DataFrame
df = pd.DataFrame(data["data"])
df = df.rename(columns={
    "CH_OPENING_PRICE": "Open",
    "CH_TRADE_HIGH_PRICE": "High",
    "CH_TRADE_LOW_PRICE": "Low",
    "CH_CLOSING_PRICE": "Close",
    "CH_TOT_TRADED_QTY": "Volume",
})
```

---

## Quick Diagnostic Script

Run this to identify which fix you need:

```python
import urllib.request
import ssl

# Test 1: Can you reach Yahoo Finance?
req = urllib.request.Request(
    "https://finance.yahoo.com/quote/TCS.NS",
    headers={"User-Agent": "Mozilla/5.0"}
)
ctx = ssl.create_default_context()
try:
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        print(f"✅ Yahoo Finance reachable (status: {resp.status})")
except Exception as e:
    print(f"❌ Cannot reach Yahoo Finance: {e}")

# Test 2: Is curl_cffi installed?
try:
    import curl_cffi
    print("✅ curl_cffi is installed")
except ImportError:
    print("❌ curl_cffi NOT installed — run: pip install curl_cffi")

# Test 3: Basic yfinance test
import yfinance as yf
data = yf.download("TCS.NS", period="5d", progress=False)
if data.empty:
    print("❌ yfinance returning empty — needs fix")
else:
    print(f"✅ yfinance working ({len(data)} rows)")
```

---

## What I Changed in Your Pipeline

I created **`nse_data_fetcher.py`** which implements all 3 fixes with automatic fallback:

```
Priority Order:
1. Check local cache (avoids re-downloading)
2. Try NSE Official API (best for Indian stocks)
3. Try yfinance with curl_cffi
4. Try yfinance with custom session
5. Return empty if all fail
```

Your `screener.py` now uses this instead of direct yfinance calls:

```python
# OLD (broken):
import yfinance as yf
data = yf.download("TCS.NS", period="1y")  # Often empty

# NEW (fixed):
from nse_data_fetcher import NSEDataFetcher
fetcher = NSEDataFetcher()
results = fetcher.fetch_history(["TCS", "RELIANCE"])  # Reliable
```

---

## Download the Fix Files

| File | Purpose |
|------|---------|
| **[check_yfinance_fixed.py](sandbox:///mnt/agents/output/check_yfinance_fixed.py)** | Standalone diagnostic + all 3 fixes |
| **[nse_data_fetcher.py](sandbox:///mnt/agents/output/nse_data_fetcher.py)** | Drop-in replacement for yfinance in your pipeline |
| **[screener_v2.py](sandbox:///mnt/agents/output/screener_v2.py)** | Your screener using the new fetcher |

---

## Immediate Action

```bash
# 1. Install the fix
pip install curl_cffi

# 2. Test if it works
python check_yfinance_fixed.py

# 3. If curl_cffi works, your pipeline will work too
python lerarning.py
```

If `curl_cffi` doesn't work, the script will automatically fall back to the NSE API — which **will** work for Indian stocks.
