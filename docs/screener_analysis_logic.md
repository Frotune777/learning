# Screener Analysis Logic

This document details the core technical analysis components implemented within the `StockScreener` and `ta_indicators` modules. It explains the mechanics behind the Trend Status, CAR Rating, Bottom Out Hunting (swing trading signals), and the comprehensive Technical Score calculation.

## 1. Trend Status Calculation

The screener evaluates the overarching trend of an equity using classical moving average crossover logic combined with distance thresholds from the 200-Day Moving Average (DMA).

### Requirements
- **Minimum Data**: At least 200 days of trading history to calculate the 200 DMA. 
- Stocks with less history receive an `Insufficient History` status.

### Logic Rules
1. **In Bull Run**:
   - `Current Market Price (CMP) > 50 DMA`
   - `CMP > 100 DMA`
   - `CMP > 200 DMA`
   - The price must be within **+0.01% and +10.0%** of the 200 DMA (acting as a near-breakout / steady climb filter).
2. **In Bear Run**:
   - `CMP < 50 DMA`
   - `CMP < 100 DMA`
   - `CMP < 200 DMA`
   - The price must be within **-10.0% and -0.01%** of the 200 DMA.
3. **Unconfirmed**: Any other condition that does not strictly satisfy the above Bull or Bear rules.

---

## 2. Cumulative Average Rule (CAR) Rating

The CAR Rating is an advanced momentum identifier that looks for sustained, incremental price improvements since the stock hit its 52-week high. 

### Mechanism
1. **Find the High**: The algorithm identifies the 52-week high price and its corresponding earliest date index.
2. **Slice History**: Only the daily close prices from the date of the 52-week high up to today are considered. A minimum of 10 trading days post-high is required (otherwise, it returns `Short History`).
3. **Expanding Mean (Cumulative Average)**: Calculates the running cumulative average of the close prices over this sliced period.
4. **Strictly Increasing Test**: Takes the last 10 days of this expanding mean. If the mean has increased for 9 consecutive daily steps, the stock is rated as **Buy/Average Out**.
5. **Avoid/Hold**: If the 9-day consecutive gain requirement is not met, it returns `Avoid/Hold`.

---

## 3. Bottom Out Hunting (Swing Trading)

This logic identifies stocks that have tested their recent 20-day floor and bounced back, signaling a potential short-term reversal setup.

### Methodology
1. **Calculate 20-Day Range**: Determine the `20-Day High` and `20-Day Low` using the most recent 20 daily bars.
2. **Floor Test**: Calculate the percentage difference between `Today's Low` and the `20-Day Low`. If this difference is within the `bottom_out_tolerance` (default 0.5%), the floor has been successfully tested.
3. **Bounce Test**: Check if the `CMP (Current Market Price)` is strictly greater than `Today's Low`.
4. **Advanced Bounce**: Calculate the percentage recovery from the `20-Day Low` to the `CMP`. Check if this exceeds the `bounce_buffer` (default 1.0%).

### Signals Output
- **Start GTT**: Floor tested successfully, price bounced, and the bounce exceeds the `bounce_buffer`. Provides a GTT buy trigger at the 20-Day High, with a stop loss below Today's Low.
- **Start GTT (Basic)**: Floor tested and price bounced, but the bounce was weak (below the `bounce_buffer`). 
- **Do not start GTT**: The floor was not tested (price didn't retrace to the 20D low), or there was no bounce from the day's low.

---

## 4. Technical Indicators & Scoring

Calculated via the `add_ta_indicators` function utilizing TA-Lib, the screener applies a 5-layer technical analysis framework to score equities out of 100 points.

### Indicators Computed
- **RSI (14)**: Relative Strength Index.
- **MACD**: Moving Average Convergence Divergence (12, 26, 9).
- **Bollinger Bands**: Upper, Middle, and Lower bands (20, 2).
- **ADX (14)**: Average Directional Index.
- **ATR (14)**: Average True Range (used for volatility insight).

### Scoring Matrix (Tech Score)
The `calculate_technical_score` function evaluates the most recent daily row:

| Indicator / Condition | Points Awarded | Max Points |
| :--- | :--- | :--- |
| **RSI (14)** | RSI between 40 and 70 (Healthy Trend) | 20 |
| **MACD** | MACD Line > MACD Signal Line (Bullish Crossover) | 20 |
| **Bollinger Bands** | CMP > Middle Band (Bullish territory) | 20 |
| **ADX (14)** | ADX > 25 (Strong Trend) | 20 |
| **Moving Averages** | 50 DMA > 200 DMA (Golden Cross proxy) | 20 |
| **Total** | | **100** |

### Tech Rating
The absolute `Tech Score` maps to an actionable `Tech Rating`:
- **STRONG BUY**: 80 - 100 points
- **BUY**: 60 - 79 points
- **NEUTRAL**: 40 - 59 points
- **SELL**: 20 - 39 points
- **STRONG SELL**: 0 - 19 points

---

## 5. Advanced Technical Strategies

The screener runs a comprehensive multi-methodology framework executing 9 robust trading systems concurrently. These generate independent CSV reports appended dynamically.

### 1. Nifty Shop Method (Single Leg System)
- **Logic**: Implements Mahesh Kaushik's RSI laddering strategy for ETF/Stock mean reversion.
- **Entry Points**: Level 1 (RSI < 35), Level 2 (RSI < 30), Level 3 (RSI < 25).
- **Target**: Mathematically calculated at `> 6.28%` (2π).
- **Stop Loss**: Does not utilize a fixed SL; recommends an "ICU SIP" to average down upon a 20% fall.

### 2. Buy Low Sell High System
- **Logic**: Accumulation near major demand levels.
- **Condition**: Tracks the `200-Day Low`. If CMP is within 2.0% above this low, flags as `Buy on Support`.
- **Target/SL**: Uses ATR-based bands (Target = CMP + 2*ATR, SL = 200D Low - 0.5*ATR).

### 3. Turtle Trading
- **Logic**: Momentum breakout trading capturing massive trends.
- **Condition**: Triggers `Buy (55D Breakout)` when CMP crosses the `55-Day High`.
- **Target/SL**: Trailing stop loss set at `20-Day Low`. Target floats dynamically at CMP + 3*ATR.

### 4. RDX Indicator
- **Logic**: Identifies explosive momentum moves.
- **Condition**: Requires `ADX > 25`, `PLUS_DI > MINUS_DI` (Bullish Trend), and `RSI > 60` for `Explosive Buy`.
- **Target/SL**: Target = CMP + 2*ATR, SL = CMP - 1.5*ATR.

### 5. 100 SMA Breakout
- **Logic**: Tracks institutional base breakouts over 6-month horizons.
- **Condition**: Checks if CMP crossed above `100 SMA` today, AND the CMP is trading at least `20%` above its `6-Month Low (126 Days)`.
- **Target/SL**: Target = CMP + 3*ATR, SL = 100 SMA.

### 6. ETF Shop Method
- **Logic**: A variant for index funds requiring minor retracements.
- **Condition**: Triggers a `Buy` if the ETF falls more than `2.0%` below its `20 DMA`.
- **Target/SL**: Mean reversion logic, typically targeting the 20 DMA.

### 7. Super BO Stocks (Super Breakout)
- **Logic**: Catches stocks recovering from severe downtrends facing immediate major resistance.
- **Condition**: CMP trades strictly above `50, 100, and 150 SMA`, but remains below the massive `200 SMA`.
- **Target/SL**: Target = 200 SMA, SL = CMP - 2*ATR.

### 8. DMADMA (Reverse Traders)
- **Logic**: Trend continuation inside an established bull market.
- **Condition**: CMP > 200 SMA and CMP > 150 SMA. Triggers when the 150 SMA pushes higher than the 200 SMA (`150 SMA Breakout`).
- **Target/SL**: Target = CMP + 2*ATR, SL = 150 SMA.

### 9. DMADMA (Without Stop Loss)
- **Logic**: Pure momentum following without SL limits.
- **Condition**: CMP > 200 SMA and CMP > 50 SMA. Triggers when the 50 SMA moves above the 200 SMA (`50 SMA Breakout` / Golden Cross analog).
- **Target/SL**: Target = Fixed `6.28%`, SL = None.
