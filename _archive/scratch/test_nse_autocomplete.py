import json
import time

import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
}

session = requests.Session()
session.headers.update(headers)


def test_autocomplete():
    try:
        print("Warming up cookies...")
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(1.0)

        # Let's try several autocomplete / search endpoints on nseindia
        # Endpoint 1: /api/search/autocomplete
        url1 = "https://www.nseindia.com/api/search/autocomplete"
        print("Testing endpoint:", url1)
        resp1 = session.get(url1, params={"q": "TCS"}, timeout=15)
        print("Status:", resp1.status_code)
        if resp1.status_code == 200:
            print("Response:", json.dumps(resp1.json(), indent=2)[:500])

        # Endpoint 2: /api/search/autocomplete?q=TCS
        # Let's also check if there is an endpoint like equity-master or some other search API

    except Exception as e:
        print("Error:", e)


test_autocomplete()
