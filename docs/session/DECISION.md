# Decision Log

## Architecture
- **Corporate Data Caching Strategy**: Instead of pulling fundamental data point-by-point, we perform a 30-day bulk fetch of Announcements, Events, Insider Trading, and Corporate Actions, caching the DataFrame to a `.parquet` file (`data/corporate_cache/`). This radically reduces NSE API calls, avoids rate limits, and accelerates screener processing time.
- **Screener Output**: The quantitative technical signals are directly enriched by merging the corporate dataframe cache directly before saving to the CSV/rich table outputs.

## Development Standards
- **Strict Linting**: The codebase strictly adheres to Ruff formatting (`--select I --fix`) and strict MyPy static type-checking. All legacy God-Script code is actively being transitioned to 100% compliant modules.
