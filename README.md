# Fortune Analytical Decision-Support System (Fortune ADSS)

An **institutional-grade, local-first Python quantitative analysis platform** for the National Stock Exchange (NSE) of India. Built for offline-first research and screening: on startup, it verifies data recency across the local Parquet data lake (~2,900+ symbols), alerts the user to data currency, and optionally pulls updates via a 3-tier fallback cascade (1st Yahoo Finance, 2nd Fyers if authenticated, 3rd NSE website charting). All technical screeners, Smart Money Concepts (SMC) engines, and machine learning models execute directly against the stored local data lake until switched to live mode.

---

## ✨ Feature Highlights

| Layer | Details |
|---|---|
| **App Name** | **Fortune Analytical Decision-Support System** (Fortune ADSS) |
| **Operating Mode** | **Offline-First (Stored Data Lake by Default)**; optional Live Mode toggle |
| **Data Sources** | 3-Tier Fallback: **1st YFinance → 2nd Fyers API v3 (if connected) → 3rd NSE Charting** |
| **Startup Check** | Auto-inspects local Parquet lake recency; prompts user to pull new data if behind |
| **Universe** | All NSE EQ equities (~2,900+ symbols stored locally) |
| **Strategies** | 13 (VCP, TTM Squeeze, Dual SuperTrend, Lorentzian ML, RDX, Candle Patterns, +7 more) |
| **Smart Money (SMC)** | Order Blocks, FVGs, Sweeps, BOS/CHoCH, Dealing-range Premium/Discount |
| **Scoring** | Multi-factor weighted consensus engine + AI narrative |
| **ML Layer** | Random Forest classifier, Isolation Forest Anomaly Detector, Lorentzian KNN |
| **Dashboard** | Streamlit dark-mode visual cockpit (SMC Studio, Screener, Risk, Macro, Backtest) |
| **CLI** | 38-option interactive REPL with startup recency auditing |


---

## 🏗️ Architecture

```
learning/
├── main.py                     # Unified CLI entry point (28 commands)
├── src/
│   ├── cli/                    # REPL menu, formatters, reporters, Telegram
│   │   ├── menus.py            # 28 interactive menu handlers
│   │   ├── telegram.py         # Telegram Bot API notifications
│   │   ├── reporter.py         # Rich console result tables + AI narrative
│   │   └── visual.py           # Premium VisualUI panels
│   ├── core/                   # Config, consensus engine, signal protocol
│   ├── engine/                 # 13 pure strategy calculators + parallel scanner
│   ├── storage/                # Equity master, historical sync, registry, bhavcopy
│   ├── data/fetcher/           # NSE charting API + yfinance + circuit breaker
│   ├── nse_bhavcopy/           # TA indicators, backtester, quant metrics, ML
│   ├── nse_live/               # Pre-market, options chain, live NSE hub
│   ├── scanners/               # Minervini, ETF, momentum squeeze, pair scanner
│   ├── scrapers/               # MMI, F&O ban, corporate data, index fetcher
│   ├── ml/                     # ML classifier, anomaly detector, gatekeeper
│   ├── scoring/                # Multi-factor weighted scoring engine
│   ├── portfolio/              # Simulated cash/position portfolio engine
│   └── dashboard/              # Streamlit app (4 pages)
├── tests/                      # 22 test files, 187 passing tests
├── data/
│   ├── raw/                    # Bhavcopy ZIP cache
│   ├── processed/              # Top-250 CSVs + screener output
│   └── historical/1d/          # Per-symbol OHLCV Parquet files
└── pyproject.toml              # uv project config (Python 3.12+)
```

---

## 🚀 Quick Start

See **[INSTALLATION.md](INSTALLATION.md)** for full setup instructions.

```bash
# 1. Install dependencies
uv sync

# 2. Configure credentials
cp ".env copy.example" .env    # edit with your Fyers + Telegram keys

# 3. Build equity master
uv run main.py build-master

# 4. Sync historical data (30 days via Bhavcopy)
uv run main.py bhavcopy-sync --days 30

# 5. Run screener
uv run main.py screen

# 6. Launch Streamlit dashboard
uv run streamlit run src/dashboard/app.py

# Or use the interactive menu for everything
uv run main.py menu
```

---

## 📋 Interactive Menu (28 Options)

| # | Feature | Description |
|---|---|---|
| **DATA** | | |
| 1 | Build Equity Master | Downloads sec_list + all NSE index constituents |
| 2 | Sync Historical — All | Full OHLCV Parquet sync for all symbols |
| 3 | Sync Historical — Filtered | Filter by cap size, index membership, or count |
| **ANALYSIS** | | |
| 4 | Technical Screener | Bull Run + CAR + Swing + 13 strategies |
| 7 | TA Dashboard — Single Stock | RSI, MACD, Bollinger, ADX for one ticker |
| 8 | Recompute TA Indicators | Refresh all Parquet TA columns |
| 24 | Strategy Inspector | All 13 strategy signals for one stock |
| 25 | Consensus Leaderboard | Top stocks by multi-strategy agreement |
| **STATUS** | | |
| 5 | Parquet Sync Status | Rows, date ranges per symbol |
| 6 | Sync Registry | Pending / failed / ok breakdown |
| 26 | Data Quality & Auto-Healer | Scan + fix data gaps |
| **QUANTITATIVE** | | |
| 9 | Liquid ETF Screener | Top liquid ETFs per sector |
| 10 | Minervini Template | VCP, RS Rating & Trend Screen |
| 11 | Sector Rotation | JdK RS-Ratio quadrant analysis |
| 12 | Correlation Matrix | Cross-asset return correlation |
| 13 | Nifty Indices Heatmap | Constituent performance heatmap |
| 14 | Market Mood Index (MMI) | Live sentiment scraper (Tickertape) |
| 15 | Moving Average Slope | Trend angle analyzer |
| 16 | Momentum Squeeze | BB/KC coiled-spring detector |
| 17 | Live NSE Data Hub | Pre-market, price info, option chain |
| 18 | Cointegration Pair Scanner | Engle-Granger pairs |
| 19 | ML Classifier Backtester | Random Forest + event backtest |
| 20 | F&O Ban List | Current NSE F&O ban securities |
| 21 | Bhavcopy Incremental Sync | Batch OHLCV update (1 ZIP/day) |
| 22 | Set Fyers API Token | Configure access token for data |
| 23 | ML Anomaly Detector | Identify bad ticks / smart money |
| **ALERTS** | | |
| 27 | Configure Telegram Alerts | Set bot token & chat ID |
| 28 | Send Results via Telegram | Push screener CSVs to Telegram |

---

## 🧪 Development

```bash
# Lint
uv run ruff check src/ main.py

# Auto-fix imports + format
uv run ruff check --select I --fix src/ main.py && uv run ruff format src/ main.py

# Type checks
uv run mypy --explicit-package-bases src/ main.py

# Tests
uv run pytest tests/ -v                                  # 187 tests
uv run pytest tests/ -v --cov=src --cov-report=term-missing   # with coverage
```

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
