"""Platform pipeline orchestrator and CLI entry point."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from src.platform.loaders.landing import LandingLoader
from src.platform.loaders.staging import StagingLoader


class PlatformOrchestrator:
    """Orchestrates end-to-end ingestion, staging, and warehouse loading."""

    def __init__(self, data_root: str = "data") -> None:
        self.data_root = Path(data_root)
        self.landing_loader = LandingLoader(self.data_root / "landing")
        self.staging_loader = StagingLoader(
            self.data_root / "landing", self.data_root / "staging"
        )

    def ingest(self, source: str, trade_date: date) -> str:
        """Download raw data into immutable landing layer and return batch_id."""
        return self.landing_loader.ingest(source, trade_date)

    def stage(self, batch_id: str) -> int:
        """Validate and stage landed data into canonical Parquet tables."""
        return self.staging_loader.stage(batch_id)

    def load_warehouse(self, batch_id: str) -> None:
        """Atomically load staged data into DuckDB warehouse."""
        raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    """CLI dispatcher for platform commands."""
    parser = argparse.ArgumentParser(description="NSE Data Platform Orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest command
    ingest_p = subparsers.add_parser("ingest", help="Ingest raw market data into landing layer")
    ingest_p.add_argument(
        "--source", required=True, help="Data source identifier (e.g. nse_bhavcopy)"
    )
    ingest_p.add_argument("--trade-date", required=True, help="Trade date in YYYY-MM-DD format")

    # Stage command
    stage_p = subparsers.add_parser(
        "stage", help="Stage landed batch into canonical Parquet tables"
    )
    stage_p.add_argument("--batch-id", required=True, help="Landing batch ID to stage")

    args = parser.parse_args(argv)
    orchestrator = PlatformOrchestrator()

    if args.command == "ingest":
        try:
            t_date = date.fromisoformat(args.trade_date)
        except ValueError as exc:
            print(
                f"Error: Invalid date format {args.trade_date}. Expected YYYY-MM-DD: {exc}",
                file=sys.stderr,
            )
            return 1
        print(f"Starting ingest for source={args.source}, trade_date={args.trade_date}...")
        batch_id = orchestrator.ingest(args.source, t_date)
        print(f"Ingest complete. Batch ID: {batch_id}")
        return 0

    if args.command == "stage":
        print(f"Starting stage for batch_id={args.batch_id}...")
        rows_written = orchestrator.stage(args.batch_id)
        print(f"Stage complete. Rows staged: {rows_written} (Batch: {args.batch_id})")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
