from src.scanners.base import BaseStrategy

from .breakout import BreakoutStrategy
from .candle_patterns import CandlePatternsStrategy
from .chart_patterns import InsideBarStrategy, IPOBaseStrategy
from .dual_supertrend import DualSuperTrend
from .lorentzian import LorentzianClassifierStrategy
from .menu_parity import (
    ATRCrossStrategy,
    HighLow52WeekStrategy,
    HighMomentumStrategy,
    IchimokuStrategy,
    NextDayBullishStrategy,
    NR4Strategy,
    SuperTrendStrategy,
)
from .ml_strategies import LorentzianStrategy
from .oscillator import CCIStrategy, MACDStrategy, StochasticStrategy
from .screenipy import ConsolidationStrategy, MomentumStrategy, RSIStrategy
from .trend import MeanReversionStrategy, TrendlineStrategy
from .trend_linear import TrendLinearRegressionStrategy
from .ttm_squeeze import TTMSqueezeStrategy
from .vcp import VCPStrategy

__all__ = ['BaseStrategy', 'BreakoutStrategy', 'CandlePatternsStrategy', 'InsideBarStrategy', 'IPOBaseStrategy', 'DualSuperTrend', 'LorentzianClassifierStrategy', 'LorentzianStrategy', 'IchimokuStrategy', 'NR4Strategy', 'HighLow52WeekStrategy', 'NextDayBullishStrategy', 'SuperTrendStrategy', 'ATRCrossStrategy', 'HighMomentumStrategy', 'MACDStrategy', 'CCIStrategy', 'StochasticStrategy', 'ConsolidationStrategy', 'RSIStrategy', 'MomentumStrategy', 'TTMSqueezeStrategy', 'TrendLinearRegressionStrategy', 'MeanReversionStrategy', 'TrendlineStrategy', 'VCPStrategy']