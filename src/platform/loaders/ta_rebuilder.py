"""Technical analysis rebuilder from warehouse fact_price_daily."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from src.nse_bhavcopy.ta_indicators import add_ta_indicators
from src.platform.loaders.warehouse import WarehouseLoader

LOGGER = logging.getLogger(__name__)


def compute_ta_for_symbol_df(
    sym_sk: int,
    symbol: str,
    df: pd.DataFrame,
    start_sk: int,
    end_sk: int,
) -> pd.DataFrame:
    """Compute TA indicators for one symbol's full price history, returning rows in range."""
    if df.empty or len(df) < 5:
        return pd.DataFrame()

    df = df.sort_values("trade_date").copy()
    df_indexed = df.set_index("trade_date")

    try:
        enriched = add_ta_indicators(df_indexed)
    except Exception as exc:
        LOGGER.warning("TA calculation failed for %s: %s", symbol, exc)
        return pd.DataFrame()

    # Reset index to get trade_date back as column
    enriched = enriched.reset_index()

    # Filter to date_sk in range
    enriched = enriched[(enriched["date_sk"] >= start_sk) & (enriched["date_sk"] <= end_sk)].copy()
    if enriched.empty:
        return pd.DataFrame()

    enriched["symbol_sk"] = sym_sk
    enriched["symbol"] = symbol
    enriched["batch_id"] = "ta_rebuild"

    # Map column names
    col_mapping = {
        "RSI_14": "rsi_14",
        "MACD": "macd",
        "MACD_SIGNAL": "macd_signal",
        "MACD_HIST": "macd_hist",
        "BB_UPPER": "bb_upper",
        "BB_MIDDLE": "bb_middle",
        "BB_LOWER": "bb_lower",
        "EMA_20": "ema_20",
        "EMA_50": "ema_50",
        "EMA_100": "ema_100",
        "EMA_200": "ema_200",
        "SMA_20": "sma_20",
        "SMA_50": "sma_50",
        "SMA_100": "sma_100",
        "SMA_150": "sma_150",
        "SMA_200": "sma_200",
        "ATR_14": "atr_14",
        "ADX_14": "adx_14",
        "PLUS_DI_14": "plus_di_14",
        "MINUS_DI_14": "minus_di_14",
        "CCI_14": "cci_14",
        "20D_LOW": "low_20d",
        "126D_LOW": "low_126d",
        "200D_LOW": "low_200d",
        "55D_HIGH": "high_55d",
        "52W_HIGH": "high_52w",
        "52W_LOW": "low_52w",
        "RSI_Divergence": "rsi_divergence",
        "MACD_Divergence": "macd_divergence",
    }

    for src_col, tgt_col in col_mapping.items():
        if src_col in enriched.columns:
            enriched[tgt_col] = enriched[src_col]
        else:
            enriched[tgt_col] = None

    # Calculate vol_ratio_50 if Volume present
    if "Volume" in enriched.columns:
        vol_s = df_indexed["Volume"]
        vol_50 = vol_s.rolling(50).mean()
        # map back
        vol_ratio_map = (vol_s / vol_50.replace(0, np.nan)).to_dict()
        enriched["vol_ratio_50"] = enriched["trade_date"].map(vol_ratio_map)
    else:
        enriched["vol_ratio_50"] = None

    enriched["weinstein_stage"] = None
    enriched["ma_10w"] = None
    enriched["ma_10w_slope"] = None
    enriched["nwe_upper"] = None
    enriched["nwe_lower"] = None

    target_cols = [
        "symbol_sk", "date_sk", "symbol", "trade_date",
        "rsi_14", "macd", "macd_signal", "macd_hist",
        "bb_upper", "bb_middle", "bb_lower",
        "ema_20", "ema_50", "ema_100", "ema_200",
        "sma_20", "sma_50", "sma_100", "sma_150", "sma_200",
        "atr_14", "adx_14", "plus_di_14", "minus_di_14", "cci_14",
        "low_20d", "low_126d", "low_200d", "high_55d", "high_52w", "low_52w",
        "rsi_divergence", "macd_divergence", "weinstein_stage",
        "ma_10w", "ma_10w_slope", "nwe_upper", "nwe_lower",
        "vol_ratio_50", "batch_id",
    ]
    return enriched[target_cols]


def rebuild_ta_from_warehouse(
    start_date: date = date(2020, 1, 1),
    end_date: date = date(2026, 10, 16),
    warehouse_loader: WarehouseLoader | None = None,
    max_workers: int = 8,
) -> dict[str, int]:
    """Rebuild fact_ta_daily from fact_price_daily across all symbols."""
    if warehouse_loader is None:
        warehouse_loader = WarehouseLoader()

    warehouse_loader.acquire_lock()
    conn = warehouse_loader._get_conn()

    start_sk = int(start_date.strftime("%Y%m%d"))
    end_sk = int(end_date.strftime("%Y%m%d"))

    try:
        conn.execute("DROP INDEX IF EXISTS idx_ta_daily_sym_date")
        conn.begin()
        del_res = conn.execute(
            f"DELETE FROM fact_ta_daily WHERE date_sk >= {start_sk} AND date_sk <= {end_sk}"
        )
        rows_deleted = del_res.fetchone()[0] if del_res else 0
        conn.commit()
        LOGGER.info("Deleted %d existing fact_ta_daily rows in range %s to %s", rows_deleted, start_date, end_date)

        # Load all symbols that have prices
        symbols_meta = conn.execute(
            "SELECT DISTINCT symbol_sk, symbol FROM fact_price_daily ORDER BY symbol"
        ).fetchall()
        total_symbols = len(symbols_meta)
        LOGGER.info("Found %d distinct symbols to compute TA for", total_symbols)

        # Load price data for all symbols
        all_prices = conn.execute(
            """
            SELECT symbol_sk, symbol, date_sk, trade_date,
                   open AS "Open", high AS "High", low AS "Low", close AS "Close", volume AS "Volume"
            FROM fact_price_daily
            ORDER BY symbol_sk, trade_date
            """
        ).df()

        grouped_prices = {
            s_sk: g for s_sk, g in all_prices.groupby("symbol_sk")
        }

        # Worker function for parallel execution
        def _worker(meta: tuple[int, str]) -> pd.DataFrame:
            s_sk, s_name = meta
            if s_sk not in grouped_prices:
                return pd.DataFrame()
            return compute_ta_for_symbol_df(
                sym_sk=s_sk,
                symbol=s_name,
                df=grouped_prices[s_sk],
                start_sk=start_sk,
                end_sk=end_sk,
            )

        insert_sql = """
        INSERT INTO fact_ta_daily (
            symbol_sk, date_sk, symbol, trade_date,
            rsi_14, macd, macd_signal, macd_hist,
            bb_upper, bb_middle, bb_lower,
            ema_20, ema_50, ema_100, ema_200,
            sma_20, sma_50, sma_100, sma_150, sma_200,
            atr_14, adx_14, plus_di_14, minus_di_14, cci_14,
            low_20d, low_126d, low_200d, high_55d, high_52w, low_52w,
            rsi_divergence, macd_divergence, weinstein_stage,
            ma_10w, ma_10w_slope, nwe_upper, nwe_lower,
            vol_ratio_50, batch_id
        )
        SELECT
            symbol_sk, date_sk, symbol, trade_date,
            rsi_14, macd, macd_signal, macd_hist,
            bb_upper, bb_middle, bb_lower,
            ema_20, ema_50, ema_100, ema_200,
            sma_20, sma_50, sma_100, sma_150, sma_200,
            atr_14, adx_14, plus_di_14, minus_di_14, cci_14,
            low_20d, low_126d, low_200d, high_55d, high_52w, low_52w,
            rsi_divergence, macd_divergence, weinstein_stage,
            ma_10w, ma_10w_slope, nwe_upper, nwe_lower,
            vol_ratio_50, batch_id
        FROM df_ta_batch
        ON CONFLICT (symbol_sk, date_sk) DO NOTHING
        """

        rows_inserted = 0
        symbols_processed = 0
        batch_results: list[pd.DataFrame] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for df_res in executor.map(_worker, symbols_meta):
                symbols_processed += 1
                if not df_res.empty:
                    batch_results.append(df_res)

                if len(batch_results) >= 100 or symbols_processed == total_symbols:
                    if batch_results:
                        combined = pd.concat(batch_results, ignore_index=True)
                        conn.begin()
                        conn.register("df_ta_batch", combined)
                        conn.execute(insert_sql)
                        conn.unregister("df_ta_batch")
                        conn.commit()
                        rows_inserted += len(combined)
                        batch_results.clear()
                    if symbols_processed % 100 == 0 or symbols_processed == total_symbols:
                        LOGGER.info("Processed %d/%d symbols (%d TA rows inserted)", symbols_processed, total_symbols, rows_inserted)

        LOGGER.info("Recreating secondary index idx_ta_daily_sym_date...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ta_daily_sym_date ON fact_ta_daily (symbol, trade_date)")

        LOGGER.info("TA rebuild complete: %d symbols processed, %d rows inserted", symbols_processed, rows_inserted)
        return {
            "symbols_processed": symbols_processed,
            "rows_inserted": rows_inserted,
            "rows_deleted": rows_deleted,
        }
    except Exception as exc:
        conn.rollback()
        LOGGER.exception("TA rebuild failed: %s", exc)
        raise
    finally:
        warehouse_loader.release_lock()
