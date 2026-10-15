import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data.PersistenceService import PersistenceService

logger = logging.getLogger(__name__)


class DataIndexManager:
    """
    Manages the master data index file (data_index.csv)
    Tracks: Symbol, Exchange, Timeframe, Start/End Date, TA/ML Status
    """

    INDEX_FILE = Path("data_index.csv")
    DATA_DIR = Path("user_data/stock_data/1d")
    RESULTS_FILE = PersistenceService.PERSISTENCE_FILE
    ML_MODELS_DIR = Path("user_data/models")

    def __init__(self):
        self.ensure_directories()

    def ensure_directories(self):
        """Ensure necessary directories exist"""
        self.DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
        self.ML_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    def infer_exchange(self, symbol):
        """Infer exchange from symbol suffix"""
        if symbol.endswith(".NS"):
            return "NSE"
        elif symbol.endswith(".BO"):
            return "BSE"
        else:
            # Default to NSE for now as most data is NSE
            return "NSE"

    def clean_symbol(self, symbol):
        """Remove suffix for matching"""
        return symbol.replace(".NS", "").replace(".BO", "")

    def get_ta_status(self):
        """Get set of symbols with technical indicator data on disk"""
        ta_symbols = set()
        indicator_dir = Path("user_data/indicators")
        if indicator_dir.exists():
            for f in indicator_dir.glob("*.pkl"):
                ta_symbols.add(f.stem.replace("_indicators", "").upper())

        # Fallback to checking SignalDatabase if available
        try:
            from src.analytics.SignalDatabase import SignalDatabase

            db = SignalDatabase()
            cursor = db.connection.execute(
                "SELECT DISTINCT symbol FROM signal_analytics"
            )
            for row in cursor.fetchall():
                ta_symbols.add(row["symbol"].upper())
        except Exception:
            pass

        return ta_symbols

    def get_ml_status(self):
        """Get set of symbols with trained ML models"""
        models = set()
        if self.ML_MODELS_DIR.exists():
            for f in self.ML_MODELS_DIR.glob("*.pkl"):
                # Filename: symbol_model.pkl or symbol_rf_v1.pkl
                # Infer symbol
                name = f.stem
                if "_model" in name:
                    symbol = name.split("_model")[0]
                    models.add(symbol.upper())
                elif "_rf_" in name:
                    symbol = name.split("_rf_")[0]
                    models.add(symbol.upper())
        return models

    def update_index(self):
        """Regenerate the data index"""
        print("🔄 Updating Data Index...")

        files = list(self.DATA_DIR.glob("*.parquet"))
        if not files:
            print("⚠️  No data files found to index.")
            return

        ta_status = self.get_ta_status()
        ml_status = self.get_ml_status()

        index_data = []

        for f in files:
            try:
                # Basic File Info
                symbol_raw = f.stem
                exchange = self.infer_exchange(symbol_raw)
                symbol_clean = self.clean_symbol(symbol_raw)

                # modification time
                mtime = datetime.fromtimestamp(f.stat().st_mtime)

                # Read Parquet Metadata (Fast)
                # If pyarrow available, we can read metadata without full file?
                # For now read pandas (might be slow for huge files, but safe)
                df = pd.read_parquet(f)

                if df.empty:
                    continue

                start_date = df.index.min()
                end_date = df.index.max()
                rows = len(df)

                # Status checks
                is_ta_updated = "Yes" if symbol_clean in ta_status else "No"
                is_ml_ready = "Yes" if symbol_clean in ml_status else "No"

                index_data.append(
                    {
                        "Symbol": symbol_clean,
                        "Exchange": exchange,
                        "Timeframe": "1d",  # Currently only scanning 1d folder
                        "Start Date": start_date.date()
                        if hasattr(start_date, "date")
                        else start_date,
                        "End Date": end_date.date()
                        if hasattr(end_date, "date")
                        else end_date,
                        "Rows": rows,
                        "Last Modified": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                        "TA Updated": is_ta_updated,
                        "ML Ready": is_ml_ready,
                    }
                )

            except Exception as e:
                logger.error(f"Error indexing {f.name}: {e}")

        if index_data:
            df_index = pd.DataFrame(index_data)
            df_index.sort_values(by="Symbol", inplace=True)
            df_index.to_csv(self.INDEX_FILE, index=False)
            print(
                f"✅ Data Index updated: {len(df_index)} records saved to {self.INDEX_FILE}"
            )
        else:
            print("⚠️  No valid records found.")
