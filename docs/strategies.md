# Sharegenius Trading Strategies

Last Modified: 2026-05-30

This document outlines the detailed logic, technical requirements, and exact formulas for all quantitative trading strategies and screeners implemented in the Sharegenius application.

## Core Screener Lists

The primary technical screener evaluates stocks across multiple timeframes and produces three core lists based on the confluence of indicators:

### 1. Final Target List
- **Logic**: Pure breakout candidates exhibiting strong intraday and short-term momentum.
- **Criteria**: Combines "Bull Run" status with "CAR (Cumulative Average Rule) Buy/Average Out" ratings. Identifies stocks with established uptrends and sufficient relative volume to sustain the breakout.
- **Sorting**: Ranked descending by `Total Traded Value` (or `Turnover`).

### 2. Swing Trading List
- **Logic**: Mean-reversion positional setups nearing entry zones for mid-term holding.
- **Criteria**: Identifies "Start GTT" (Good Till Triggered) signals. Specifically targets stocks that have retraced to their 20-day lows and are showing initial signs of a bounce, providing favorable risk-reward entries.
- **GTT Target**: Defined as `GTT_TRIGGER * 1.20` (20% upside target).

### 3. Super List (The Holy Grail)
- **Logic**: Highest conviction setups passing multiple extreme filters.
- **Criteria**: Requires the rare confluence of Bull Run status, CAR Buy/Average Out rating, *and* a GTT bounce signal simultaneously. These are high-probability setups with strong momentum and defined support.

---

## Advanced Strategy Outputs

In addition to the core lists, the pipeline runs specific quantitative strategies computed inside the core screener:

### Nifty Shop (Single Leg)
- **Type**: Mean Reversion
- **Logic**: RSI laddering strategy designed to buy oversold conditions in strong stocks.
- **Entry Triggers**: 
  - Level 3 Buy: `RSI < 25.0`
  - Level 2 Buy: `RSI < 30.0`
  - Level 1 Buy: `RSI < 35.0`
- **Target**: Fixed 6.28% profit target from the Current Market Price (`CMP * 1.0628`).
- **Stop Loss**: No defined stop loss (relies on averaging down).

### Buy Low Sell High
- **Type**: Demand Level Accumulation
- **Logic**: Accumulates shares when they approach significant long-term support levels.
- **Entry Triggers**: `((CMP - 200 Day Low) / 200 Day Low) * 100 <= 2.0%`
- **Target**: `CMP + (2 * ATR)`
- **Stop Loss**: `200 Day Low - (0.5 * ATR)`

### Turtle Trading
- **Type**: Momentum Breakout
- **Logic**: Classic explosive momentum breakout strategy following the original Turtle rules.
- **Entry Triggers**: `CMP >= 55 Day High`
- **Target**: `CMP + (3 * ATR)`
- **Stop Loss**: `20 Day Low`

### RDX Indicator
- **Type**: Strict Momentum Screener
- **Logic**: Identifies stocks with powerful, trending upward or downward momentum.
- **Entry Triggers**: 
  - Explosive Buy: `ADX > 25.0` AND `+DI > -DI` AND `RSI > 60.0`
  - Explosive Sell: `ADX > 25.0` AND `-DI > +DI` AND `RSI < 40.0`
- **Target**: `CMP + (2 * ATR)` (For Longs)
- **Stop Loss**: `CMP - (1.5 * ATR)` (For Longs)

### 100 SMA Breakout
- **Type**: Base Breakout
- **Logic**: Institutional 6-month base breakout strategy.
- **Entry Triggers**: 
  1. `Previous Close <= Previous 100 SMA` AND `CMP > 100 SMA` (Crossover)
  2. `((CMP - 6 Month Low) / 6 Month Low) * 100 >= 20.0%` (20% above base)
- **Target**: `CMP + (3 * ATR)`
- **Stop Loss**: `100 SMA`

### ETF Shop Method
- **Type**: Index Fund Retracement
- **Logic**: A lower-risk variation of mean reversion applied specifically to Exchange Traded Funds (ETFs).
- **Entry Triggers**: `((CMP - 20 SMA) / 20 SMA) * 100 < -2.0%` (Trading more than 2% below its 20-day average).

### Super BO Stocks
- **Type**: Recovery / Turnaround
- **Logic**: Identifies stocks rising from protracted downtrends that are facing ultimate long-term resistance.
- **Entry Triggers**: `CMP > 50 SMA` AND `CMP > 100 SMA` AND `CMP > 150 SMA` AND `CMP < 200 SMA`.
- **Target**: `200 SMA` (Anticipating resistance test).
- **Stop Loss**: `CMP - (2 * ATR)`

### DMADMA (Reverse)
- **Type**: Bull Market Continuation
- **Logic**: Captures secondary breakouts in established uptrends.
- **Entry Triggers**: `CMP > 200 SMA` AND `CMP > 150 SMA` AND `150 SMA > 200 SMA`.
- **Target**: `CMP + (2 * ATR)`
- **Stop Loss**: `150 SMA`

### DMADMA (No SL)
- **Type**: Pure Momentum Following
- **Logic**: A medium-term trend following approach analogous to a "Golden Cross."
- **Entry Triggers**: `CMP > 200 SMA` AND `CMP > 50 SMA` AND `50 SMA > 200 SMA`.
- **Target**: Fixed 6.28% profit target (`CMP * 1.0628`).
- **Stop Loss**: No defined stop loss.
