import time

import requests

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(headers)


def test_api():
    try:
        print("Warming up cookies...")
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1.0)

        print("Fetching index constituents for NIFTY 50...")
        resp = session.get(
            "https://www.nseindia.com/api/equity-stock-indices?index=NIFTY%2050",
            timeout=15,
        )
        print("Index Status:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "data" in data and len(data["data"]) > 0:
                first_item = data["data"][0]
                print("Index constituent fields:")
                for k, v in first_item.items():
                    print(f"  {k}: {v}")

                # Check for token or identifier
                meta = first_item.get("meta", {})
                if meta:
                    print("Index constituent meta:")
                    for k, v in meta.items():
                        print(f"    {k}: {v}")

        time.sleep(1.0)
        print("\nFetching quote for TCS...")
        resp = session.get(
            "https://www.nseindia.com/api/quote-equity?symbol=TCS", timeout=15
        )
        print("Quote Status:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            print("Quote keys:", list(data.keys()))
            for key in ["info", "metadata", "securityInfo", "sddDetails"]:
                if key in data:
                    print(f"Quote {key}:")
                    for k, v in data[key].items():
                        print(f"  {k}: {v}")
    except Exception as e:
        print("Error:", e)


test_api()
