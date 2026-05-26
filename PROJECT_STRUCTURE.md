# Project Structure

Last Updated: 2026-05-26
## Directory Tree

```
.
├── data
│   ├── processed
│   └── raw
├── lerarning.py
├── PROJECT_STRUCTURE.md
├── pyproject.toml
├── src
│   └── nse_bhavcopy
│       ├── downloader.py
│       └── __init__.py
├── TASKS.md
└── tests
    ├── __init__.py
    └── test_downloader.py
```

## Module Responsibilities

### src/nse_bhavcopy

**Purpose:** Core package containing the logic for downloading, cleaning, and extracting Top 250 EQ stocks by turnover from the NSE Bhavcopy market file.
**Key Files:**
- `downloader.py`: Houses the `BhavcopyDownloader` class responsible for sending HTTP requests to the NSE archive, downloading raw zip bytes, saving them locally, cleaning data, filtering for series 'EQ' and discarding ETFs, and exporting the top 250 records to CSV.
- `__init__.py`: Package entry point.

**Dependencies:**
- `pandas`
- `requests`

**Used By:**
- `lerarning.py` (Main entry point)
- `tests/test_downloader.py` (Unit tests)

---

### tests

**Purpose:** Houses all pytest unit tests to verify logic correctness and maintain 100% test coverage.
**Key Files:**
- `test_downloader.py`: Contains test suites mocking network responses and verifying raw/processed folder savings.

---

### Root Directory

**Purpose:** Orchestration, environment settings, and task tracking.
**Key Files:**
- `lerarning.py`: Script executing the downloader across date offsets until a successful day is found.
- `TASKS.md`: Project-level task checklist and status details.
- `pyproject.toml`: Project dependencies and configuration settings.
