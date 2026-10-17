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
