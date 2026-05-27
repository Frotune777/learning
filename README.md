# Local NSE Bhavcopy Downloader & Processor

An institutional-grade, local-first Python application that downloads daily market Bhavcopy files from the National Stock Exchange (NSE) of India, cleans and filters the records for active equities, sorts them by daily turnover, and saves the top 250 records to local folders in English.

---

## Key Features

- **Local Execution:** No Google Sheets credentials or remote spreadsheet configurations required.
- **Auto-date Scanning:** Automatically scans backwards from today (up to 7 days) to target the most recent active trading day (excluding weekends and market holidays).
- **Intelligent Filtering:** Retains only pure equity series (`EQ` series), stripping away ETFs, Mutual Funds, and commodity keywords.
- **Standardized Exports:** Outputs raw zip files to `data/raw/` and processed top 250 stock lists sorted by turnover descending to `data/processed/` in a clean CSV format.
- **DuckDB Time-Series Query Engine:** Runs high-performance SQL queries over local historical Parquet stores.
- **Random Forest Classifier:** Predicts next-day stock price directions utilizing technical indicators (RSI, MACD), rolling volatility, and delivery percentage accumulation.
- **NSE Backtesting Engine:** Simulates vectorized or event-driven backtests featuring real NSE transaction costs, T+1 cash settlement cycles, F&O ban verification, and daily circuit limit blocks (UC/LC).
- **Robust Quality Control:** Fully typed, compliant with strict PEP-8 standards via Ruff formatting, and backed by a comprehensive unit testing framework.

---

## Directory Structure

```
.
├── CHANGELOG.md             # Project change history
├── PROJECT_STRUCTURE.md     # Module maps and dependency flows
├── README.md                # System overview and setup instructions
├── TASKS.md                 # Local task status board
├── data
│   ├── processed            # Top 250 filtered stock lists (CSV format)
│   └── raw                  # Raw downloaded ZIP files from the NSE
├── main.py                  # Interactive CLI REPL and orchestrator entry point
├── pyproject.toml           # Strict package versions and linter settings
├── src
│   ├── data
│   │   └── fetcher          # Stateful NSE charting API downloader
│   ├── nse_bhavcopy         # Core downloader, screener, ML, and backtesters
│   └── nse_live             # Pre-market and options data hub
├── tests                    # Pytest test suite
└── uv.lock                  # Dependency locking mapping
```

---

## Quick Start

### 1. Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Make sure your machine runs Python 3.13+.

### 2. Setup

Sync packages and construct the local virtual environment:

```bash
uv sync
```

### 3. CLI Subcommands

#### Launch Interactive REPL Menu
```bash
uv run main.py menu
```

#### Run ML Backtest on a Symbol
```bash
uv run main.py backtest --symbol TCS --n-estimators 100 --max-depth 5
```

#### Fetch F&O Ban List
```bash
uv run main.py fo-ban
```

---

## Development Guidelines

### Import Fixes and Formatting

```bash
uv run ruff check --select I --fix .  # Sort imports
uv run ruff format .                    # Format code files
uv run ruff check .                      # Verify linting
```

### Static Type Checks

```bash
uv run mypy --explicit-package-bases src/
uv run mypy --explicit-package-bases main.py
```

### Running Tests

Execute pytest with code coverage tracking:

```bash
uv run pytest tests/ -v
```
