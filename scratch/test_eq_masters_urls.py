import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://charting.nseindia.com/",
}

urls = [
    "https://charting.nseindia.com/Charts/GetEQMasters",
    "https://charting.nseindia.com/v1/charts/GetEQMasters",
    "https://charting.nseindia.com/charts/GetEQMasters",
    "https://charting.nseindia.com/v1/charts/GetEQMaster",
    "https://charting.nseindia.com/v1/charts/eqmasters",
    "https://charting.nseindia.com/v1/charts/eqmaster",
    "https://www.nseindia.com/api/chart-share-data",
    "https://www.nseindia.com/api/historical/cm/equity/GetEQMasters",
]

for url in urls:
    try:
        print(f"Testing: {url}")
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            print("  SUCCESS! Length:", len(resp.text))
            print("  Snippet:", resp.text[:200])
            break
    except Exception as e:
        print(f"  Error: {e}")
