# test_fetcher.py — run this with: uv run python test_fetcher.py
import pandas as pd
import yfinance as yf
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

print(f"yfinance version: {yf.__version__}")

# Test 1: Raw yf.download with your exact parameters
print("\n=== TEST 1: Raw yf.download() ===")
try:
    df = yf.download(
        tickers="RELIANCE.NS TCS.NS",
        period="1y",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,  # Your current setting
    )
    print(f"Success: shape={df.shape}, empty={df.empty}")
    print(f"Columns: {df.columns.tolist()}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")

# Test 2: Same but with threads=False
print("\n=== TEST 2: threads=False ===")
try:
    df = yf.download(
        tickers="RELIANCE.NS TCS.NS",
        period="1y",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    print(f"Success: shape={df.shape}, empty={df.empty}")
    print(f"Columns: {df.columns.tolist()}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")

# Test 3: Single ticker via Ticker.history (what your fetch() uses)
print("\n=== TEST 3: Ticker.history() ===")
try:
    ticker = yf.Ticker("RELIANCE.NS")
    df = ticker.history(period="1y", interval="1d")
    print(f"Success: shape={df.shape}, empty={df.empty}")
    print(f"Columns: {df.columns.tolist()}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")

# Test 4: With actions=False
print("\n=== TEST 4: with actions=False ===")
try:
    df = yf.download(
        tickers="RELIANCE.NS TCS.NS",
        period="1y",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=False,
        actions=False,
    )
    print(f"Success: shape={df.shape}, empty={df.empty}")
    print(f"Columns: {df.columns.tolist()}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")