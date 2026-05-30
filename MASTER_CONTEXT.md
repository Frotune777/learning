# Master Context

## Current Objective
Stabilize and Modularize the NSE Screener application, migrating from monolithic scripts to an institutional-grade, highly testable pipeline combining Technical Analysis (TA) and Fundamental Intelligence.

## System Architecture
1. **Data Acquisition Layer**: `BhavcopyDownloader` + `HistoricalSync` manages price fetching via Parquet caches.
2. **Fundamental Intelligence Layer**: `CorporateDataScraper` caches Announcements, Insider Trading, and Events directly from the NSE to validate TA setups.
3. **Processing Engine**: A parallelized `StockScreener` iterates through the cache, calculating over 10 different trading strategies (Darvas Box, MMI, DMADMA).
4. **CLI Interface**: Interactive REPL loop powered by `rich` to cleanly present tables and orchestrate automated system sweeps.

## Next Steps
- Expand ML Anomaly detection for smarter Bhavcopy discrepancy handling.
- Continually refine edge-case exception handling within the CLI loops.
- Standardize full unit-test coverage to 100% across all quantitative components.
