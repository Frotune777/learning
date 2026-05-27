import sys

sys.path.insert(0, ".")
from src.nse_bhavcopy.historical_sync import HistoricalSync

hs = HistoricalSync(data_dir="data/historical", timeframe="1d", start_date="2025-01-01")
ok = hs.sync_one("TCS")
print("TCS sync result:", ok)
if ok:
    df = hs.read("TCS")
    print("Rows:", len(df))
    print(df.tail(3))
