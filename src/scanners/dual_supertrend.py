import numpy as np
import pandas as pd
from backtesting import Strategy


def supertrend_impl(high, low, close, atr_period, factor):
    """
    SuperTrend indicator implementation compatible with backtesting.py
    Returns: (SuperTrend Line, Direction)
    Direction: 1 (Green/Up), -1 (Red/Down) - NOTE: User script used -1 for Long (Green) logic?
    Let's stick to standard: 1 = Uptrend/Green, -1 = Downtrend/Red usually,
    but let's follow user's logic exactly if possible.

    User Logic:
    if close > upperband_prev: direction = -1 (This means -1 is GREEN/UP in user script)
    if close < lowerband_prev: direction = 1 (This means 1 is RED/DOWN in user script)
    """

    # Convert inputs to pandas Series for rolling func
    price_len = len(close)
    high = pd.Series(high)
    low = pd.Series(low)
    close = pd.Series(close)

    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)

    atr = tr.rolling(atr_period).mean().fillna(0)

    hl2 = (high + low) / 2
    upperband = hl2 + (factor * atr)
    lowerband = hl2 - (factor * atr)

    # We need to iterate to simulate the recursive SuperTrend logic
    direction = np.zeros(price_len)  # 1 or -1
    st = np.zeros(price_len)

    # Initialize first valid index
    direction[:atr_period] = 1  # Default
    upperband_arr = upperband.values
    lowerband_arr = lowerband.values
    close_arr = close.values

    # Recursive calculation
    # We use a simple loop. Numba could speed this up but standard python is fine for this scale.
    for i in range(atr_period, price_len):
        if close_arr[i] > upperband_arr[i - 1]:
            direction[i] = -1  # User's Green
        elif close_arr[i] < lowerband_arr[i - 1]:
            direction[i] = 1  # User's Red
        else:
            direction[i] = direction[i - 1]
            if direction[i] == -1:  # Green/Up
                lowerband_arr[i] = max(lowerband_arr[i], lowerband_arr[i - 1])
            else:  # Red/Down
                upperband_arr[i] = min(upperband_arr[i], upperband_arr[i - 1])

        st[i] = lowerband_arr[i] if direction[i] == -1 else upperband_arr[i]

    return st, direction


class DualSuperTrend(Strategy):
    """
    Dual SuperTrend Strategy
    Converted from User's Script.

    Logic:
    - Long Entry: When 'Buy SuperTrend' flips to Up (-1).
    - Short Entry: When 'Sell SuperTrend' flips to Down (1).
    """

    # Optimization Parameters
    buy_atr = 10
    buy_factor = 3
    sell_atr = 10
    sell_factor = 3

    def init(self):
        # We need to register the indicator helper
        # self.I stores the result for plotting

        # Calculate Buy SuperTrend
        # self.I requires a function that returns the array.
        # Since our function returns two arrays, we might need a workaround or wrapper.
        # Simplest is to calculate inside init using helper, but wrap for plotting if needed.

        # NOTE: backtesting.py self.I expects a callable.
        # We will wrap the calls.

        self.buy_st, self.buy_dir = self.I(
            supertrend_impl,
            self.data.High,
            self.data.Low,
            self.data.Close,
            self.buy_atr,
            self.buy_factor,
            overlay=True,
        )
        self.sell_st, self.sell_dir = self.I(
            supertrend_impl,
            self.data.High,
            self.data.Low,
            self.data.Close,
            self.sell_atr,
            self.sell_factor,
            overlay=True,
        )

    def next(self):
        # User Logic:
        # long_entry = (df.loc[curr, 'buy_dir'] == -1 and df.loc[prev, 'buy_dir'] == 1)
        # short_entry = (df.loc[curr, 'sell_dir'] == 1 and df.loc[prev, 'sell_dir'] == -1)

        # In backtesting.py, self.buy_dir[-1] is current, self.buy_dir[-2] is prev

        # Long Entry
        if self.buy_dir[-1] == -1 and self.buy_dir[-2] == 1:
            if not self.position.is_long:
                self.position.close()
                self.buy()

        # Short Entry (or Close Long?)
        # The user's script supports Shorting.
        # if allow_short: ...
        # For now, let's assume standard Long-Only or Reversal.
        # If we want to simulate the user's exact "Allow Long" / "Allow Short" flags,
        # we can add those as class params too.

        elif self.sell_dir[-1] == 1 and self.sell_dir[-2] == -1:
            if self.position.is_long:
                self.position.close()
            # If you want to enable shorting:
            # self.sell()
