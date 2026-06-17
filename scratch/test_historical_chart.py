from datetime import datetime

import requests

# Fetching TCS since 2000-01-01
symbol = "TCS"
token = "11536"  # TCS token
from_date = int(datetime(2000, 1, 1).timestamp())
to_date = int(datetime.now().timestamp())

url = "https://charting.nseindia.com/v1/charts/symbolHistoricalData"
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": f"https://charting.nseindia.com/?symbol={symbol}-EQ",
}
params = {
    "token": token,
    "fromDate": str(from_date),
    "toDate": str(to_date),
    "symbol": f"{symbol}-EQ",
    "symbolType": "Equity",
    "chartType": "I",  # "I" for intraday/daily? Wait, in nse_charts.py they use "D" for daily, "I" is for intraday, let's try both!
    "timeInterval": "1",  # "1" or what? in nse_charts.py, D has timeInterval 1
}

# Let's try to query daily charting data!
# In src/data/fetcher/prices/nse_charts.py:
# D maps to chartType = "D", timeInterval = "1"? Wait, TF_MAP: "1d": ("D", 1)
# Wait, let's try both: chartType="D" & timeInterval="1"
params_d = {
    "token": token,
    "fromDate": str(from_date),
    "toDate": str(to_date),
    "symbol": f"{symbol}-EQ",
    "symbolType": "Equity",
    "chartType": "D",
    "timeInterval": "1",
}

print(
    f"Requesting data for {symbol} from {datetime.fromtimestamp(from_date)} to {datetime.fromtimestamp(to_date)}..."
)
try:
    resp = requests.get(url, params=params_d, headers=headers, timeout=30)
    print("Status code:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        records = data.get("data", [])
        print("Fetched records:", len(records))
        if records:
            print("First record:", records[0])
            print("Last record:", records[-1])
            # Check what date field we have
            ts = records[0].get("time") or records[0].get("timestamp")
            if ts:
                print(
                    "First record date:",
                    datetime.fromtimestamp(ts)
                    if ts < 1_000_000_000_000
                    else datetime.fromtimestamp(ts / 1000),
                )
    else:
        print("Failed:", resp.text[:500])
except Exception as e:
    print("Error:", e)
