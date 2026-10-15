from typing import Any, Dict

import pandas as pd
import talib

from src.scanners.base import BaseStrategy

try:
    import advanced_ta as ata

    HAS_ATA = True
except ImportError:
    HAS_ATA = False


class LorentzianClassifierStrategy(BaseStrategy):
    """
    Lorentzian Classification strategy ported from PKScreener.
    Uses the advanced-ta library for distance-based trend classification.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.description = "Lorentzian Classification (PKScreener Port)"
        self.lookback_limit = 2000

    def analyze(self, df: pd.DataFrame) -> bool:
        if not HAS_ATA:
            self.reason = "advanced-ta library not installed"
            return False

        if df is None or len(df) < 50:
            self.reason = "Insufficient data for Lorentzian analysis"
            return False

        try:
            # PKScreener reverses the data for analysis
            # Screenipy data is usually newest first (iloc[0] is latest)
            # Lorentzian classification usually expects chronological order for internal processing
            data = df.iloc[::-1].copy()

            # Map columns to lowercase as expected by some libs or for consistency
            data = data.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )

            # Features configuration from PKScreener ScreeningStatistics.py
            # Features include RSI, WaveTrend (WT), CCI, ADX, and MFI
            features = [
                ata.LorentzianClassification.Feature("RSI", 14, 2),  # f1
                ata.LorentzianClassification.Feature("WT", 10, 11),  # f2
                ata.LorentzianClassification.Feature("CCI", 20, 2),  # f3
                ata.LorentzianClassification.Feature("ADX", 20, 2),  # f4
                ata.LorentzianClassification.Feature("RSI", 9, 2),  # f5
                talib.MFI(
                    data["high"], data["low"], data["close"], data["volume"], 14
                ),  # f6
            ]

            # Initialization
            lc = ata.LorentzianClassification(
                data=data,
                features=features,
                settings=ata.LorentzianClassification.Settings(
                    source=data["close"],
                    neighborsCount=8,
                    maxBarsBack=self.lookback_limit,
                    useDynamicExits=False,
                ),
                filterSettings=ata.LorentzianClassification.FilterSettings(
                    useVolatilityFilter=True,
                    useRegimeFilter=True,
                    useAdxFilter=False,
                    regimeThreshold=-0.1,
                    adxThreshold=20,
                    kernelFilter=ata.LorentzianClassification.KernelFilter(
                        useKernelSmoothing=False,
                        lookbackWindow=8,
                        relativeWeight=8.0,
                        regressionLevel=25,
                        crossoverLag=2,
                    ),
                ),
            )

            # Check for latest signals
            latest = lc.df.iloc[-1]

            if latest["isNewBuySignal"]:
                self.reason = "Lorentzian Buy Signal detected"
                return True
            elif latest["isNewSellSignal"]:
                self.reason = f"Lorentzian Sell Signal detected (Kernel: {latest.get('kernel', 'N/A')})"
                return False

            self.reason = f"No Lorentzian signal (Kernel: {latest.get('kernel', 'N/A')}, Prediction: {latest.get('prediction', 'N/A')})"
            return False

        except Exception as e:
            self.reason = f"Lorentzian Analysis Error: {str(e)}"
            return False

    def get_description(self) -> str:
        return self.description
