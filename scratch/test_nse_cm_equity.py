import time
from datetime import datetime

import requests

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/report-detail/eq_wind_sec",
}

session = requests.Session()
session.headers.update(headers)


def test_cm_equity():
    try:
        print("Warming up cookies...")
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1.0)

        # Query for TCS from 01-01-2000 to 27-05-2026
        # Note: the NSE API might limit the number of days per request (e.g., max 1 year or 2 years per query).
        # Let's test a 1-year request first, and a 20-year request next.

        print("Testing 1 year request...")
        url = "https://www.nseindia.com/api/historical/cm/equity"
        params = {
            "symbol": "TCS",
            "series": '["EQ"]',
            "from": "01-01-2025",
            "to": "27-05-2026",
        }

        resp = session.get(url, params=params, timeout=15)
        print("1 Year Status:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            records = data.get("data", [])
            print("Records returned:", len(records))
            if records:
                print("First record:", records[0])
                print("Last record:", records[-1])
        else:
            print("Response:", resp.text[:500])

        time.sleep(1.0)
        print("\nTesting 20-year request...")
        params_long = {
            "symbol": "TCS",
            "series": '["EQ"]',
            "from": "01-01-2000",
            "to": "27-05-2026",
        }
        resp = session.get(url, params=params_long, timeout=15)
        print("Long Query Status:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            records = data.get("data", [])
            print("Records returned:", len(records))
        else:
            print("Response:", resp.text[:500])

    except Exception as e:
        print("Error:", e)


test_cm_equity()
