# fyers/ — ARCHIVED (Unit 2)

**Archived on:** 2026-10-15
**Reason:** Orphaned OpenAlgo extract. Zero live imports from src/, tests/,
main.py, or interactive_scanner.py. 10 broken top-level imports:
broker.*, database.*, utils.httpx_client, extensions, zmq.

## What lives here
OpenAlgo broker integration (API v3 order/margin/data/funds, HSM WebSocket
streaming, master contract DB). Originally part of the OpenAlgo project.

## Why archived, not deleted
Preserved for potential reuse of order-routing / WebSocket logic in a future
unit (proposed Unit 14). Nothing was deleted.

## The REAL Fyers integration
The canonical codebase uses src/nse_bhavcopy/fyers_fetcher.py
(FyersFetcher — historical OHLCV, quotes, option chain). That module is
ACTIVE and has 20 references across src/cli, src/core, src/dashboard,
src/storage, and tests/.

## Reviving this folder
To un-archive: port the OpenAlgo scaffolding (broker/, database/, utils/,
extensions/) into the canonical src/ namespace, then rewrite relative
imports. Estimated effort: 1-2 days. Not scheduled.
