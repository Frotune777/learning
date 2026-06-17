import time

import requests


def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/"
    }

    session = requests.Session()
    session.headers.update(headers)

    try:
        # Step 1: Prime session cookies via the working subpage
        print("Visiting pre-open page...")
        r1 = session.get("https://www.nseindia.com/market-data/pre-open-market-cm-and-emerge-market", timeout=10)
        print(f"Pre-open page status: {r1.status_code}")
        print("Cookies gathered:", list(session.cookies.keys()))

        time.sleep(0.5)

        # Step 2: Fetch index data
        print("\nQuerying API...")
        r3 = session.get("https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050", timeout=10)
        print(f"API status code: {r3.status_code}")
        if r3.status_code == 200:
            print("Successfully fetched!")
            print(r3.text[:300])
        else:
            print("Failed. Content:")
            print(r3.text[:300])

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
