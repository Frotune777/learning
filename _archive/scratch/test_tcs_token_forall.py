from datetime import datetime

import requests

# Fetching RELIANCE using TCS's token "11536"
symbol = "RELIANCE"
token = "11536"  # TCS token
from_date = int(datetime(2025, 1, 1).timestamp())
to_date = int(datetime.now().timestamp())

url = "https://charting.nseindia.com/v1/charts/symbolHistoricalData"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"https://charting.nseindia.com/?symbol={symbol}-EQ",
}
params = {
    "token": token,
    "fromDate": str(from_date),
    "toDate": str(to_date),
    "symbol": f"{symbol}-EQ",
    "symbolType": "Equity",
    "chartType": "D",
    "timeInterval": "1",
}

print(f"Requesting RELIANCE using TCS token '11536' from 2025-01-01...")
try:
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    print("Status code:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        records = data.get("data", [])
        print("Fetched records:", len(records))
        if records:
            print("First record:", records[0])
            print("Last record:", records[-1])
    else:
        print("Failed:", resp.text[:500])
except Exception as e:
    print("Error:", e)
