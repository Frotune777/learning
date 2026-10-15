"""
Strategy Optimizer
Optimizes technical indicator parameters using Backtesting.py
"""

import json
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

# Import indicators from our own classes for consistency
# or implement them inside the strategy using Talib directly for speed
import talib
from backtesting import Backtest, Strategy


class ScannerSelectionStrategy(Strategy):
    """
    Strategy that mimics the UltraOptimizedScanner logic:
    Buy: SuperTrend Bullish AND OBV Bullish (Trend Continuing)
    Sell: SuperTrend Bearish OR OBV Bearish (Weakness)
    """

    # Parameters to optimize
    supertrend_period = 10
    supertrend_multiplier = 3.0
    obv_ma = 20

    def init(self):
        # Prepare Data
        # Backtesting.py provides self.data.Close, self.data.High etc. (numpy arrays)
        close = self.data.Close
        high = self.data.High
        low = self.data.Low
        volume = self.data.Volume

        # --- SuperTrend Calculation ---
        # We need a helper for SuperTrend as it's stateful
        # Or use a vectorized approximation if possible, but loop is safer for correctness
        self.supertrend = self.I(
            self.calculate_supertrend,
            high,
            low,
            close,
            self.supertrend_period,
            self.supertrend_multiplier,
        )

        # --- OBV Calculation ---
        # OBV = Cumulative Volume based on Close direction
        # OBV MA = SMA of OBV
        self.obv = self.I(self.calculate_obv, close, volume)
        self.obv_sma = self.I(talib.SMA, self.obv, timeperiod=self.obv_ma)

    def calculate_obv(self, close, volume):
        # Calculate OBV
        obv = np.zeros_like(close)
        for i in range(1, len(close)):
            if close[i] > close[i - 1]:
                obv[i] = obv[i - 1] + volume[i]
            elif close[i] < close[i - 1]:
                obv[i] = obv[i - 1] - volume[i]
            else:
                obv[i] = obv[i - 1]
        return obv

    def calculate_supertrend(self, high, low, close, period, multiplier):
        # Calculate ATR
        # TR = max(H-L, |H-Cp|, |L-Cp|)
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        # Simple SMA of TR for ATR (approx) or proper Wilder's
        # Using simple rolling mean for speed/consistency with scanner
        atr = pd.Series(tr).rolling(period).mean().fillna(0).values

        hl2 = (high + low) / 2
        upperband = hl2 + (multiplier * atr)
        lowerband = hl2 - (multiplier * atr)

        st = np.zeros_like(close)
        direction = np.zeros_like(close)  # 1 Bull/ -1 Bear

        # Initialize
        for i in range(period, len(close)):
            if i > period:
                if close[i - 1] <= upperband[i - 1]:
                    upperband[i] = min(upperband[i], upperband[i - 1])
                else:
                    upperband[i] = upperband[i]

                if close[i - 1] >= lowerband[i - 1]:
                    lowerband[i] = max(lowerband[i], lowerband[i - 1])
                else:
                    lowerband[i] = lowerband[i]

            if close[i] <= upperband[i]:
                st[i] = upperband[i]
                direction[i] = -1
            else:
                st[i] = lowerband[i]
                direction[i] = 1

        # Return Direction for easy signal logic (1 or -1)
        return direction

    def next(self):
        # Current signals
        st_dir = self.supertrend[-1]
        obv_val = self.obv[-1]
        obv_ma_val = self.obv_sma[-1]

        is_bullish = (st_dir == 1) and (obv_val > obv_ma_val)
        is_bearish = (st_dir == -1) or (obv_val < obv_ma_val)

        if not self.position:
            if is_bullish:
                self.buy()
        else:
            if is_bearish:
                self.position.close()


class StrategyOptimizer:
    """
    Optimizes trading strategies directly using Backtesting.py
    """

    PARAMS_FILE = Path("user_data/strategy_params.json")

    def __init__(self):
        self.ensure_params_file()

    def ensure_params_file(self):
        """Ensure params file exists"""
        if not self.PARAMS_FILE.exists():
            self.PARAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.PARAMS_FILE, "w") as f:
                json.dump({}, f)

    def get_params(self, symbol: str) -> Dict:
        """Get optimized params for a stock"""
        try:
            with open(self.PARAMS_FILE, "r") as f:
                data = json.load(f)
                return data.get(symbol, {})
        except Exception:
            return {}

    def save_params(self, symbol: str, params: Dict):
        """Save optimized params"""
        try:
            with open(self.PARAMS_FILE, "r") as f:
                data = json.load(f)

            # Convert numpy types to python native types for JSON serialization
            clean_params = {}
            for k, v in params.items():
                if isinstance(v, (np.integer, np.int64, np.int32)):
                    clean_params[k] = int(v)
                elif isinstance(v, (np.floating, np.float64, np.float32)):
                    clean_params[k] = float(v)
                else:
                    clean_params[k] = v

            data[symbol] = clean_params

            with open(self.PARAMS_FILE, "w") as f:
                json.dump(data, f, indent=4)

            print(f"✅ Saved optimized params for {symbol}")
        except Exception as e:
            print(f"❌ Failed to save params: {e}")

    def optimize(self, data: pd.DataFrame, symbol: str) -> Dict:
        """
        Run backtesting.py optimization

        Args:
            data: OHLC DataFrame (columns must be Capitalized: Open, High, Low, Close, Volume)
            symbol: Stock symbol

        Returns:
            Best parameters dict
        """
        print(f"🚀 Optimizing strategy for {symbol} using Backtesting.py...")

        # Ensure columns are correct
        df = data.copy()
        # Backtesting.py requires Index to be datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        # Ensure no NaN
        df = df.dropna()

        # Set up Backtest
        bt = Backtest(df, ScannerSelectionStrategy, cash=100000, commission=0.002)

        try:
            # Run Optimization
            # Ranges: start, stop, step
            stats = bt.optimize(
                supertrend_period=range(7, 22, 3),  # [7, 10, 13, 16, 19]
                supertrend_multiplier=[2.0, 3.0, 4.0],  # [2, 3, 4]
                obv_ma=range(10, 51, 10),  # [10, 20, 30, 40, 50]
                maximize="Return [%]",  # Maximize Total Return
                constraint=lambda p: (
                    p.supertrend_period > 5
                ),  # Simple constraint example
                max_tries=200,
            )

            print(f"  🏆 Best Return: {stats['Return [%]']:.2f}%")
            print(f"  📈 Win Rate: {stats['Win Rate [%]']:.2f}%")
            print(f"  📉 Max Drawdown: {stats['Max. Drawdown [%]']:.2f}%")

            # Extract winning params (they are attributes of the stats._strategy)
            # Actually stats is a Series that includes the params at the end usually,
            # OR we can get them from stats._strategy attributes if the returned object supports it.
            # Backtesting.py stats object contains the param values as indices if strictly grouped,
            # BUT usually it returns a Series with mixed stats and params.
            # Let's extract known keys.

            best_params = {
                "supertrend_period": stats._strategy.supertrend_period,
                "supertrend_multiplier": stats._strategy.supertrend_multiplier,
                "obv_ma": stats._strategy.obv_ma,
            }

            print(f"  ⚙️  Best Params: {best_params}")
            self.save_params(symbol, best_params)
            return best_params

        except Exception as e:
            print(f"⚠️ Optimization failed: {e}")
            # If default run fails (e.g. no trades), try running without optimize to debug?
            return {}
