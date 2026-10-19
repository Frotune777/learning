"""Warehouse loader for dimension seeding and historical fact backfill."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.platform.exceptions import PlatformError
from src.platform.loaders.master_enrichment import MasterEnrichmentLoader
from src.platform.loaders.staging import StagingLoader
from src.platform.loaders.surveillance import fetch_asm_list, fetch_esm_list, fetch_gsm_list
from src.platform.repositories.symbol_repo import SymbolRepo

LOGGER = logging.getLogger(__name__)


class WarehouseLoader:
    """Manages seeding dimensions and backfilling facts in DuckDB warehouse."""

    def __init__(self, db_path: Path | str = "data/warehouse.duckdb") -> None:
        self.db_path = Path(db_path)
        self.lock_file = self.db_path.parent / ".warehouse.lock"

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(self.db_path))

    def acquire_lock(self) -> None:
        """Acquire process-level mutual exclusion lock."""
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        if self.lock_file.exists():
            try:
                pid = int(self.lock_file.read_text().strip())
                import os

                os.kill(pid, 0)
                raise PlatformError(f"Warehouse database locked by active PID {pid}")
            except (OSError, ValueError):
                pass
        import os

        self.lock_file.write_text(str(os.getpid()))

    def release_lock(self) -> None:
        """Release process-level mutual exclusion lock."""
        if self.lock_file.exists():
            self.lock_file.unlink(missing_ok=True)

    def seed_dimensions(
        self,
        holidays_path: Path | str = "config/holidays.json",
        master_path: Path | str | None = None,
    ) -> dict[str, int]:
        """Seed all static dimensions (date, source, index, symbol, strategy)."""
        self.acquire_lock()
        conn = self._get_conn()
        counts: dict[str, int] = {}
        try:
            # 1. dim_source
            sources = [
                (
                    1,
                    "nse_bhavcopy",
                    "NSE Bhavcopy",
                    "Official National Stock Exchange Bhavcopy reports",
                ),
                (2, "fyers", "Fyers Broker API", "Fyers REST API historical and live data"),
                (3, "yfinance", "Yahoo Finance", "Yahoo finance historical daily candles"),
                (
                    4,
                    "nse_charts",
                    "NSE Charting API",
                    "NSE website live and intraday charting API",
                ),
                (
                    5,
                    "corporate_actions",
                    "Corporate Actions Inferred",
                    "Inferred or published corporate splits/bonuses",
                ),
            ]
            conn.begin()
            conn.executemany(
                """
                INSERT INTO dim_source
                    (source_sk, source_code, source_name, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (source_code) DO UPDATE SET
                    source_name = excluded.source_name,
                    description = excluded.description
                """,
                sources,
            )
            counts["dim_source"] = len(sources)

            # 2. dim_strategy
            strategies = [
                (1, "VCP", "Volatility Contraction Pattern", "BREAKOUT"),
                (2, "TTM_SQUEEZE", "TTM Squeeze Momentum", "MOMENTUM"),
                (3, "DUAL_SUPERTREND", "Dual SuperTrend Trend Following", "TREND"),
                (4, "LORENTZIAN", "Lorentzian Classification KNN", "ML"),
                (5, "RDX", "RDX Momentum Explosion", "MOMENTUM"),
                (6, "CANDLE_PATTERNS", "Classic Candlestick Patterns", "REVERSAL"),
                (7, "BUY_LOW", "Buy Low Sell High Dynamic Levels", "MEAN_REVERSION"),
                (8, "SMC_SWEEP", "Smart Money Concepts Liquidity Sweep", "INSTITUTIONAL"),
                (9, "ETF_SHOP", "ETF Shop Method Rotation", "ROTATION"),
                (10, "MOMENTUM_SQUEEZE", "Momentum Squeeze Breakout", "MOMENTUM"),
                (11, "MINERVINI", "Mark Minervini Trend Template", "TREND"),
            ]
            conn.executemany(
                """
                INSERT INTO dim_strategy
                    (strategy_sk, strategy_code, strategy_name, strategy_type)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (strategy_code) DO UPDATE SET
                    strategy_name = excluded.strategy_name,
                    strategy_type = excluded.strategy_type
                """,
                strategies,
            )
            counts["dim_strategy"] = len(strategies)

            # 3. dim_date (2000-01-01 to today+365)
            h_path = Path(holidays_path)
            holidays: set[str] = set()
            if h_path.is_file():
                h_data = json.loads(h_path.read_text(encoding="utf-8"))
                for v in h_data.values():
                    if isinstance(v, list):
                        holidays.update(v)

            start_d = date(1990, 1, 1)
            end_d = date.today() + timedelta(days=365)
            curr = start_d
            date_rows: list[tuple[Any, ...]] = []
            while curr <= end_d:
                d_sk = int(curr.strftime("%Y%m%d"))
                dow = curr.isoweekday()  # 1=Mon, 7=Sun
                is_weekday = dow <= 5
                d_str = curr.isoformat()
                is_holiday = d_str in holidays
                is_trading = is_weekday and not is_holiday
                holiday_name = "NSE Holiday" if is_holiday else None

                date_rows.append((
                    d_sk,
                    curr,
                    curr.year,
                    (curr.month - 1) // 3 + 1,
                    curr.month,
                    curr.isocalendar()[1],
                    dow,
                    is_weekday,
                    is_trading,
                    holiday_name,
                    "T+1",
                ))
                curr += timedelta(days=1)

            conn.executemany(
                """
                INSERT INTO dim_date (
                    date_sk, calendar_date, year, quarter, month, week_of_year,
                    day_of_week, is_weekday, is_trading_day, holiday_name, settlement_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (date_sk) DO UPDATE SET
                    is_trading_day = excluded.is_trading_day,
                    holiday_name = excluded.holiday_name
                """,
                date_rows,
            )
            counts["dim_date"] = len(date_rows)

            # 4. dim_index (from master columns)
            index_codes = [
                ("NIFTY_50", "Nifty 50 Index", "BROAD_MARKET", True),
                ("NIFTY_100", "Nifty 100 Index", "BROAD_MARKET", False),
                ("NIFTY_200", "Nifty 200 Index", "BROAD_MARKET", False),
                ("NIFTY_500", "Nifty 500 Index", "BROAD_MARKET", False),
                ("NIFTY_NEXT_50", "Nifty Next 50 Index", "BROAD_MARKET", False),
                ("NIFTY_MIDCAP_50", "Nifty Midcap 50 Index", "BROAD_MARKET", False),
                ("NIFTY_MIDCAP_100", "Nifty Midcap 100 Index", "BROAD_MARKET", False),
                ("NIFTY_MIDCAP_150", "Nifty Midcap 150 Index", "BROAD_MARKET", False),
                ("NIFTY_SMALLCAP_50", "Nifty Smallcap 50 Index", "BROAD_MARKET", False),
                ("NIFTY_SMALLCAP_100", "Nifty Smallcap 100 Index", "BROAD_MARKET", False),
                ("NIFTY_SMALLCAP_250", "Nifty Smallcap 250 Index", "BROAD_MARKET", False),
                ("NIFTY_BANK", "Nifty Bank Index", "SECTORAL", True),
                ("NIFTY_IT", "Nifty IT Index", "SECTORAL", True),
                ("NIFTY_PSU_BANK", "Nifty PSU Bank Index", "SECTORAL", False),
                ("NIFTY_FMCG", "Nifty FMCG Index", "SECTORAL", False),
                ("NIFTY_PHARMA", "Nifty Pharma Index", "SECTORAL", False),
                ("NIFTY_AUTO", "Nifty Auto Index", "SECTORAL", False),
                ("NIFTY_METAL", "Nifty Metal Index", "SECTORAL", False),
                ("NIFTY_REALTY", "Nifty Realty Index", "SECTORAL", False),
                ("NIFTY_MEDIA", "Nifty Media Index", "SECTORAL", False),
                ("NIFTY_INFRA", "Nifty Infra Index", "SECTORAL", False),
                ("NIFTY_ENERGY", "Nifty Energy Index", "SECTORAL", False),
                ("NIFTY_COMMODITIES", "Nifty Commodities Index", "THEMATIC", False),
                ("NIFTY_CONSUMPTION", "Nifty Consumption Index", "THEMATIC", False),
                ("NIFTY_FIN_SERVICE", "Nifty Financial Services Index", "SECTORAL", True),
            ]
            conn.executemany(
                """
                INSERT INTO dim_index
                    (index_sk, index_code, index_name, category, is_tradable_fo)
                VALUES (nextval('seq_index_sk'), ?, ?, ?, ?)
                ON CONFLICT (index_code) DO UPDATE SET
                    index_name = excluded.index_name,
                    category = excluded.category,
                    is_tradable_fo = excluded.is_tradable_fo
                """,
                [(c[0], c[1], c[2], c[3]) for c in index_codes],
            )
            conn.commit()
            counts["dim_index"] = len(index_codes)

            # 5. dim_symbol from latest master
            if master_path is None:
                masters = sorted(Path("data").glob("nse_equity_master_*.parquet"))
                if not masters:
                    raise PlatformError("No nse_equity_master_*.parquet found in data/")
                master_file = masters[-1]
            else:
                master_file = Path(master_path)

            master_df = pd.read_parquet(master_file)
            symbol_rows: list[tuple[Any, ...]] = []
            for _, row in master_df.iterrows():
                sym = str(row.get("Symbol", "")).strip().upper()
                if not sym:
                    continue
                srs = str(row.get("Series", "EQ")).strip()
                name = str(row.get("SecurityName", sym)).strip()
                sector = str(row.get("Band", "")).strip() or None
                symbol_rows.append((
                    sym,
                    None,  # ISIN will be enriched in B.5
                    name,
                    srs,
                    sector,
                    None,  # macro_sector
                    True,  # is_active
                    "HEALTHY",
                    date(2000, 1, 1),
                    date(9999, 12, 31),
                    True,
                ))

            conn.begin()
            conn.execute("DELETE FROM dim_symbol")
            conn.execute("DROP SEQUENCE IF EXISTS seq_symbol_sk")
            conn.execute("CREATE SEQUENCE seq_symbol_sk START 1")
            conn.executemany(
                """
                INSERT INTO dim_symbol (
                    symbol_sk, symbol, isin, company_name, series, sector, macro_sector,
                    is_active, classification, valid_from, valid_to, is_current
                ) VALUES (nextval('seq_symbol_sk'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                symbol_rows,
            )
            conn.commit()
            counts["dim_symbol"] = len(symbol_rows)

            return counts
        finally:
            conn.close()
            self.release_lock()

    def _get_symbol_map(self, conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
        """Fetch symbol -> symbol_sk mapping for current symbols."""
        query = "SELECT symbol, symbol_sk FROM dim_symbol WHERE is_current = TRUE"
        rows = conn.execute(query).fetchall()
        return {r[0]: r[1] for r in rows}

    def backfill_price_from_historical(
        self, hist_dir: Path | str = "data/historical/1d"
    ) -> dict[str, int]:
        """Backfill fact_price_daily directly from historical Parquet files."""
        self.acquire_lock()
        conn = self._get_conn()
        try:
            sym_map = self._get_symbol_map(conn)
            p = Path(hist_dir)
            files = sorted(p.glob("*.parquet"))

            inserted_rows = 0
            skipped_symbols = 0
            processed_symbols = 0

            for i, f in enumerate(files, 1):
                sym = f.stem.upper()
                if sym not in sym_map:
                    skipped_symbols += 1
                    LOGGER.debug("SKIPPED_UNIVERSE: %s not in dim_symbol", sym)
                    continue

                sym_sk = sym_map[sym]
                try:
                    df = pd.read_parquet(f)
                    if df.empty:
                        continue

                    # Reset index to get Date column
                    if "Date" not in df.columns and isinstance(df.index, pd.DatetimeIndex):
                        df = df.reset_index()
                    date_col = "Date" if "Date" in df.columns else df.columns[0]
                    df["trade_date"] = pd.to_datetime(df[date_col]).dt.date
                    df["date_sk"] = pd.to_datetime(df[date_col]).dt.strftime("%Y%m%d").astype(int)
                    df["symbol_sk"] = sym_sk
                    df["symbol"] = sym
                    df["series"] = "EQ"
                    df["open"] = pd.to_numeric(df["Open"], errors="coerce").fillna(0.0)
                    df["high"] = pd.to_numeric(df["High"], errors="coerce").fillna(0.0)
                    df["low"] = pd.to_numeric(df["Low"], errors="coerce").fillna(0.0)
                    df["close"] = pd.to_numeric(df["Close"], errors="coerce").fillna(0.0)
                    df["volume"] = (
                        pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype("int64")
                    )
                    df["last"] = df["close"]
                    df["prev_close"] = df["close"]
                    df["turnover"] = df["volume"] * df["close"]
                    df["trades"] = 0
                    df["vwap"] = df["close"]
                    df["source_sk"] = 1
                    df["batch_id"] = "historical_backfill"

                    cols = [
                        "symbol_sk", "date_sk", "symbol", "trade_date", "series",
                        "open", "high", "low", "close", "last", "prev_close",
                        "volume", "turnover", "trades", "vwap", "source_sk", "batch_id"
                    ]
                    sub_df = df[cols].drop_duplicates(subset=["symbol_sk", "date_sk"])

                    conn.register("batch_df", sub_df)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO fact_price_daily (
                            symbol_sk, date_sk, symbol, trade_date, series,
                            open, high, low, close, last, prev_close,
                            volume, turnover, trades, vwap, source_sk, batch_id
                        ) SELECT * FROM batch_df
                        """
                    )
                    conn.unregister("batch_df")

                    inserted_rows += len(sub_df)
                    processed_symbols += 1

                    if i % 100 == 0 or i == len(files):
                        LOGGER.info(
                            "Price backfill progress: %d/%d files processed (%d rows)",
                            i, len(files), inserted_rows,
                        )
                except Exception as exc:
                    LOGGER.warning("Failed price backfill for %s: %s", sym, exc)

            return {
                "rows_inserted": inserted_rows,
                "symbols_processed": processed_symbols,
                "skipped_universe": skipped_symbols,
            }
        finally:
            conn.close()
            self.release_lock()

    def backfill_ta_from_historical(
        self, hist_dir: Path | str = "data/historical/1d"
    ) -> dict[str, int]:
        """Backfill fact_ta_daily from historical Parquet indicator columns."""
        self.acquire_lock()
        conn = self._get_conn()
        try:
            sym_map = self._get_symbol_map(conn)
            p = Path(hist_dir)
            files = sorted(p.glob("*.parquet"))

            inserted_rows = 0
            skipped_symbols = 0
            processed_symbols = 0

            for i, f in enumerate(files, 1):
                sym = f.stem.upper()
                if sym not in sym_map:
                    skipped_symbols += 1
                    continue

                sym_sk = sym_map[sym]
                try:
                    df = pd.read_parquet(f)
                    if df.empty:
                        continue

                    if "Date" not in df.columns and isinstance(df.index, pd.DatetimeIndex):
                        df = df.reset_index()
                    date_col = "Date" if "Date" in df.columns else df.columns[0]
                    df["trade_date"] = pd.to_datetime(df[date_col]).dt.date
                    df["date_sk"] = pd.to_datetime(df[date_col]).dt.strftime("%Y%m%d").astype(int)
                    df["symbol_sk"] = sym_sk
                    df["symbol"] = sym
                    df["batch_id"] = "historical_backfill"

                    def _col(name: str) -> pd.Series:
                        if name in df.columns:
                            return pd.to_numeric(df[name], errors="coerce")
                        return pd.Series([None] * len(df), dtype="float64")

                    df["rsi_14"] = _col("RSI_14")
                    df["macd"] = _col("MACD")
                    df["macd_signal"] = _col("MACD_SIGNAL")
                    df["macd_hist"] = _col("MACD_HIST")
                    df["bb_upper"] = _col("BB_UPPER")
                    df["bb_middle"] = _col("BB_MIDDLE")
                    df["bb_lower"] = _col("BB_LOWER")
                    df["ema_20"] = _col("EMA_20")
                    df["ema_50"] = _col("EMA_50")
                    df["ema_100"] = _col("EMA_100")
                    df["ema_200"] = _col("EMA_200")
                    df["sma_20"] = _col("SMA_20")
                    df["sma_50"] = _col("SMA_50")
                    df["sma_100"] = _col("SMA_100")
                    df["sma_150"] = _col("SMA_150")
                    df["sma_200"] = _col("SMA_200")
                    df["atr_14"] = _col("ATR_14")
                    df["adx_14"] = _col("ADX_14")
                    df["plus_di_14"] = _col("PLUS_DI_14")
                    df["minus_di_14"] = _col("MINUS_DI_14")
                    df["cci_14"] = _col("CCI_14")
                    df["low_20d"] = _col("20D_LOW")
                    df["low_126d"] = _col("126D_LOW")
                    df["low_200d"] = _col("200D_LOW")
                    df["high_55d"] = _col("55D_HIGH")
                    df["high_52w"] = _col("52W_HIGH")
                    df["low_52w"] = _col("52W_LOW")
                    df["rsi_divergence"] = (
                        df["RSI_Divergence"].astype(str)
                        if "RSI_Divergence" in df.columns
                        else None
                    )
                    df["macd_divergence"] = (
                        df["MACD_Divergence"].astype(str)
                        if "MACD_Divergence" in df.columns
                        else None
                    )
                    df["weinstein_stage"] = _col("weinstein_stage")
                    df["ma_10w"] = _col("ma_10w")
                    df["ma_10w_slope"] = _col("ma_10w_slope")
                    df["nwe_upper"] = _col("nwe_upper")
                    df["nwe_lower"] = _col("nwe_lower")
                    df["vol_ratio_50"] = _col("vol_ratio_50")

                    cols = [
                        "symbol_sk", "date_sk", "symbol", "trade_date",
                        "rsi_14", "macd", "macd_signal", "macd_hist",
                        "bb_upper", "bb_middle", "bb_lower",
                        "ema_20", "ema_50", "ema_100", "ema_200",
                        "sma_20", "sma_50", "sma_100", "sma_150", "sma_200",
                        "atr_14", "adx_14", "plus_di_14", "minus_di_14", "cci_14",
                        "low_20d", "low_126d", "low_200d", "high_55d", "high_52w", "low_52w",
                        "rsi_divergence", "macd_divergence", "weinstein_stage",
                        "ma_10w", "ma_10w_slope", "nwe_upper", "nwe_lower", "vol_ratio_50",
                        "batch_id"
                    ]
                    sub_df = df[cols].drop_duplicates(subset=["symbol_sk", "date_sk"])

                    conn.register("batch_ta_df", sub_df)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO fact_ta_daily (
                            symbol_sk, date_sk, symbol, trade_date,
                            rsi_14, macd, macd_signal, macd_hist,
                            bb_upper, bb_middle, bb_lower,
                            ema_20, ema_50, ema_100, ema_200,
                            sma_20, sma_50, sma_100, sma_150, sma_200,
                            atr_14, adx_14, plus_di_14, minus_di_14, cci_14,
                            low_20d, low_126d, low_200d, high_55d, high_52w, low_52w,
                            rsi_divergence, macd_divergence, weinstein_stage,
                            ma_10w, ma_10w_slope, nwe_upper, nwe_lower, vol_ratio_50,
                            batch_id
                        ) SELECT * FROM batch_ta_df
                        """
                    )
                    conn.unregister("batch_ta_df")

                    inserted_rows += len(sub_df)
                    processed_symbols += 1

                    if i % 100 == 0 or i == len(files):
                        LOGGER.info(
                            "TA backfill progress: %d/%d files processed (%d rows)",
                            i, len(files), inserted_rows,
                        )
                except Exception as exc:
                    LOGGER.warning("Failed TA backfill for %s: %s", sym, exc)

            return {
                "rows_inserted": inserted_rows,
                "symbols_processed": processed_symbols,
                "skipped_universe": skipped_symbols,
            }
        finally:
            conn.close()
            self.release_lock()

    def backfill_dq_from_logs(
        self,
        runs_log_path: Path | str = "logs/dq/runs.jsonl",
        symbols_log_path: Path | str = "logs/dq/symbols.jsonl",
    ) -> dict[str, int]:
        """Backfill fact_dq_run and fact_dq_symbol from JSONL audit logs."""
        self.acquire_lock()
        conn = self._get_conn()
        counts: dict[str, int] = {"runs": 0, "symbols": 0}
        try:
            r_path = Path(runs_log_path)
            if r_path.is_file():
                run_rows: list[tuple[Any, ...]] = []
                with open(r_path, encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        item = json.loads(line)
                        run_rows.append((
                            item.get("run_id"),
                            item.get("timestamp"),
                            item.get("stage", "cli.dq-check"),
                            int(item.get("total_symbols", 0)),
                            int(item.get("passed_count", 0)),
                            int(item.get("failed_count", 0)),
                            float(item.get("failure_pct", 0.0)),
                            bool(item.get("halt_triggered", False)),
                            item.get("halt_reason"),
                            float(item.get("duration_ms", 0.0)),
                            int(item.get("inactive_count", 0)),
                            int(item.get("stale_count", 0)),
                            int(item.get("low_coverage_count", 0)),
                        ))

                if run_rows:
                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO fact_dq_run (
                            run_id, run_timestamp, stage, total_symbols, passed_count,
                            failed_count, failure_pct, halt_triggered, halt_reason,
                            duration_ms, inactive_count, stale_count, low_coverage_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        run_rows,
                    )
                    counts["runs"] = len(run_rows)

            s_path = Path(symbols_log_path)
            if s_path.is_file():
                sym_map = self._get_symbol_map(conn)
                sym_rows: list[tuple[Any, ...]] = []
                with open(s_path, encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        item = json.loads(line)
                        sym = item.get("symbol", "").strip().upper()
                        sym_rows.append((
                            item.get("run_id"),
                            sym_map.get(sym),
                            sym,
                            bool(item.get("passed", False)),
                            item.get("failure_reason"),
                            item.get("last_bar_date"),
                            item.get("row_count"),
                            (
                                float(item.get("coverage_pct", 0.0))
                                if item.get("coverage_pct") is not None
                                else None
                            ),
                            bool(item.get("has_stale_ta", False)),
                        ))

                if sym_rows:
                    conn.executemany(
                        """
                        INSERT INTO fact_dq_symbol (
                            dq_symbol_id, run_id, symbol_sk, symbol, passed,
                            failure_reason, last_bar_date, row_count, coverage_pct, has_stale_ta
                        ) VALUES (nextval('seq_dq_symbol_id'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        sym_rows,
                    )
                    counts["symbols"] = len(sym_rows)

            return counts
        finally:
            conn.close()
            self.release_lock()

    def _get_symbol_map_all(self, conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
        """Fetch symbol -> symbol_sk mapping for all symbols (current and non-current)."""
        query = "SELECT symbol, symbol_sk FROM dim_symbol"
        rows = conn.execute(query).fetchall()
        return {r[0]: r[1] for r in rows}

    def enrich_master(self, tiers: list[int] | None = None) -> dict[str, Any]:
        """Download, stage, and apply Tier 1 & 2 master enrichment via SCD2."""
        self.acquire_lock()
        conn = self._get_conn()
        try:
            landing_loader = MasterEnrichmentLoader(self.db_path.parent / "landing")
            staging_loader = StagingLoader(
                self.db_path.parent / "landing", self.db_path.parent / "staging"
            )

            LOGGER.info("Ingesting Tier 1 reference datasets...")
            landing_loader.ingest_equity_l()
            landing_loader.ingest_index_constituents()
            landing_loader.ingest_fo_mktlots()
            landing_loader.ingest_sec_list()

            LOGGER.info("Staging Tier 1 datasets...")
            staging_loader.stage_equity_master()
            staging_loader.stage_index_membership()
            staging_loader.stage_fo_flags()

            repo = SymbolRepo(conn)

            stg_masters = sorted(
                (self.db_path.parent / "staging" / "equity_master").glob("*/*.parquet")
            )
            stg_df = pd.read_parquet(stg_masters[-1]) if stg_masters else pd.DataFrame()

            inactive_file = Path("data/historical/inactive_symbols.csv")
            inactive_df = pd.read_csv(inactive_file) if inactive_file.is_file() else pd.DataFrame()
            masters = sorted(Path("data").glob("nse_equity_master_*.parquet"))
            master_syms = set()
            if masters:
                m_df_syms = pd.read_parquet(masters[-1])
                master_syms = set(m_df_syms["Symbol"].str.strip().str.upper())
            equity_l_syms = (
                set(stg_df["symbol"].str.strip().str.upper()) if not stg_df.empty else set()
            )
            active_known_syms = master_syms | equity_l_syms

            delisted_set = (
                set(inactive_df["symbol"].str.strip().str.upper()) - active_known_syms
                if not inactive_df.empty
                else set()
            )
            delisted_dates = (
                dict(zip(
                    inactive_df["symbol"].str.strip().str.upper(),
                    inactive_df["last_bar_date"],
                ))
                if not inactive_df.empty
                else {}
            )

            # Industry mapping from index constituent CSVs
            landing_indices = sorted(
                (self.db_path.parent / "landing" / "nse_index_constituents").glob("*/*/*.csv")
            )
            industry_map: dict[str, str] = {}
            for csv_f in landing_indices:
                try:
                    c_df = pd.read_csv(csv_f)
                    if "Symbol" in c_df.columns and "Industry" in c_df.columns:
                        for _, r in c_df.iterrows():
                            s = str(r["Symbol"]).strip().upper()
                            ind = str(r["Industry"]).strip()
                            if s and ind and s not in industry_map:
                                industry_map[s] = ind
                except Exception:
                    pass

            # Fallback ISIN map from landing bhavcopies and raw
            isin_map: dict[str, str] = {}
            bh_files = sorted(
                (self.db_path.parent / "landing" / "nse_bhavcopy").glob("*/*/*.csv")
            )
            if bh_files:
                try:
                    b_df = pd.read_csv(bh_files[-1], usecols=["TckrSymb", "ISIN"])
                    for _, r in b_df.dropna(subset=["ISIN"]).iterrows():
                        isin_map[str(r["TckrSymb"]).strip().upper()] = (
                            str(r["ISIN"]).strip().upper()
                        )
                except Exception:
                    pass

            isin_map.update({
                "ABGSEC": "INF209KC1134",
                "GSEC10ADD": "INF740KA1ZI7",
                "ASHIKA": "INE094B01013",
                "CCAVENUE": "INE483S01020",
                "HEG": "INE545A01024",
                "LASA": "INE670X01014",
                "SELMC": "INE105I01020",
                "SILLYMONKS": "INE203Y01012",
            })

            records_to_upsert: list[dict[str, Any]] = []
            seen_symbols: set[str] = set()

            if not stg_df.empty:
                for _, r in stg_df.iterrows():
                    sym = str(r["symbol"]).strip().upper()
                    if not sym:
                        continue
                    seen_symbols.add(sym)
                    srs = str(r.get("series", "EQ")).strip().upper()
                    isin = str(r.get("isin", "")).strip().upper() or isin_map.get(sym)
                    sec = industry_map.get(sym)
                    records_to_upsert.append({
                        "symbol": sym,
                        "isin": isin,
                        "company_name": str(r.get("company_name", sym)).strip(),
                        "series": srs,
                        "sector": sec,
                        "macro_sector": None,
                        "is_active": True,
                        "classification": "HEALTHY",
                        "is_current": True,
                    })

            masters = sorted(Path("data").glob("nse_equity_master_*.parquet"))
            if masters:
                m_df = pd.read_parquet(masters[-1])
                for _, r in m_df.iterrows():
                    sym = str(r["Symbol"]).strip().upper()
                    if not sym or sym in seen_symbols:
                        continue
                    seen_symbols.add(sym)
                    srs = str(r.get("Series", "EQ")).strip().upper()
                    isin = isin_map.get(sym) or f"IN_{sym}"
                    sec = industry_map.get(sym) or (str(r.get("Band", "")).strip() or None)
                    records_to_upsert.append({
                        "symbol": sym,
                        "isin": isin,
                        "company_name": str(r.get("SecurityName", sym)).strip(),
                        "series": srs,
                        "sector": sec,
                        "macro_sector": None,
                        "is_active": True,
                        "classification": "HEALTHY",
                        "is_current": True,
                    })

            for h_p in sorted(Path("data/historical/1d").glob("*.parquet")):
                sym = h_p.stem.upper()
                if sym in seen_symbols or sym in delisted_set:
                    continue
                seen_symbols.add(sym)
                isin = isin_map.get(sym) or f"IN_{sym}"
                records_to_upsert.append({
                    "symbol": sym,
                    "isin": isin,
                    "company_name": sym,
                    "series": "EQ",
                    "sector": industry_map.get(sym),
                    "macro_sector": None,
                    "is_active": True,
                    "classification": "HEALTHY",
                    "is_current": True,
                })

            for sym in sorted(delisted_set):
                seen_symbols.add(sym)
                d_date = delisted_dates.get(sym)
                d_val = pd.to_datetime(d_date).date() if pd.notna(d_date) else date(2025, 1, 1)
                records_to_upsert.append({
                    "symbol": sym,
                    "isin": isin_map.get(sym),
                    "company_name": sym,
                    "series": "EQ",
                    "sector": None,
                    "macro_sector": None,
                    "is_active": False,
                    "is_current": False,
                    "delisting_date": d_val,
                })

            return repo.upsert_scd2(records_to_upsert)
        finally:
            conn.close()
            self.release_lock()

    def _backfill_price_for_symbols(
        self,
        conn: duckdb.DuckDBPyConnection,
        sym_map: dict[str, int],
        files: list[Path],
    ) -> int:
        """Helper to backfill fact_price_daily for a specific set of Parquet files."""
        inserted = 0
        for f in files:
            sym = f.stem.upper()
            if sym not in sym_map:
                continue
            sym_sk = sym_map[sym]
            try:
                df = pd.read_parquet(f)
                if df.empty:
                    continue
                if "Date" not in df.columns and isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index()
                date_col = "Date" if "Date" in df.columns else df.columns[0]
                df["trade_date"] = pd.to_datetime(df[date_col]).dt.date
                df["date_sk"] = pd.to_datetime(df[date_col]).dt.strftime("%Y%m%d").astype(int)
                df["symbol_sk"] = sym_sk
                df["symbol"] = sym
                df["series"] = "EQ"
                df["open"] = pd.to_numeric(df["Open"], errors="coerce").fillna(0.0)
                df["high"] = pd.to_numeric(df["High"], errors="coerce").fillna(0.0)
                df["low"] = pd.to_numeric(df["Low"], errors="coerce").fillna(0.0)
                df["close"] = pd.to_numeric(df["Close"], errors="coerce").fillna(0.0)
                df["volume"] = (
                    pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype("int64")
                )
                df["last"] = df["close"]
                df["prev_close"] = df["close"]
                df["turnover"] = df["volume"] * df["close"]
                df["trades"] = 0
                df["vwap"] = df["close"]
                df["source_sk"] = 1
                df["batch_id"] = "historical_backfill"

                cols = [
                    "symbol_sk", "date_sk", "symbol", "trade_date", "series",
                    "open", "high", "low", "close", "last", "prev_close",
                    "volume", "turnover", "trades", "vwap", "source_sk", "batch_id"
                ]
                sub_df = df[cols].drop_duplicates(subset=["symbol_sk", "date_sk"])

                conn.register("batch_df", sub_df)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO fact_price_daily (
                        symbol_sk, date_sk, symbol, trade_date, series,
                        open, high, low, close, last, prev_close,
                        volume, turnover, trades, vwap, source_sk, batch_id
                    ) SELECT * FROM batch_df
                    """
                )
                conn.unregister("batch_df")
                inserted += len(sub_df)
            except Exception as exc:
                LOGGER.warning("Failed backfilling price for %s: %s", sym, exc)
        return inserted

    def _backfill_ta_for_symbols(
        self,
        conn: duckdb.DuckDBPyConnection,
        sym_map: dict[str, int],
        files: list[Path],
    ) -> int:
        """Helper to backfill fact_ta_daily for a specific set of Parquet files."""
        inserted = 0
        for f in files:
            sym = f.stem.upper()
            if sym not in sym_map:
                continue
            sym_sk = sym_map[sym]
            try:
                df = pd.read_parquet(f)
                if df.empty:
                    continue
                if "Date" not in df.columns and isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index()
                date_col = "Date" if "Date" in df.columns else df.columns[0]
                df["trade_date"] = pd.to_datetime(df[date_col]).dt.date
                df["date_sk"] = pd.to_datetime(df[date_col]).dt.strftime("%Y%m%d").astype(int)
                df["symbol_sk"] = sym_sk
                df["symbol"] = sym

                def _col(name: str) -> pd.Series:
                    if name in df.columns:
                        return pd.to_numeric(df[name], errors="coerce")
                    return pd.Series([None] * len(df), dtype="float64")

                df["rsi_14"] = _col("RSI_14")
                df["macd"] = _col("MACD")
                df["macd_signal"] = _col("MACD_SIGNAL")
                df["macd_hist"] = _col("MACD_HIST")
                df["bb_upper"] = _col("BB_UPPER")
                df["bb_middle"] = _col("BB_MIDDLE")
                df["bb_lower"] = _col("BB_LOWER")
                df["ema_20"] = _col("EMA_20")
                df["ema_50"] = _col("EMA_50")
                df["ema_100"] = _col("EMA_100")
                df["ema_200"] = _col("EMA_200")
                df["sma_20"] = _col("SMA_20")
                df["sma_50"] = _col("SMA_50")
                df["sma_100"] = _col("SMA_100")
                df["sma_150"] = _col("SMA_150")
                df["sma_200"] = _col("SMA_200")
                df["atr_14"] = _col("ATR_14")
                df["adx_14"] = _col("ADX_14")
                df["plus_di_14"] = _col("PLUS_DI_14")
                df["minus_di_14"] = _col("MINUS_DI_14")
                df["cci_14"] = _col("CCI_14")
                df["low_20d"] = _col("20D_LOW")
                df["low_126d"] = _col("126D_LOW")
                df["low_200d"] = _col("200D_LOW")
                df["high_55d"] = _col("55D_HIGH")
                df["high_52w"] = _col("52W_HIGH")
                df["low_52w"] = _col("52W_LOW")
                df["rsi_divergence"] = (
                    df["RSI_Divergence"].astype(str)
                    if "RSI_Divergence" in df.columns
                    else None
                )
                df["macd_divergence"] = (
                    df["MACD_Divergence"].astype(str)
                    if "MACD_Divergence" in df.columns
                    else None
                )
                df["weinstein_stage"] = _col("weinstein_stage")
                df["ma_10w"] = _col("ma_10w")
                df["ma_10w_slope"] = _col("ma_10w_slope")
                df["nwe_upper"] = _col("nwe_upper")
                df["nwe_lower"] = _col("nwe_lower")
                df["vol_ratio_50"] = _col("vol_ratio_50")
                df["batch_id"] = "historical_backfill"

                cols = [
                    "symbol_sk", "date_sk", "symbol", "trade_date",
                    "rsi_14", "macd", "macd_signal", "macd_hist",
                    "bb_upper", "bb_middle", "bb_lower",
                    "ema_20", "ema_50", "ema_100", "ema_200",
                    "sma_20", "sma_50", "sma_100", "sma_150", "sma_200",
                    "atr_14", "adx_14", "plus_di_14", "minus_di_14", "cci_14",
                    "low_20d", "low_126d", "low_200d", "high_55d", "high_52w", "low_52w",
                    "rsi_divergence", "macd_divergence", "weinstein_stage",
                    "ma_10w", "ma_10w_slope", "nwe_upper", "nwe_lower", "vol_ratio_50",
                    "batch_id"
                ]
                sub_df = df[cols].drop_duplicates(subset=["symbol_sk", "date_sk"])

                conn.register("batch_ta_df", sub_df)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO fact_ta_daily (
                        symbol_sk, date_sk, symbol, trade_date,
                        rsi_14, macd, macd_signal, macd_hist,
                        bb_upper, bb_middle, bb_lower,
                        ema_20, ema_50, ema_100, ema_200,
                        sma_20, sma_50, sma_100, sma_150, sma_200,
                        atr_14, adx_14, plus_di_14, minus_di_14, cci_14,
                        low_20d, low_126d, low_200d, high_55d, high_52w, low_52w,
                        rsi_divergence, macd_divergence, weinstein_stage,
                        ma_10w, ma_10w_slope, nwe_upper, nwe_lower, vol_ratio_50,
                        batch_id
                    ) SELECT * FROM batch_ta_df
                    """
                )
                conn.unregister("batch_ta_df")
                inserted += len(sub_df)
            except Exception as exc:
                LOGGER.warning("Failed backfilling TA for %s: %s", sym, exc)
        return inserted

    def backfill_populations(
        self, hist_dir: Path | str = "data/historical/1d"
    ) -> dict[str, Any]:
        """Backfill fact_price_daily & fact_ta_daily for Pop 2 (active) and Pop 3 (delisted)."""
        self.acquire_lock()
        conn = self._get_conn()
        try:
            sym_map = self._get_symbol_map_all(conn)
            p = Path(hist_dir)

            inactive_f = Path("data/historical/inactive_symbols.csv")
            delisted_set = (
                set(pd.read_csv(inactive_f)["symbol"].str.upper())
                if inactive_f.is_file()
                else set()
            )

            masters = sorted(Path("data").glob("nse_equity_master_*.parquet"))
            master = pd.read_parquet(masters[-1])
            master_syms = set(master["Symbol"].str.upper())

            all_files = {f.stem.upper(): f for f in p.glob("*.parquet")}
            skipped_files = set(all_files.keys()) - master_syms

            pop2_syms = sorted(list(skipped_files - delisted_set))
            pop3_syms = sorted(list(skipped_files & delisted_set))

            pop2_price = self._backfill_price_for_symbols(
                conn, sym_map, [all_files[s] for s in pop2_syms if s in all_files]
            )
            pop3_price = self._backfill_price_for_symbols(
                conn, sym_map, [all_files[s] for s in pop3_syms if s in all_files]
            )

            pop2_ta = self._backfill_ta_for_symbols(
                conn, sym_map, [all_files[s] for s in pop2_syms if s in all_files]
            )
            pop3_ta = self._backfill_ta_for_symbols(
                conn, sym_map, [all_files[s] for s in pop3_syms if s in all_files]
            )

            return {
                "pop2_active": {
                    "symbols": len(pop2_syms),
                    "price_rows": pop2_price,
                    "ta_rows": pop2_ta,
                },
                "pop3_delisted": {
                    "symbols": len(pop3_syms),
                    "price_rows": pop3_price,
                    "ta_rows": pop3_ta,
                },
            }
        finally:
            conn.close()
            self.release_lock()

    def backfill_index_membership(self) -> int:
        """Backfill fact_index_membership from staged index constituents."""
        self.acquire_lock()
        conn = self._get_conn()
        try:
            stg_files = sorted(
                (self.db_path.parent / "staging" / "index_membership").glob("*/*.parquet")
            )
            if not stg_files:
                return 0
            df = pd.read_parquet(stg_files[-1])
            if df.empty:
                return 0

            idx_rows = conn.execute("SELECT index_code, index_sk FROM dim_index").fetchall()
            idx_map = {r[0]: r[1] for r in idx_rows}

            sym_rows = conn.execute(
                "SELECT symbol, symbol_sk FROM dim_symbol WHERE is_current = TRUE"
            ).fetchall()
            sym_map = {r[0]: r[1] for r in sym_rows}

            membership_rows: list[tuple[Any, ...]] = []
            today_d = date.today()

            for _, r in df.iterrows():
                idx_code = str(r["index_code"]).strip().upper()
                sym = str(r["symbol"]).strip().upper()
                if idx_code in idx_map and sym in sym_map:
                    idx_sk = idx_map[idx_code]
                    sym_sk = sym_map[sym]
                    membership_rows.append((
                        idx_sk,
                        sym_sk,
                        None,
                        today_d,
                        date(9999, 12, 31),
                        str(r.get("batch_id", "tier1_index")),
                    ))

            if membership_rows:
                conn.begin()
                conn.execute("DELETE FROM fact_index_membership")
                conn.executemany(
                    """
                    INSERT INTO fact_index_membership (
                        membership_id, index_sk, symbol_sk, weight, valid_from, valid_to, batch_id
                    ) VALUES (nextval('seq_membership_id'), ?, ?, ?, ?, ?, ?)
                    """,
                    membership_rows,
                )
                conn.commit()
            return len(membership_rows)
        finally:
            conn.close()
            self.release_lock()

    def backfill_delivery_from_staging(self) -> int:
        """Backfill fact_delivery_daily from staged delivery data (e.g. sec_bhavdata_full)."""
        self.acquire_lock()
        conn = self._get_conn()
        try:
            stg_files = sorted(
                (self.db_path.parent / "staging" / "delivery_daily").glob("*/*.parquet")
            )
            if not stg_files:
                landing_loader = MasterEnrichmentLoader(self.db_path.parent / "landing")
                staging_loader = StagingLoader(
                    self.db_path.parent / "landing", self.db_path.parent / "staging"
                )
                landing_loader.ingest_sec_bhavdata_full(date(2026, 10, 16))
                staging_loader.stage_delivery_daily()
                stg_files = sorted(
                    (self.db_path.parent / "staging" / "delivery_daily").glob("*/*.parquet")
                )

            sym_map = self._get_symbol_map(conn)
            inserted = 0
            for sf in stg_files:
                df = pd.read_parquet(sf)
                if df.empty:
                    continue
                rows: list[tuple[Any, ...]] = []
                for _, r in df.iterrows():
                    sym = str(r["symbol"]).strip().upper()
                    if sym not in sym_map:
                        continue
                    sym_sk = sym_map[sym]
                    t_date = pd.to_datetime(r["trade_date"]).date()
                    d_sk = int(t_date.strftime("%Y%m%d"))
                    trd_qty = int(r["traded_qty"]) if pd.notna(r["traded_qty"]) else 0
                    del_qty = (
                        int(r["deliverable_qty"]) if pd.notna(r["deliverable_qty"]) else None
                    )
                    del_pct = (
                        float(r["delivery_pct"]) if pd.notna(r["delivery_pct"]) else None
                    )
                    rows.append((
                        sym_sk, d_sk, sym, t_date, str(r.get("series", "EQ")),
                        trd_qty, del_qty, del_pct, 1, str(r.get("batch_id", "delivery_backfill")),
                    ))

                if rows:
                    conn.executemany(
                        """
                        INSERT INTO fact_delivery_daily (
                            symbol_sk, date_sk, symbol, trade_date, series,
                            traded_qty, deliverable_qty, delivery_pct, source_sk, batch_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (symbol_sk, date_sk) DO UPDATE SET
                            traded_qty = excluded.traded_qty,
                            deliverable_qty = excluded.deliverable_qty,
                            delivery_pct = excluded.delivery_pct
                        """,
                        rows,
                    )
                    inserted += len(rows)
            return inserted
        finally:
            conn.close()
            self.release_lock()

    def backfill_symbol_health(self) -> int:
        """Backfill fact_symbol_health today for all is_current=TRUE symbols."""
        self.acquire_lock()
        conn = self._get_conn()
        try:
            today_d = date.today()
            d_sk = int(today_d.strftime("%Y%m%d"))

            curr_syms = conn.execute(
                "SELECT symbol_sk, symbol, is_active FROM dim_symbol WHERE is_current = TRUE"
            ).fetchall()

            reg_file = Path("data/historical/sync_registry_1d.parquet")
            reg_map: dict[str, dict[str, Any]] = {}
            if reg_file.is_file():
                reg_df = pd.read_parquet(reg_file)
                for _, r in reg_df.iterrows():
                    reg_map[str(r["symbol"]).strip().upper()] = dict(r)

            rows: list[tuple[Any, ...]] = []
            for sym_sk, sym, is_act in curr_syms:
                reg_entry = reg_map.get(sym, {})
                last_b_date = reg_entry.get("last_bar_date")
                l_date = pd.to_datetime(last_b_date).date() if pd.notna(last_b_date) else None
                cls = "HEALTHY" if is_act else "DELISTED"
                days_quiet = 0
                if l_date:
                    days_quiet = (today_d - l_date).days
                    if days_quiet > 30 and is_act:
                        cls = "STALE"

                rows.append((
                    sym_sk, d_sk, cls, days_quiet, l_date,
                    "Phase B.5 automated health assessment",
                ))

            if rows:
                conn.begin()
                conn.execute("DELETE FROM fact_symbol_health")
                conn.executemany(
                    """
                    INSERT INTO fact_symbol_health (
                        health_id, symbol_sk, date_sk, classification,
                        days_quiet, last_trade_date, notes
                    ) VALUES (nextval('seq_health_id'), ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.commit()
            return len(rows)
        finally:
            conn.close()
            self.release_lock()

    def backfill_surveillance_today(self) -> int:
        """Backfill fact_symbol_surveillance today for all is_current=TRUE symbols."""
        self.acquire_lock()
        conn = self._get_conn()
        try:
            today_d = date.today()
            d_sk = int(today_d.strftime("%Y%m%d"))

            asm_df = fetch_asm_list()
            gsm_df = fetch_gsm_list()
            esm_df = fetch_esm_list()

            surv_map: dict[str, tuple[str, str]] = {}
            for _, r in asm_df.iterrows():
                surv_map[str(r["symbol"]).upper()] = ("ASM", str(r.get("stage", "STAGE_1")))
            for _, r in gsm_df.iterrows():
                surv_map[str(r["symbol"]).upper()] = ("GSM", str(r.get("stage", "STAGE_1")))
            for _, r in esm_df.iterrows():
                surv_map[str(r["symbol"]).upper()] = ("ESM", str(r.get("stage", "STAGE_1")))

            curr_syms = conn.execute(
                "SELECT symbol_sk, symbol FROM dim_symbol WHERE is_current = TRUE"
            ).fetchall()

            rows: list[tuple[Any, ...]] = []
            for sym_sk, sym in curr_syms:
                if sym in surv_map:
                    s_type, s_stage = surv_map[sym]
                else:
                    s_type, s_stage = "NONE", "NONE"

                rows.append((
                    sym_sk, d_sk, s_type, s_stage, today_d, "daily_surveillance",
                ))

            if rows:
                conn.executemany(
                    """
                    INSERT INTO fact_symbol_surveillance (
                        surveillance_id, symbol_sk, date_sk, surveillance_type,
                        stage, effective_date, batch_id
                    ) VALUES (nextval('seq_surveillance_id'), ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            return len(rows)
        finally:
            conn.close()
            self.release_lock()

    def inventory_missing_historical(
        self, out_path: Path | str = "data/warehouse_missing_historical.csv"
    ) -> int:
        """Identify Pop 4 active symbols missing historical data and export CSV."""
        conn = self._get_conn()
        try:
            query = """
            SELECT symbol, isin, series
            FROM dim_symbol
            WHERE is_current = TRUE
              AND symbol NOT IN (SELECT DISTINCT symbol FROM fact_price_daily)
            ORDER BY symbol
            """
            rows = conn.execute(query).fetchall()
            df = pd.DataFrame(rows, columns=["symbol", "isin", "series"])
            df["reason"] = "NO_PARQUET"
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(p, index=False)
            return len(df)
        finally:
            conn.close()

