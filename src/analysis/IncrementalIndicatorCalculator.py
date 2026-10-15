#!/usr/bin/env python3
"""
Incremental Indicator Calculator
Calculate technical indicators incrementally (O(1) per new bar)
With cache versioning and validation
"""

import hashlib
import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IncrementalIndicatorCalculator:
    """
    Calculate indicators incrementally with versioned cache

    Features:
    - Cache versioning with semantic versioning
    - Schema validation via hash
    - Corrupted pickle handling
    - Backward compatibility
    - O(1) complexity per new bar
    """

    CACHE_VERSION = "1.0.0"

    def __init__(self, cache_dir="user_data/indicators"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"Initialized IncrementalIndicatorCalculator (v{self.CACHE_VERSION})"
        )

    def get_indicators(
        self, symbol: str, data: pd.DataFrame, force_refresh: bool = False
    ) -> dict[str, Any]:
        """
        Get indicators with incremental calculation

        Args:
            symbol: Stock symbol
            data: OHLCV DataFrame
            force_refresh: Force full recalculation

        Returns:
            Dictionary of indicator values
        """
        cache_file = self.cache_dir / f"{symbol.lower()}_indicators.pkl"

        # Try to load cached state
        if not force_refresh and cache_file.exists():
            cached = self._load_cache(cache_file)

            if cached is not None:
                last_date = cached["last_date"]

                # Get new bars only
                new_data = data[data.index > last_date]

                if len(new_data) == 0:
                    logger.debug(f"{symbol}: Using cached indicators (up-to-date)")
                    return cached["indicators"]

                # Incremental update (O(1) per bar)
                logger.info(
                    f"{symbol}: Updating {len(new_data)} new bars incrementally"
                )
                indicators = self._update_incremental(cached["state"], new_data)

                # Save updated state
                self._save_cache(cache_file, indicators, data.index[-1])

                return indicators

        # Full calculation (first time or cache invalid)
        logger.info(f"{symbol}: Full calculation ({len(data)} bars)")
        indicators = self._calculate_full(data)

        # Save state for next update
        self._save_cache(cache_file, indicators, data.index[-1])

        return indicators

    def _load_cache(self, cache_file: Path) -> dict | None:
        """Load cache with version validation"""
        try:
            with open(cache_file, "rb") as f:
                cached = pickle.load(f)

            # Version check
            if cached.get("version") != self.CACHE_VERSION:
                logger.warning(
                    f"Cache version mismatch: {cached.get('version')} != {self.CACHE_VERSION}. "
                    "Rebuilding cache..."
                )
                return None

            # Schema validation
            if cached.get("schema_hash") != self._compute_schema_hash():
                logger.warning("Cache schema changed. Rebuilding cache...")
                return None

            # Integrity check
            if not self._validate_cache_integrity(cached):
                logger.error("Cache integrity check failed. Rebuilding...")
                return None

            return cached

        except (pickle.UnpicklingError, EOFError, AttributeError) as e:
            logger.error(f"Corrupted cache file: {e}. Rebuilding...")
            return None
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return None

    def _save_cache(self, cache_file: Path, indicators: dict, last_date: pd.Timestamp):
        """Save cache with version info"""
        cache_data = {
            "version": self.CACHE_VERSION,
            "schema_hash": self._compute_schema_hash(),
            "last_date": last_date,
            "indicators": indicators,
            "state": self._extract_state(indicators),
            "metadata": {
                "created_at": datetime.now(),
                "indicator_list": list(indicators.keys()),
            },
        }

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.debug(f"Saved cache: {cache_file}")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def _compute_schema_hash(self) -> str:
        """Compute hash of indicator schema for validation"""
        schema = {
            "indicators": ["supertrend", "obv", "rsi", "macd", "bollinger", "vwap"],
            "supertrend_params": {"period": 14, "multiplier": 2.0},
            "rsi_params": {"period": 14},
            "macd_params": {"fast": 12, "slow": 26, "signal": 9},
            "bollinger_params": {"period": 20, "std": 2.0},
            "vwap_params": {},
        }

        schema_str = json.dumps(schema, sort_keys=True)
        return hashlib.md5(schema_str.encode()).hexdigest()

    def _validate_cache_integrity(self, cached: dict) -> bool:
        """Validate cache data integrity"""
        required_keys = ["version", "last_date", "indicators", "state"]

        # Check required keys
        if not all(key in cached for key in required_keys):
            return False

        # Check indicators structure
        indicators = cached["indicators"]
        expected_indicators = ["supertrend", "obv", "rsi", "macd", "bollinger", "vwap"]

        if not all(ind in indicators for ind in expected_indicators):
            return False

        # Check state structure
        state = cached["state"]
        if not isinstance(state, dict):
            return False

        return True

    def _extract_state(self, indicators: dict) -> dict:
        """Extract state needed for incremental updates"""
        return {
            "supertrend": indicators["supertrend"],
            "obv": indicators["obv"],
            "rsi": indicators["rsi"],
            "macd": indicators["macd"],
            "bollinger": indicators["bollinger"],
            "vwap": indicators["vwap"],
        }

    def _calculate_full(self, data: pd.DataFrame) -> dict[str, Any]:
        """Full calculation of all indicators"""
        indicators = {}

        # SuperTrend
        indicators["supertrend"] = self._calculate_supertrend_full(data)

        # OBV
        indicators["obv"] = self._calculate_obv_full(data)

        # RSI
        indicators["rsi"] = self._calculate_rsi_full(data)

        # MACD
        indicators["macd"] = self._calculate_macd_full(data)

        # Bollinger Bands
        indicators["bollinger"] = self._calculate_bollinger_full(data)

        # VWAP
        indicators["vwap"] = self._calculate_vwap_full(data)

        return indicators

    def _update_incremental(
        self, prev_state: dict, new_data: pd.DataFrame
    ) -> dict[str, Any]:
        """Update indicators incrementally (O(1) per bar)"""
        indicators = prev_state.copy()

        for idx, row in new_data.iterrows():
            # SuperTrend (O(1))
            indicators["supertrend"] = self._update_supertrend(
                indicators["supertrend"], row
            )

            # OBV (O(1))
            indicators["obv"] = self._update_obv(indicators["obv"], row)

            # RSI (O(1))
            indicators["rsi"] = self._update_rsi(indicators["rsi"], row)

            # MACD (O(1))
            indicators["macd"] = self._update_macd(indicators["macd"], row)

            # Bollinger Bands (O(1))
            indicators["bollinger"] = self._update_bollinger(
                indicators["bollinger"], row
            )

            # VWAP (O(1))
            indicators["vwap"] = self._update_vwap(indicators["vwap"], row)

        return indicators

    # ===== Full Calculation Methods =====

    def _calculate_supertrend_full(self, data: pd.DataFrame) -> dict:
        """Calculate SuperTrend from scratch"""
        period = 14
        multiplier = 2.0

        # Calculate ATR
        high_low = data["High"] - data["Low"]
        high_close = np.abs(data["High"] - data["Close"].shift())
        low_close = np.abs(data["Low"] - data["Close"].shift())

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(span=period, adjust=False).mean()

        # Calculate bands
        hl_avg = (data["High"] + data["Low"]) / 2
        upper = hl_avg + (multiplier * atr)
        lower = hl_avg - (multiplier * atr)

        # Determine trend
        trend = pd.Series(index=data.index, dtype=int)
        trend.iloc[0] = 1

        for i in range(1, len(data)):
            if data["Close"].iloc[i] > upper.iloc[i - 1]:
                trend.iloc[i] = 1
            elif data["Close"].iloc[i] < lower.iloc[i - 1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i - 1]

        return {
            "atr": atr.iloc[-1],
            "upper": upper.iloc[-1],
            "lower": lower.iloc[-1],
            "trend": trend.iloc[-1],
            "prev_close": data["Close"].iloc[-1],
        }

    def _calculate_obv_full(self, data: pd.DataFrame) -> dict:
        """Calculate OBV from scratch"""
        obv = pd.Series(index=data.index, dtype=float)
        obv.iloc[0] = data["Volume"].iloc[0]

        for i in range(1, len(data)):
            if data["Close"].iloc[i] > data["Close"].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] + data["Volume"].iloc[i]
            elif data["Close"].iloc[i] < data["Close"].iloc[i - 1]:
                obv.iloc[i] = obv.iloc[i - 1] - data["Volume"].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i - 1]

        return {"value": obv.iloc[-1], "prev_close": data["Close"].iloc[-1]}

    def _calculate_rsi_full(self, data: pd.DataFrame) -> dict:
        """Calculate RSI from scratch"""
        period = 14

        delta = data["Close"].diff()
        gain = (delta.where(delta > 0, 0)).ewm(span=period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(span=period, adjust=False).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return {
            "value": rsi.iloc[-1],
            "avg_gain": gain.iloc[-1],
            "avg_loss": loss.iloc[-1],
            "prev_close": data["Close"].iloc[-1],
        }

    def _calculate_macd_full(self, data: pd.DataFrame) -> dict:
        """Calculate MACD from scratch"""
        fast_ema = data["Close"].ewm(span=12, adjust=False).mean()
        slow_ema = data["Close"].ewm(span=26, adjust=False).mean()

        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            "fast_ema": fast_ema.iloc[-1],
            "slow_ema": slow_ema.iloc[-1],
            "macd_line": macd_line.iloc[-1],
            "signal_line": signal_line.iloc[-1],
            "histogram": histogram.iloc[-1],
        }

    def _calculate_bollinger_full(self, data: pd.DataFrame) -> dict:
        """Calculate Bollinger Bands from scratch"""
        period = 20
        std_mult = 2.0

        sma = data["Close"].rolling(window=period).mean()
        std = data["Close"].rolling(window=period).std()

        upper = sma + (std_mult * std)
        lower = sma - (std_mult * std)

        # Store last 'period' values for exact rolling calculation
        rolling_buffer = list(data["Close"].iloc[-period:].values)

        return {
            "sma": sma.iloc[-1],
            "upper": upper.iloc[-1],
            "lower": lower.iloc[-1],
            "std": std.iloc[-1],
            "rolling_buffer": rolling_buffer,  # Exact rolling window
            "period": period,
        }

    def _calculate_vwap_full(self, data: pd.DataFrame) -> dict:
        """Calculate VWAP from scratch"""
        typical_price = (data["High"] + data["Low"] + data["Close"]) / 3
        tp_volume = typical_price * data["Volume"]

        cum_tp_volume = tp_volume.sum()
        cum_volume = data["Volume"].sum()

        vwap = cum_tp_volume / cum_volume if cum_volume > 0 else typical_price.iloc[-1]

        return {"vwap": vwap, "cum_tp_volume": cum_tp_volume, "cum_volume": cum_volume}

    # ===== Incremental Update Methods =====

    def _update_supertrend(self, prev_st: dict, new_bar: pd.Series) -> dict:
        """Update SuperTrend incrementally (O(1))"""
        # Calculate True Range
        tr = max(
            new_bar["High"] - new_bar["Low"],
            abs(new_bar["High"] - prev_st["prev_close"]),
            abs(new_bar["Low"] - prev_st["prev_close"]),
        )

        # Update ATR (EMA)
        alpha = 2 / (14 + 1)
        atr = alpha * tr + (1 - alpha) * prev_st["atr"]

        # Update bands
        multiplier = 2.0
        hl_avg = (new_bar["High"] + new_bar["Low"]) / 2
        upper = hl_avg + multiplier * atr
        lower = hl_avg - multiplier * atr

        # Update trend
        if new_bar["Close"] > prev_st["upper"]:
            trend = 1
        elif new_bar["Close"] < prev_st["lower"]:
            trend = -1
        else:
            trend = prev_st["trend"]

        return {
            "atr": atr,
            "upper": upper,
            "lower": lower,
            "trend": trend,
            "prev_close": new_bar["Close"],
        }

    def _update_obv(self, prev_obv: dict, new_bar: pd.Series) -> dict:
        """Update OBV incrementally (O(1))"""
        if new_bar["Close"] > prev_obv["prev_close"]:
            obv = prev_obv["value"] + new_bar["Volume"]
        elif new_bar["Close"] < prev_obv["prev_close"]:
            obv = prev_obv["value"] - new_bar["Volume"]
        else:
            obv = prev_obv["value"]

        return {"value": obv, "prev_close": new_bar["Close"]}

    def _update_rsi(self, prev_rsi: dict, new_bar: pd.Series) -> dict:
        """Update RSI incrementally (O(1))"""
        delta = new_bar["Close"] - prev_rsi["prev_close"]

        alpha = 2 / (14 + 1)

        if delta > 0:
            avg_gain = alpha * delta + (1 - alpha) * prev_rsi["avg_gain"]
            avg_loss = (1 - alpha) * prev_rsi["avg_loss"]
        else:
            avg_gain = (1 - alpha) * prev_rsi["avg_gain"]
            avg_loss = alpha * abs(delta) + (1 - alpha) * prev_rsi["avg_loss"]

        rs = avg_gain / avg_loss if avg_loss > 0 else 0
        rsi = 100 - (100 / (1 + rs)) if avg_loss > 0 else 100

        return {
            "value": rsi,
            "avg_gain": avg_gain,
            "avg_loss": avg_loss,
            "prev_close": new_bar["Close"],
        }

    def _update_macd(self, prev_macd: dict, new_bar: pd.Series) -> dict:
        """Update MACD incrementally (O(1))"""
        fast_alpha = 2 / (12 + 1)
        slow_alpha = 2 / (26 + 1)
        signal_alpha = 2 / (9 + 1)

        # Update EMAs
        fast_ema = (
            fast_alpha * new_bar["Close"] + (1 - fast_alpha) * prev_macd["fast_ema"]
        )
        slow_ema = (
            slow_alpha * new_bar["Close"] + (1 - slow_alpha) * prev_macd["slow_ema"]
        )

        # MACD line
        macd_line = fast_ema - slow_ema

        # Signal line
        signal_line = (
            signal_alpha * macd_line + (1 - signal_alpha) * prev_macd["signal_line"]
        )

        # Histogram
        histogram = macd_line - signal_line

        return {
            "fast_ema": fast_ema,
            "slow_ema": slow_ema,
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram,
        }

    def _update_bollinger(self, prev_bb: dict, new_bar: pd.Series) -> dict:
        """Update Bollinger Bands incrementally with exact rolling window (O(1))"""
        period = prev_bb.get("period", 20)

        # Update rolling buffer
        rolling_buffer = prev_bb["rolling_buffer"].copy()
        rolling_buffer.append(new_bar["Close"])

        # Keep only last 'period' values
        if len(rolling_buffer) > period:
            rolling_buffer.pop(0)

        # Calculate exact SMA and STD from buffer
        import numpy as np

        sma = np.mean(rolling_buffer)
        std = np.std(rolling_buffer, ddof=1)  # ddof=1 for sample std

        # Bands
        upper = sma + (2.0 * std)
        lower = sma - (2.0 * std)

        return {
            "sma": sma,
            "upper": upper,
            "lower": lower,
            "std": std,
            "rolling_buffer": rolling_buffer,
            "period": period,
        }

    def _update_vwap(self, prev_vwap: dict, new_bar: pd.Series) -> dict:
        """Update VWAP incrementally (O(1))"""
        typical_price = (new_bar["High"] + new_bar["Low"] + new_bar["Close"]) / 3

        # Cumulative values
        cum_tp_volume = prev_vwap["cum_tp_volume"] + (typical_price * new_bar["Volume"])
        cum_volume = prev_vwap["cum_volume"] + new_bar["Volume"]

        # VWAP
        vwap = cum_tp_volume / cum_volume if cum_volume > 0 else typical_price

        return {"vwap": vwap, "cum_tp_volume": cum_tp_volume, "cum_volume": cum_volume}
