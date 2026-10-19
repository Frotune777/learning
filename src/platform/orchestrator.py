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

    def enrich_master(self, tiers: list[int] | None = None) -> dict[str, Any]:
        """Run Tier 1 & 2 master enrichment via SCD2."""
        return self.warehouse_loader.enrich_master(tiers)

    def backfill_delivery(self) -> int:
        """Backfill daily security delivery metrics from staging."""
        return self.warehouse_loader.backfill_delivery_from_staging()

    def backfill_delivery_history(
        self,
        start_date: date,
        end_date: date,
        cache_dir: str = "data/raw/delivery",
        rate_delay: float = 1.0,
    ) -> dict[str, int]:
        """Backfill historical delivery data from official NSE archives (2020+)."""
        from src.platform.loaders.delivery_backfill import backfill_delivery_history

        return backfill_delivery_history(
            start_date=start_date,
            end_date=end_date,
            warehouse_loader=self.warehouse_loader,
            cache_dir=cache_dir,
            rate_delay=rate_delay,
        )

    def backfill_surveillance(self) -> int:
        """Backfill surveillance measures (ASM, GSM, ESM) snapshot."""
        return self.warehouse_loader.backfill_surveillance_today()

    def backfill_symbol_health(self) -> int:
        """Backfill symbol health assessment snapshot."""
        return self.warehouse_loader.backfill_symbol_health()

    def populate_calendar(
        self,
        start_date: date = date(2000, 1, 1),
        end_date: date = date(2030, 12, 31),
    ) -> int:
        """Populate dim_date using pandas_market_calendars XNSE."""
        from src.platform.loaders.calendar_backfill import populate_full_nse_calendar

        return populate_full_nse_calendar(
            start_date=start_date,
            end_date=end_date,
            db_path=self.warehouse_loader.db_path,
        )

    def rebuild_price(
        self,
        start_date: date = date(2020, 1, 1),
        end_date: date = date(2026, 10, 16),
        cache_dir: str = "data/raw/delivery",
    ) -> dict[str, int]:
        """Rebuild fact_price_daily for 2020+ from official NSE sec_bhavdata."""
        from src.platform.loaders.price_rebuilder import rebuild_price_from_sec_bhavdata

        return rebuild_price_from_sec_bhavdata(
            start_date=start_date,
            end_date=end_date,
            cache_dir=cache_dir,
            warehouse_loader=self.warehouse_loader,
        )

    def rebuild_ta(
        self,
        start_date: date = date(2020, 1, 1),
        end_date: date = date(2026, 10, 16),
        max_workers: int = 8,
    ) -> dict[str, int]:
        """Rebuild fact_ta_daily from fact_price_daily."""
        from src.platform.loaders.ta_rebuilder import rebuild_ta_from_warehouse

        return rebuild_ta_from_warehouse(
            start_date=start_date,
            end_date=end_date,
            warehouse_loader=self.warehouse_loader,
            max_workers=max_workers,
        )


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

    # Enrich master command
    enrich_p = subparsers.add_parser("enrich-master", help="Enrich master universe via SCD2")
    enrich_p.add_argument(
        "--tiers", nargs="+", type=int, default=[1, 2], help="Enrichment tiers to execute"
    )

    # Backfill delivery command (from staging)
    subparsers.add_parser("backfill-delivery", help="Backfill fact_delivery_daily from staging")

    # Backfill delivery history command (from official NSE archives)
    deliv_hist_p = subparsers.add_parser(
        "backfill-delivery-history", help="Backfill fact_delivery_daily from NSE sec_bhavdata archives"
    )
    deliv_hist_p.add_argument("--start", default="2020-01-01", help="Start date (YYYY-MM-DD)")
    deliv_hist_p.add_argument(
        "--end", default=date.today().isoformat(), help="End date (YYYY-MM-DD)"
    )
    deliv_hist_p.add_argument(
        "--cache-dir", default="data/raw/delivery", help="Cache directory for raw files"
    )
    deliv_hist_p.add_argument(
        "--delay", type=float, default=1.0, help="Rate delay between requests in seconds"
    )

    # Backfill surveillance command
    subparsers.add_parser("backfill-surveillance", help="Backfill fact_symbol_surveillance")

    # Backfill symbol health command
    subparsers.add_parser("backfill-symbol-health", help="Backfill fact_symbol_health")

    # Populate calendar command
    subparsers.add_parser("populate-calendar", help="Populate dim_date using full XNSE calendar")

    # Rebuild price command
    reb_price_p = subparsers.add_parser("rebuild-price", help="Rebuild fact_price_daily from sec_bhavdata")
    reb_price_p.add_argument("--start", default="2020-01-01", help="Start date (YYYY-MM-DD)")
    reb_price_p.add_argument("--end", default="2026-10-16", help="End date (YYYY-MM-DD)")
    reb_price_p.add_argument("--source", default="sec_bhavdata", help="Source type (sec_bhavdata)")
    reb_price_p.add_argument("--cache-dir", default="data/raw/delivery", help="Cache directory")

    # Rebuild TA command
    reb_ta_p = subparsers.add_parser("rebuild-ta", help="Rebuild fact_ta_daily from fact_price_daily")
    reb_ta_p.add_argument("--start", default="2020-01-01", help="Start date (YYYY-MM-DD)")
    reb_ta_p.add_argument("--end", default="2026-10-16", help="End date (YYYY-MM-DD)")
    reb_ta_p.add_argument("--source", default="warehouse", help="Source type (warehouse)")
    reb_ta_p.add_argument("--workers", type=int, default=8, help="Max worker threads")

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

    if args.command == "enrich-master":
        print(f"Enriching master universe for tiers={args.tiers}...")
        res = orchestrator.enrich_master(args.tiers)
        print(f"Master enrichment complete: {res}")
        return 0

    if args.command == "backfill-delivery":
        print("Backfilling delivery from staging...")
        rows = orchestrator.backfill_delivery()
        print(f"Delivery backfill complete: {rows} rows")
        return 0

    if args.command == "backfill-delivery-history":
        try:
            start_d = date.fromisoformat(args.start)
            end_d = date.fromisoformat(args.end)
        except ValueError as exc:
            print(f"Error: Invalid date format: {exc}", file=sys.stderr)
            return 1
        print(f"Starting delivery history backfill from {start_d} to {end_d}...")
        res = orchestrator.backfill_delivery_history(
            start_date=start_d,
            end_date=end_d,
            cache_dir=args.cache_dir,
            rate_delay=args.delay,
        )
        print("Delivery history backfill complete:")
        print(f"  Downloaded: {res['downloaded']} files")
        print(f"  Parsed: {res['parsed']} files")
        print(f"  Inserted: {res['inserted']} rows")
        print(f"  Skipped (unknown symbols): {res['skipped_unknown_symbol']}")
        return 0

    if args.command == "backfill-surveillance":
        print("Backfilling symbol surveillance snapshot...")
        rows = orchestrator.backfill_surveillance()
        print(f"Surveillance backfill complete: {rows} rows")
        return 0

    if args.command == "backfill-symbol-health":
        print("Backfilling symbol health snapshot...")
        rows = orchestrator.backfill_symbol_health()
        print(f"Symbol health backfill complete: {rows} rows")
        return 0

    if args.command == "populate-calendar":
        print("Populating full NSE calendar into dim_date...")
        count = orchestrator.populate_calendar()
        print(f"Calendar populated: {count} dates updated/inserted.")
        return 0

    if args.command == "rebuild-price":
        try:
            start_d = date.fromisoformat(args.start)
            end_d = date.fromisoformat(args.end)
        except ValueError as exc:
            print(f"Error: Invalid date format: {exc}", file=sys.stderr)
            return 1
        print(f"Starting price rebuild from {start_d} to {end_d} via {args.source}...")
        res = orchestrator.rebuild_price(
            start_date=start_d,
            end_date=end_d,
            cache_dir=args.cache_dir,
        )
        print("Price rebuild complete:")
        print(f"  Files parsed: {res['files_parsed']}")
        print(f"  Rows deleted: {res['rows_deleted']}")
        print(f"  Rows inserted: {res['rows_inserted']}")
        print(f"  Dates processed: {res['dates_processed']}")
        return 0

    if args.command == "rebuild-ta":
        try:
            start_d = date.fromisoformat(args.start)
            end_d = date.fromisoformat(args.end)
        except ValueError as exc:
            print(f"Error: Invalid date format: {exc}", file=sys.stderr)
            return 1
        print(f"Starting TA rebuild from {start_d} to {end_d} via {args.source}...")
        res = orchestrator.rebuild_ta(
            start_date=start_d,
            end_date=end_d,
            max_workers=args.workers,
        )
        print("TA rebuild complete:")
        print(f"  Symbols processed: {res['symbols_processed']}")
        print(f"  Rows deleted: {res['rows_deleted']}")
        print(f"  Rows inserted: {res['rows_inserted']}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
