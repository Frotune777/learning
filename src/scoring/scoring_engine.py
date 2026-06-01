"""
File: src/scoring/scoring_engine.py
Purpose: Vectorised multi-factor scoring and ranking engine for screened stocks.
Last Modified: 2026-06-01
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


class ScoringEngine:
    """
    Multi-factor weighted scoring and ranking engine.
    
    Evaluates:
        1. Trend Quality (25%) - SMA alignment and distance to 200 DMA
        2. Momentum (20%) - RSI and ADX/DI alignment
        3. CAR Quality (15%) - Textbook CAR Buy rating
        4. Risk-Adjusted Return (15%) - Sharpe ratio and Max Drawdown
        5. Volume / Accumulation (10%) - Delivery % and Volume Spike
        6. Volatility Regime (10%) - Stable/low volatility preference
        7. Event / Catalyst (5%) - Proximity to events/insider trading
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        # Default weights summing to 1.0 (100 points)
        self.weights = weights or {
            "trend": 0.25,
            "momentum": 0.20,
            "car": 0.15,
            "risk_adjusted": 0.15,
            "volume": 0.10,
            "volatility": 0.10,
            "catalyst": 0.05,
        }
        # Double check sum
        total_weight = sum(self.weights.values())
        if not np.isclose(total_weight, 1.0):
            LOGGER.warning("Scoring weights do not sum to 1.0: %.2f", total_weight)

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate composite multi-factor score and rank for the given DataFrame.
        
        Parameters:
            df (pd.DataFrame): DataFrame containing technical, risk, and corporate columns.
            
        Returns:
            pd.DataFrame: Enriched DataFrame with score and rank columns.
        """
        if df.empty:
            return df.copy()

        result = df.copy()

        # 1. Trend Quality Score (Max 100 scaled to 25%)
        trend_score = self._score_trend(result)
        
        # 2. Momentum Score (Max 100 scaled to 20%)
        momentum_score = self._score_momentum(result)
        
        # 3. CAR Quality Score (Max 100 scaled to 15%)
        car_score = self._score_car(result)
        
        # 4. Risk-Adjusted Score (Max 100 scaled to 15%)
        risk_score = self._score_risk(result)
        
        # 5. Volume/Accumulation Score (Max 100 scaled to 10%)
        volume_score = self._score_volume(result)
        
        # 6. Volatility Regime Score (Max 100 scaled to 10%)
        vol_score = self._score_volatility(result)
        
        # 7. Catalyst Score (Max 100 scaled to 5%)
        catalyst_score = self._score_catalyst(result)

        # Combine weighted scores
        result["TREND_FACTOR_SCORE"] = trend_score
        result["MOMENTUM_FACTOR_SCORE"] = momentum_score
        result["CAR_FACTOR_SCORE"] = car_score
        result["RISK_FACTOR_SCORE"] = risk_score
        result["VOLUME_FACTOR_SCORE"] = volume_score
        result["VOLATILITY_FACTOR_SCORE"] = vol_score
        result["CATALYST_FACTOR_SCORE"] = catalyst_score

        result["COMPOSITE_SCORE"] = (
            (trend_score * self.weights["trend"]) +
            (momentum_score * self.weights["momentum"]) +
            (car_score * self.weights["car"]) +
            (risk_score * self.weights["risk_adjusted"]) +
            (volume_score * self.weights["volume"]) +
            (vol_score * self.weights["volatility"]) +
            (catalyst_score * self.weights["catalyst"])
        )

        # Rank candidates (higher score = lower rank number, i.e., rank 1 is best)
        result["RANK"] = result["COMPOSITE_SCORE"].rank(ascending=False, method="min")
        
        return result

    def _score_trend(self, df: pd.DataFrame) -> pd.Series:
        """Score based on DMA stacks and CMP position relative to MAs."""
        score = pd.Series(0.0, index=df.index)
        
        # Check DMA alignment (CMP > SMA_20 > SMA_50 > SMA_100 > SMA_150 > SMA_200)
        # We award points incrementally
        if "CMP" in df.columns:
            cmp = df["CMP"]
            sma_20 = df.get("SMA_20", pd.Series(np.nan, index=df.index))
            dma_50 = df.get("DMA_50", pd.Series(np.nan, index=df.index))
            dma_100 = df.get("DMA_100", pd.Series(np.nan, index=df.index))
            dma_150 = df.get("DMA_150", pd.Series(np.nan, index=df.index))
            dma_200 = df.get("DMA_200", pd.Series(np.nan, index=df.index))

            # 50 points for basic stack order
            order_pts = pd.Series(0.0, index=df.index)
            order_pts += np.where(cmp > sma_20, 10.0, 0.0)
            order_pts += np.where(sma_20 > dma_50, 10.0, 0.0)
            order_pts += np.where(dma_50 > dma_100, 10.0, 0.0)
            order_pts += np.where(dma_100 > dma_150, 10.0, 0.0)
            order_pts += np.where(dma_150 > dma_200, 10.0, 0.0)
            score += order_pts

            # 50 points for distance to 200 DMA (closer is better for low-risk entry, e.g., 0-15%)
            if "DIFF_200_DMA" in df.columns:
                diff = df["DIFF_200_DMA"]
                # Full points if between 0.1% and 10%, decaying points up to 30%
                dist_score = np.where(
                    (diff > 0) & (diff <= 10.0), 50.0,
                    np.where(
                        (diff > 10.0) & (diff <= 20.0), 35.0,
                        np.where((diff > 20.0) & (diff <= 30.0), 15.0, 0.0)
                    )
                )
                score += dist_score

        return score.clip(0.0, 100.0)

    def _score_momentum(self, df: pd.DataFrame) -> pd.Series:
        """Score based on RSI and ADX/DI indicators."""
        score = pd.Series(0.0, index=df.index)

        # RSI Momentum (50 points)
        if "RSI_14" in df.columns:
            rsi = df["RSI_14"]
            # Best range is 55 to 70 for strong bullish momentum
            rsi_pts = np.where(
                (rsi >= 55.0) & (rsi <= 70.0), 50.0,
                np.where(
                    (rsi >= 45.0) & (rsi < 55.0), 30.0,
                    np.where(
                        (rsi > 70.0) & (rsi <= 80.0), 20.0, # Overbought but trending
                        np.where((rsi >= 35.0) & (rsi < 45.0), 10.0, 0.0)
                    )
                )
            )
            score += rsi_pts

        # ADX trend strength & DI alignment (50 points)
        adx = df.get("ADX_14", pd.Series(np.nan, index=df.index))
        plus_di = df.get("PLUS_DI_14", pd.Series(np.nan, index=df.index))
        minus_di = df.get("MINUS_DI_14", pd.Series(np.nan, index=df.index))

        adx_pts = np.where(
            (adx > 25.0) & (plus_di > minus_di), 50.0,
            np.where(
                (adx > 20.0) & (plus_di > minus_di), 35.0,
                np.where(plus_di > minus_di, 15.0, 0.0)
            )
        )
        score += adx_pts

        return score.clip(0.0, 100.0)

    def _score_car(self, df: pd.DataFrame) -> pd.Series:
        """Score based on Cumulative Average Rule rating."""
        score = pd.Series(0.0, index=df.index)
        if "CAR_RATING" in df.columns:
            # 100 points for Buy/Average Out
            score = np.where(df["CAR_RATING"] == "Buy/Average Out", 100.0, 20.0)
        return pd.Series(score, index=df.index)

    def _score_risk(self, df: pd.DataFrame) -> pd.Series:
        """Score based on Sharpe Ratio and Max Drawdown."""
        score = pd.Series(0.0, index=df.index)
        
        # Sharpe 1Y (50 points)
        sharpe = df.get("SHARPE_1Y", pd.Series(np.nan, index=df.index))
        sharpe_pts = np.where(
            sharpe >= 2.0, 50.0,
            np.where(
                sharpe >= 1.0, 35.0,
                np.where(sharpe >= 0.5, 15.0, 0.0)
            )
        )
        score += sharpe_pts

        # Max Drawdown (50 points) - lower drawdown is better
        max_dd = df.get("MAX_DRAWDOWN_PCT", pd.Series(np.nan, index=df.index))
        # Note: drawdown can be positive or negative in representation; we check absolute value
        abs_dd = max_dd.abs()
        dd_pts = np.where(
            abs_dd <= 10.0, 50.0,
            np.where(
                abs_dd <= 20.0, 35.0,
                np.where(abs_dd <= 35.0, 15.0, 0.0)
            )
        )
        score += dd_pts

        return score.clip(0.0, 100.0)

    def _score_volume(self, df: pd.DataFrame) -> pd.Series:
        """Score based on delivery percentage and volume spikes."""
        score = pd.Series(0.0, index=df.index)

        # Delivery Percentage (50 points)
        deliv = df.get("DELIV_PCT", pd.Series(np.nan, index=df.index))
        deliv_pts = np.where(
            deliv >= 45.0, 50.0,
            np.where(
                deliv >= 30.0, 35.0,
                np.where(deliv >= 20.0, 15.0, 0.0)
            )
        )
        score += deliv_pts

        # Volume Spike (50 points)
        vol_spike = df.get("VOL_SPIKE", pd.Series(np.nan, index=df.index))
        vol_pts = np.where(
            vol_spike >= 2.5, 50.0,
            np.where(
                vol_spike >= 1.5, 35.0,
                np.where(vol_spike >= 1.0, 15.0, 0.0)
            )
        )
        score += vol_pts

        return score.clip(0.0, 100.0)

    def _score_volatility(self, df: pd.DataFrame) -> pd.Series:
        """Score based on GARCH volatility or daily return volatility (low volatility preferred)."""
        score = pd.Series(50.0, index=df.index)  # Default neutral score

        vol = df.get("GARCH_VOL_PCT", pd.Series(np.nan, index=df.index))
        
        # Lower volatility in trend is positive
        score = np.where(
            vol <= 20.0, 100.0,
            np.where(
                vol <= 35.0, 75.0,
                np.where(vol <= 50.0, 40.0, 10.0)
            )
        )
        return pd.Series(score, index=df.index)

    def _score_catalyst(self, df: pd.DataFrame) -> pd.Series:
        """Score based on Insider trades, upcoming corporate actions, and event days."""
        score = pd.Series(30.0, index=df.index) # Base score

        # Insider Trading Score (SEBI)
        insider = df.get("Insider Score", pd.Series(0.0, index=df.index)).fillna(0.0)
        score += np.where(insider > 0.0, 40.0, 0.0) # Insider buying is positive

        # Corporate Action Proximity / Event Risk
        event_days = df.get("Event Risk (Days)", pd.Series(np.nan, index=df.index))
        # If event is near (e.g. < 5 days), might be a catalyst or risk. Award positive points for setup proximity
        score += np.where((event_days > 0) & (event_days <= 10), 30.0, 10.0)

        return score.clip(0.0, 100.0)
