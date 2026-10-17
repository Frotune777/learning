"""Platform pipeline orchestrator and CLI entry point."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

from src.platform.loaders.landing import LandingLoader
from src.platform.loaders.staging import StagingLoader
from src.platform.loaders.warehouse import WarehouseLoader
from src.platform.migrations.runner import MigrationRunner


class PlatformOrchestrator:
    """Orchestrates end-to-end ingestion, staging, warehouse loading, and migrations."""

    def __init__(self, data_root: str = "data") -> None:
        self.data_root = Path(data_root)
        self.landing_loader = LandingLoader(self.data_root / "landing")
        self.staging_loader = StagingLoader(
            self.data_root / "landing", self.data_root / "staging"
        )
        self.warehouse_loader = WarehouseLoader(self.data_root / "warehouse.duckdb")
        self.migration_runner = MigrationRunner(db_path=self.data_root / "warehouse.duckdb")

    def ingest(self, source: str, trade_date: date) -> str:
        """Download raw data into immutable landing layer and return batch_id."""
        return self.landing_loader.ingest(source, trade_date)

    def stage(self, batch_id: str) -> int:
        """Validate and stage landed data into canonical Parquet tables."""
        return self.staging_loader.stage(batch_id)

    def migrate(self) -> list[int]:
        """Apply all pending database migrations."""
        return self.migration_runner.migrate()

    def seed_dimensions(self) -> dict[str, int]:
        """Seed all warehouse dimensions."""
        return self.warehouse_loader.seed_dimensions()

    def backfill_warehouse(self, source_dir: Path | str = "data/historical/1d") -> dict[str, Any]:
        """Backfill price and TA facts from historical Parquets."""
        price_res = self.warehouse_loader.backfill_price_from_historical(source_dir)
        ta_res = self.warehouse_loader.backfill_ta_from_historical(source_dir)
        return {"price": price_res, "ta": ta_res}

    def backfill_dq(self, runs_log: Path | str = "logs/dq/runs.jsonl") -> dict[str, int]:
        """Backfill data quality run logs."""
        return self.warehouse_loader.backfill_dq_from_logs(runs_log)


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

    # Migrate command
    subparsers.add_parser("migrate", help="Run pending warehouse database DDL migrations")

    # Seed dimensions command
    subparsers.add_parser("seed-dimensions", help="Seed static warehouse dimensions")

    # Backfill warehouse command
    backfill_p = subparsers.add_parser(
        "backfill-warehouse", help="Backfill facts from historical Parquet files"
    )
    backfill_p.add_argument(
        "--source-dir",
        default="data/historical/1d",
        help="Directory containing historical Parquets",
    )

    # Backfill DQ command
    dq_p = subparsers.add_parser("backfill-dq", help="Backfill Data Quality logs into fact_dq_run")
    dq_p.add_argument("--runs-log", default="logs/dq/runs.jsonl", help="Path to runs.jsonl log")

    args = parser.parse_args(argv)
    orchestrator = PlatformOrchestrator()

    if args.command == "ingest":
        try:
            t_date = date.fromisoformat(args.trade_date)
        except ValueError as exc:
            print(f"Error: Invalid date format {args.trade_date}: {exc}", file=sys.stderr)
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

    if args.command == "migrate":
        print("Applying pending database migrations...")
        applied = orchestrator.migrate()
        print(f"Migrations applied: {applied}")
        return 0

    if args.command == "seed-dimensions":
        print("Seeding warehouse dimensions...")
        counts = orchestrator.seed_dimensions()
        print(f"Dimensions seeded: {counts}")
        return 0

    if args.command == "backfill-warehouse":
        print(f"Backfilling warehouse from {args.source_dir}...")
        res = orchestrator.backfill_warehouse(args.source_dir)
        print(f"Warehouse backfill complete: {res}")
        return 0

    if args.command == "backfill-dq":
        print(f"Backfilling DQ logs from {args.runs_log}...")
        res = orchestrator.backfill_dq(args.runs_log)
        print(f"DQ backfill complete: {res}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
