import json
import sys

import requests

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://charting.nseindia.com/",
}

try:
    print("Fetching from charting.nseindia.com/Charts/GetEQMasters...")
    resp = requests.get(
        "https://charting.nseindia.com/Charts/GetEQMasters", headers=headers, timeout=30
    )
    print("Status:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        print("Data type:", type(data))
        if isinstance(data, list):
            print("Length of list:", len(data))
            if len(data) > 0:
                print("First 3 elements:")
                print(json.dumps(data[:3], indent=2))
        elif isinstance(data, dict):
            print("Keys:", list(data.keys()))
            for k in list(data.keys())[:3]:
                print(f"Key {k} type:", type(data[k]))
                if isinstance(data[k], list) and len(data[k]) > 0:
                    print(f"First element of {k}:", json.dumps(data[k][0], indent=2))
    else:
        print("Response headers:", resp.headers)
        print("Response body:", resp.text[:500])
except Exception as e:
    print("Error:", e)
