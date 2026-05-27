
# NSE Equity Master Table — Implementation Plan

## Goal
Build a comprehensive EQ Master table with:
- Basic security info (Symbol, Name, ISIN, Series, Face Value)
- Index membership (Nifty 50, Nifty 100, Nifty 200, Nifty 500, etc.)
- Sector/Industry classification
- Market cap category (Large, Mid, Small)
- Trading metadata (Listing date, Market lot, etc.)

## Data Sources (from your network traces + research)

### 1. Base Security Master
**Source:** https://nsearchives.nseindia.com/content/equities/sec_list.csv
**Contains:** Symbol, Series, Security Name, Band, Remarks

### 2. Index Constituents
**Source:** https://www.nseindia.com/api/equity-stock-indices?index=NIFTY%2050
**Your trace shows:**
- Endpoint: /api/equity-stock-indices
- Parameter: index=NIFTY 50
- Returns: JSON with constituent stocks

**Available indices to fetch:**
- NIFTY 50
- NIFTY 100
- NIFTY 200
- NIFTY 500
- NIFTY MIDCAP 50
- NIFTY MIDCAP 100
- NIFTY MIDCAP 150
- NIFTY SMALLCAP 50
- NIFTY SMALLCAP 100
- NIFTY SMALLCAP 250
- NIFTY NEXT 50
- NIFTY BANK
- NIFTY IT
- NIFTY PSU BANK
- NIFTY FMCG
- NIFTY PHARMA
- NIFTY AUTO
- NIFTY METAL
- NIFTY REALTY
- NIFTY MEDIA
- NIFTY INFRA
- NIFTY ENERGY
- NIFTY COMMODITIES
- NIFTY CONSUMPTION
- NIFTY FIN SERVICE
- NIFTY PVT BANK

### 3. Sector/Industry Classification
**Source:** https://www.nseindia.com/api/sector-indices
**Alternative:** From individual stock info API

### 4. Detailed Stock Info
**Source:** https://www.nseindia.com/api/quote-equity?symbol=TCS
**Contains:** Industry, Sector, Market cap, etc.

### 5. CM Security File (Most Complete)
**Source:** https://nsearchives.nseindia.com/content/fo/cm_security_YYYYMMDD.csv
**Contains:** Symbol, Series, ISIN, Face Value, Market Lot, etc.

## Proposed Table Schema

```sql
CREATE TABLE nse_equity_master (
    -- Primary Key
    symbol              TEXT PRIMARY KEY,       -- TCS, RELIANCE, etc.

    -- Basic Info
    security_name       TEXT,                   -- Tata Consultancy Services Limited
    isin                TEXT,                   -- INE467B01029
    series              TEXT,                   -- EQ, BE, etc.
    face_value          REAL,                   -- 1.0
    paid_up_value       REAL,                   -- 1.0
    market_lot          INTEGER,                -- 1
    listing_date        DATE,                   -- 2004-08-25

    -- Index Membership (Boolean flags)
    is_nifty50          BOOLEAN DEFAULT FALSE,
    is_nifty100         BOOLEAN DEFAULT FALSE,
    is_nifty200         BOOLEAN DEFAULT FALSE,
    is_nifty500         BOOLEAN DEFAULT FALSE,
    is_nifty_next50     BOOLEAN DEFAULT FALSE,
    is_nifty_midcap50   BOOLEAN DEFAULT FALSE,
    is_nifty_midcap100  BOOLEAN DEFAULT FALSE,
    is_nifty_midcap150  BOOLEAN DEFAULT FALSE,
    is_nifty_smallcap50 BOOLEAN DEFAULT FALSE,
    is_nifty_smallcap100 BOOLEAN DEFAULT FALSE,
    is_nifty_smallcap250 BOOLEAN DEFAULT FALSE,

    -- Sector Indices
    is_nifty_bank       BOOLEAN DEFAULT FALSE,
    is_nifty_it         BOOLEAN DEFAULT FALSE,
    is_nifty_psu_bank   BOOLEAN DEFAULT FALSE,
    is_nifty_fmcg       BOOLEAN DEFAULT FALSE,
    is_nifty_pharma     BOOLEAN DEFAULT FALSE,
    is_nifty_auto       BOOLEAN DEFAULT FALSE,
    is_nifty_metal      BOOLEAN DEFAULT FALSE,
    is_nifty_realty     BOOLEAN DEFAULT FALSE,
    is_nifty_media      BOOLEAN DEFAULT FALSE,
    is_nifty_infra      BOOLEAN DEFAULT FALSE,
    is_nifty_energy     BOOLEAN DEFAULT FALSE,

    -- Classification
    sector              TEXT,                   -- Information Technology
    industry            TEXT,                   -- IT Consulting & Software
    macro_sector        TEXT,                   -- Technology

    -- Market Cap Category (derived from index membership)
    market_cap_category TEXT,                   -- Large, Mid, Small

    -- Trading Metadata
    price_band          REAL,                   -- 20.0 (percentage)
    tick_size           REAL,                   -- 0.05

    -- Timestamps
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Source tracking
    data_source         TEXT                    -- nse_api, cm_file, csv, etc.
);
```

## Implementation Steps

### Phase 1: Fetch Base Data
1. Download `sec_list.csv` for all securities
2. Download CM Security File for ISIN, Face Value, etc.
3. Merge into base DataFrame

### Phase 2: Fetch Index Constituents
1. Loop through all indices
2. For each index, call `/api/equity-stock-indices?index=INDEX_NAME`
3. Mark symbols as members of each index

### Phase 3: Fetch Sector/Industry
1. For each symbol, call `/api/quote-equity?symbol=SYMBOL`
2. Extract sector and industry
3. OR use bulk sector API if available

### Phase 4: Derive Categories
1. Market cap category:
   - Large Cap: Nifty 100 member
   - Mid Cap: Nifty Midcap 150 member (not in Nifty 100)
   - Small Cap: Nifty Smallcap 250 member (not in above)

### Phase 5: Save and Cache
1. Save as Parquet (fast) + CSV (human-readable)
2. Cache with 1-day freshness
3. Provide update method

## Python Implementation Plan

```python
class NSEEquityMasterBuilder:
    """Builds comprehensive NSE Equity Master table."""

    def __init__(self, cache_dir="data/cache"):
        self.session = requests.Session()
        self.cache_dir = cache_dir

    def build_master_table(self) -> pd.DataFrame:
        # Step 1: Base securities
        df = self._fetch_base_securities()

        # Step 2: Index memberships
        indices = [
            "NIFTY 50", "NIFTY 100", "NIFTY 200", "NIFTY 500",
            "NIFTY NEXT 50", "NIFTY MIDCAP 50", "NIFTY MIDCAP 100",
            "NIFTY MIDCAP 150", "NIFTY SMALLCAP 50", "NIFTY SMALLCAP 100",
            "NIFTY SMALLCAP 250", "NIFTY BANK", "NIFTY IT",
            "NIFTY PSU BANK", "NIFTY FMCG", "NIFTY PHARMA",
            "NIFTY AUTO", "NIFTY METAL", "NIFTY REALTY",
            "NIFTY MEDIA", "NIFTY INFRA", "NIFTY ENERGY",
        ]

        for index_name in indices:
            members = self._fetch_index_constituents(index_name)
            col_name = f"is_{index_name.lower().replace(' ', '_')}"
            df[col_name] = df["symbol"].isin(members)

        # Step 3: Sector/Industry
        df = self._enrich_sector_industry(df)

        # Step 4: Derive market cap category
        df["market_cap_category"] = df.apply(self._derive_market_cap, axis=1)

        return df

    def _fetch_index_constituents(self, index_name: str) -> list[str]:
        """Fetch constituents for a given index."""
        url = "https://www.nseindia.com/api/equity-stock-indices"
        params = {"index": index_name}

        # Need cookies from nseindia.com first
        self.session.get("https://www.nseindia.com", timeout=10)

        resp = self.session.get(url, params=params, timeout=30)
        data = resp.json()

        # Extract symbols from response
        symbols = []
        if "data" in data:
            for item in data["data"]:
                if "symbol" in item:
                    symbols.append(item["symbol"])

        return symbols
```

## Output Files

| File | Format | Purpose |
|------|--------|---------|
| `nse_equity_master.parquet` | Parquet | Fast loading in Python |
| `nse_equity_master.csv` | CSV | Human-readable, Excel |
| `nse_equity_master.json` | JSON | API consumption |

## Usage in Your Pipeline

```python
from nse_equity_master_builder import NSEEquityMasterBuilder

# Build or load master
builder = NSEEquityMasterBuilder()
df_master = builder.build_master_table()

# Filter for specific universe
nifty50 = df_master[df_master["is_nifty50"] == True]["symbol"].tolist()
nifty100 = df_master[df_master["is_nifty100"] == True]["symbol"].tolist()
midcaps = df_master[df_master["market_cap_category"] == "Mid"]["symbol"].tolist()

# Use in screener
screener = StockScreener()
screener.screen_stocks(symbols=nifty50)
```
