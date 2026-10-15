import pandas as pd


class VolumeIndicators:
    @staticmethod
    def volume_profile(df: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
        """
        Calculate Volume Profile - price levels with highest volume.
        Returns Point of Control (POC) and Value Area.
        """
        try:
            if len(df) < 20:
                return df

            # Create price bins
            price_min = df["Low"].min()
            price_max = df["High"].max()
            price_range = price_max - price_min

            if price_range == 0:
                df["POC"] = df["Close"].iloc[-1]
                df["Value_Area_High"] = df["Close"].iloc[-1]
                df["Value_Area_Low"] = df["Close"].iloc[-1]
                return df

            bin_size = price_range / bins

            # Assign each candle to price bins and sum volume
            volume_at_price = {}
            for i in range(bins):
                bin_low = price_min + i * bin_size
                bin_high = bin_low + bin_size
                bin_center = (bin_low + bin_high) / 2

                # Sum volume for candles in this price range
                mask = (df["Low"] <= bin_high) & (df["High"] >= bin_low)
                volume_at_price[bin_center] = df.loc[mask, "Volume"].sum()

            # Point of Control (POC) - price with maximum volume
            poc_price = max(volume_at_price, key=volume_at_price.get)
            df["POC"] = poc_price

            # Value Area - 70% of total volume
            total_volume = sum(volume_at_price.values())
            target_volume = total_volume * 0.70

            # Sort by volume descending
            sorted_prices = sorted(
                volume_at_price.items(), key=lambda x: x[1], reverse=True
            )

            cumulative_volume = 0
            value_area_prices = []

            for price, vol in sorted_prices:
                cumulative_volume += vol
                value_area_prices.append(price)
                if cumulative_volume >= target_volume:
                    break

            df["Value_Area_High"] = (
                max(value_area_prices) if value_area_prices else poc_price
            )
            df["Value_Area_Low"] = (
                min(value_area_prices) if value_area_prices else poc_price
            )

            return df
        except Exception:
            df["POC"] = df["Close"].iloc[-1] if not df.empty else 0
            df["Value_Area_High"] = df["Close"].iloc[-1] if not df.empty else 0
            df["Value_Area_Low"] = df["Close"].iloc[-1] if not df.empty else 0
            return df

    def obv(self, data: pd.DataFrame) -> pd.Series:
        """Calculate On-Balance Volume - Vectorized for performance"""
        import numpy as np

        # Calculate price changes
        close_diff = data["Close"].diff()

        # Determine direction: 1 for up, -1 for down, 0 for unchanged
        direction = np.sign(close_diff).fillna(0)

        # Calculate OBV as cumulative sum of (direction * volume)
        obv = (direction * data["Volume"]).cumsum()

        return obv
