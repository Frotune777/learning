# Local NSE Bhavcopy Downloader & Processor

An institutional-grade, local-first Python application that downloads daily market Bhavcopy files from the National Stock Exchange (NSE) of India, cleans and filters the records for active equities, sorts them by daily turnover, and saves the top 250 records to local folders in English.

---

## Key Features

- **Local Execution:** No Google Sheets credentials or remote spreadsheet configurations required.
- **Auto-date Scanning:** Automatically scans backwards from today (up to 7 days) to target the most recent active trading day (excluding weekends and market holidays).
- **Intelligent Filtering:** Retains only pure equity series (`EQ` series), stripping away ETFs, Mutual Funds, and commodity keywords (e.g., `BEES`, `ETF`, `GOLD`, `LIQUID`).
- **Standardized Exports:** Outputs raw zip files to `data/raw/` and processed top 250 stock lists sorted by turnover descending to `data/processed/` in a clean CSV format.
- **Robust Quality Control:** Fully typed, compliant with strict PEP-8 standards via Ruff formatting, and backed by a comprehensive unit testing framework with 100% test coverage.

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
├── lerarning.py             # Pipeline orchestrator and entry point
├── pyproject.toml           # Strict package versions and linter settings
├── src
│   └── nse_bhavcopy
│       ├── __init__.py      # Package constructor
│       └── downloader.py    # Core downloader and processor class
├── tests
│   ├── __init__.py      # Test package constructor
│   └── test_downloader.py  # Moked unit test cases
└── uv.lock                  # Dependency locking mapping
```

---

## Quick Start

### 1. Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed. If not, install it using:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Make sure your machine runs Python 3.13+.

### 2. Setup

Sync packages and construct the local virtual environment:

```bash
uv sync
```

This will lock exact package versions (`pandas==2.2.3`, `requests==2.32.3`) automatically.

### 3. Execution

To run the main local NSE downloader pipeline:

```bash
uv run python lerarning.py
```

Check `data/raw/` for the downloaded ZIP archives and `data/processed/` for the extracted top 250 stocks list.

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
uv run mypy src/ --explicit-package-bases
uv run mypy lerarning.py --explicit-package-bases
```

### Running Tests

Execute pytest with code coverage tracking:

```bash
uv run pytest tests/ -v --cov=src
```
