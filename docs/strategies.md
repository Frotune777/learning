# Fortune ADSS: Comprehensive Strategies & Screeners Logic Reference

**Application:** Fortune Analytical Decision-Support System (Fortune ADSS)  
**Last Updated:** 2026-11-18  
**Scope:** 100% Analytical Decision-Support & Technical Screening. Strictly ZERO live broker order execution. Operates offline against stored Parquet data in `data/historical/1d/`.

---

## Table of Contents
1. [Core Screener Lists & Technical Scoring](#1-core-screener-lists--technical-scoring)
2. [The 13 Core Quantitative Strategies (`src/engine/strategies.py`)](#2-the-13-core-quantitative-strategies)
3. [Capsule Academy 5-Star & SMC Framework (`src/engine/capsule_engine.py`)](#3-capsule-academy-5-star--smc-framework)
4. [Train No. 920/130 Momentum Setup](#4-train-no-920130-momentum-setup)
5. [Smart Money Concepts Engine (`src/engine/smc.py`)](#5-smart-money-concepts-engine)
6. [LuxAlgo Technical & Market Structure Suite (`src/engine/lux_*.py`)](#6-luxalgo-technical--market-structure-suite)
7. [Specialized Market Scanners (`src/scanners/`)](#7-specialized-market-scanners)

---

## 1. Core Screener Lists & Technical Scoring

The primary technical screener (`src/engine/screener.py`) scans the local Parquet data lake and categorizes equities into 3 primary actionable lists:

### 1.1 Final Target List (Breakout Momentum)
- **Logic:** Identifies equities in sustained upward breakouts with institutional accumulation.
- **Criteria:**
  - **Trend Status:** `In Bull Run` ($\text{CMP} > \text{50 DMA}$, $\text{CMP} > \text{100 DMA}$, $\text{CMP} > \text{200 DMA}$, and CMP within $+0.01\%$ to $+10.0\%$ above 200 DMA).
  - **CAR Rating:** `Buy/Average Out` (Cumulative average of daily closes since the 52-week high strictly increasing for 9 consecutive trading sessions).
- **Ranking:** Descending by Total Traded Value / Daily Turnover.

### 1.2 Swing Trading List (Floor Test & Bounce)
- **Logic:** Identifies mean-reversion dip opportunities where price tests short-term demand floors.
- **Criteria:**
  - Calculates 20-Day Range (`20-Day High`, `20-Day Low`).
  - **Floor Test:** $(\text{Low}_{\text{today}} - \text{Low}_{\text{20D}}) / \text{Low}_{\text{20D}} \le 0.5\%$ (tested recent base).
  - **Bounce Test:** $\text{CMP} > \text{Low}_{\text{today}}$ and $(\text{CMP} - \text{Low}_{\text{20D}}) / \text{Low}_{\text{20D}} \ge 1.0\%$ (`bounce_buffer`).
- **Signal:** Generates `Start GTT` with entry trigger at 20-Day High and target at $\text{GTT\_TRIGGER} \times 1.20$ (+20% gain).

### 1.3 Super List (Confluence of High Conviction)
- **Logic:** Rarest institutional setups meeting both trend continuation and structural dip support.
- **Criteria:** Simultaneous intersection of:
  1. `In Bull Run` status.
  2. `CAR Buy/Average Out` rating.
  3. `Start GTT` swing reversal signal.

### 1.4 Technical Score Matrix (0–100 Points)
The `calculate_technical_score` function awards up to 100 points:
- **RSI (14):** 20 pts if $40 \le \text{RSI} \le 70$ (sustainable trend without extreme exhaustion).
- **MACD (12, 26, 9):** 20 pts if $\text{MACD Line} > \text{Signal Line}$ (bullish momentum).
- **Bollinger Bands (20, 2):** 20 pts if $\text{CMP} > \text{Middle Band}$ (bullish half).
- **ADX (14):** 20 pts if $\text{ADX} > 25$ (strong directional trend).
- **Moving Averages:** 20 pts if $50\text{ DMA} > 200\text{ DMA}$ (Golden Cross proxy).
- **Mapping:** 80–100 = **STRONG BUY** | 60–79 = **BUY** | 40–59 = **NEUTRAL** | 20–39 = **SELL** | 0–19 = **STRONG SELL**.

---

## 2. The 13 Core Quantitative Strategies

All 13 strategies are implemented as pure, vectorized functional calculators in `src/engine/strategies.py`:

| # | Strategy Name | Type | Core Mathematical Criteria | Target / Stop Loss |
|---|---|---|---|---|
| **1** | **Nifty Shop** | Mean Reversion | Mahesh Kaushik RSI ladder:<br>• Level 1 Buy: $\text{RSI} < 35.0$<br>• Level 2 Buy: $\text{RSI} < 30.0$<br>• Level 3 Buy: $\text{RSI} < 25.0$ | **Target:** $\text{CMP} \times 1.0628$ ($+6.28\% = 2\pi$)<br>**SL:** None (ICU SIP averaging down on -20% drawdown) |
| **2** | **Buy Low Sell High** | Demand Accumulation | CMP tests 200-day floor:<br>$\frac{\text{CMP} - \text{Low}_{200\text{D}}}{\text{Low}_{200\text{D}}} \times 100 \le 2.0\%$ | **Target:** $\text{CMP} + 2 \times \text{ATR}_{14}$<br>**SL:** $\text{Low}_{200\text{D}} - 0.5 \times \text{ATR}_{14}$ |
| **3** | **Turtle Trading** | Trend Breakout | Donchian 55-day channel breakout:<br>$\text{CMP} \ge \text{High}_{55\text{D}}$ | **Target:** $\text{CMP} + 3 \times \text{ATR}_{14}$<br>**SL:** $\text{Low}_{20\text{D}}$ (20-day channel trailing exit) |
| **4** | **RDX Momentum** | Trend Strength | Explosive momentum confluence:<br>$\text{ADX} > 25.0$ AND $+\text{DI} > -\text{DI}$ AND $\text{RSI} > 60.0$ | **Target:** $\text{CMP} + 2 \times \text{ATR}_{14}$<br>**SL:** $\text{CMP} - 1.5 \times \text{ATR}_{14}$ |
| **5** | **100 SMA Breakout** | Base Expansion | 6-month base breakout over institutional benchmark:<br>1. $\text{Close}_{t-1} \le 100\text{ SMA}_{t-1}$ AND $\text{CMP} > 100\text{ SMA}_t$<br>2. $\frac{\text{CMP} - \text{Low}_{6\text{M}}}{\text{Low}_{6\text{M}}} \times 100 \ge 20.0\%$ | **Target:** $\text{CMP} + 3 \times \text{ATR}_{14}$<br>**SL:** $100\text{ SMA}$ |
| **6** | **ETF Shop** | Index Retracement | Mean reversion for benchmark ETFs:<br>$\frac{\text{CMP} - 20\text{ SMA}}{20\text{ SMA}} \times 100 < -2.0\%$ | **Target:** $20\text{ SMA}$ reversion<br>**SL:** Position-sized dip reserve |
| **7** | **Super BO Stocks** | Turnaround Recovery | Multi-SMA recovery before final barrier:<br>$\text{CMP} > 50\text{ SMA}$, $\text{CMP} > 100\text{ SMA}$, $\text{CMP} > 150\text{ SMA}$, but $\text{CMP} < 200\text{ SMA}$ | **Target:** $200\text{ SMA}$ (test of major line)<br>**SL:** $\text{CMP} - 2 \times \text{ATR}_{14}$ |
| **8** | **DMADMA Reverse** | Trend Continuation | Intermediate MA breakout in bull trend:<br>$\text{CMP} > 200\text{ SMA}$ AND $\text{CMP} > 150\text{ SMA}$ AND $150\text{ SMA} > 200\text{ SMA}$ | **Target:** $\text{CMP} + 2 \times \text{ATR}_{14}$<br>**SL:** $150\text{ SMA}$ |
| **9** | **DMADMA No SL** | Golden Cross Momentum | Medium-term trend following:<br>$\text{CMP} > 200\text{ SMA}$ AND $\text{CMP} > 50\text{ SMA}$ AND $50\text{ SMA} > 200\text{ SMA}$ | **Target:** Fixed $+6.28\%$ ($\text{CMP} \times 1.0628$)<br>**SL:** None |
| **10** | **VCP (Volatility Contraction)** | Volatility Squeeze | Mark Minervini contraction stages ($T_1 > T_2 > T_3$), contraction depth shrinking by $\ge 40\%$ per wave, volume drying up in final base ($< 50\text{D Volume}$), breakout on $+50\%$ volume spike | **Target:** $\text{Pivot} + 15\%$ to $+25\%$<br>**SL:** Lowest point of the final contraction wave |
| **11** | **TTM Squeeze** | Energy Compression | Bollinger Bands (20, 2.0) fully contained within Keltner Channels (20, 1.5). Squeeze fires when bands expand outside Keltner, accompanied by Momentum Histogram shifting positive | **Target:** Dynamic trailing until momentum bar changes slope<br>**SL:** Opposite Keltner Channel band |
| **12** | **Dual SuperTrend** | Trend Confirmation | Fast SuperTrend (10, 2.0) and Slow SuperTrend (10, 3.0) must simultaneously flip green/bullish | **Target:** Multi-bar trend ride<br>**SL:** Slow SuperTrend line |
| **13** | **Lorentzian Classification** | Machine Learning KNN | 5-dimensional feature space (RSI, WaveTrend, CCI, ADX, EMA slope) transformed using Lorentzian distance: $d(u,v) = \sum \ln(1 + |u_i - v_i|)$. Predicts forward 4-bar direction based on $K=8$ nearest historical neighbors | **Confidence:** Triggers long when $\ge 75\%$ nearest neighbors are bullish |

---

## 3. Capsule Academy 5-Star & SMC Framework

Implemented in `src/engine/capsule_engine.py` and `src/scanners/capsule_screener.py` based on Dr. Nayeem Ahmad Shariff's official texts (*5-Star Study of Capsule Academy* and *Smart Money Capsule 1.0*):

```
       ┌────────────────────────────────────────────────────────┐
       │               STAR 1: MONTHLY (FARMS)                  │
       │    MACD Hist > 0 · CCI 30/5 > 0 · EMA 9/20 Bull · RSI > 60   │
       └───────────────────────────┬────────────────────────────┘
                                   │ (Filters High-Level Universe)
       ┌───────────────────────────▼────────────────────────────┐
       │             STAR 2: WEEKLY (SUNFLOWERS)                │
       │  Above EMA 200 (Mandatory) · CCI 30/5 > 0 · RSI > 55   │
       └───────────────────────────┬────────────────────────────┘
                                   │ (Swing Trading Candidates)
       ┌───────────────────────────▼────────────────────────────┐
       │               STAR 3: DAILY (SEEDS)                    │
       │   Above EMA 200 (Mandatory) · EMA 7 Bull · RSI > 50    │
       └───────────────────────────┬────────────────────────────┘
                                   │ (Execution & Surge Check)
       ┌───────────────────────────▼────────────────────────────┐
       │     STAR 4: TURNOVER SURGE & STAR 5: FUNDAMENTALS     │
       │  Turnover Surge > 50-100% · Spread < 0.5% · Mcap > 500Cr│
       └────────────────────────────────────────────────────────┘
```

### 3.1 Star Breakdown Criteria
1. **Star 1: Monthly (Farms)**
   - Monthly MACD Histogram is positive and non-declining ($H_t \ge H_{t-1}$).
   - Monthly CCI (30 period, 5 smoothing) $> 0$.
   - Monthly CMP $>$ EMA 9 and CMP $>$ EMA 200 (if 200M history exists).
   - Monthly EMA 9 $>$ EMA 20 crossover or alignment.
   - Monthly RSI $\ge 60$ (super-bullish zone).
2. **Star 2: Weekly (Sunflowers)**
   - Weekly CMP $>$ EMA 200 (**MANDATORY**).
   - Weekly MACD Histogram $> 0$.
   - Weekly CCI (30/5) $> 0$ or fresh signal cross.
   - Weekly CMP $>$ EMA 9 and EMA 9 $>$ EMA 20.
   - Weekly RSI $\ge 55$.
3. **Star 3: Daily (Seeds / Positional)**
   - Daily CMP $>$ EMA 200 (**MANDATORY RULE OF CAPSULE ACADEMY**).
   - Daily CCI (30/5) $> 0$ or fresh crossover.
   - Daily MACD Histogram $> 0$.
   - Daily Close $>$ EMA 7.
   - Daily RSI $\ge 50$.
4. **Star 4: Simple Turnover Surge**
   - Simple Turnover defined as $\text{Volume} \times \text{Price}$.
   - Day's turnover expands by **$+50\%$ to $+100\%+$** over the previous day's turnover.
   - Bid-Ask Spread $< 0.5\%$ (tight institutional liquidity).
   - Minimum Market Capitalization $> 500\text{ Cr}$.
5. **Star 5: Fundamental Health**
   - Clean promoter holding, low pledged shares, positive ROCE/ROE.

---

## 4. Train No. 920/130 Momentum Setup

A systematic trend-following train ride strategy for high-velocity swings:

### 4.1 Boarding Criteria (All Must Align)
1. **Long-Term Filter:** Daily CMP $>$ Daily EMA 200.
2. **Daily CCI Indicator:** Daily CCI (30 period, 7 smoothing) $> 0$.
3. **Multi-Timeframe RSI Alignment:**
   - Daily RSI between **40 and 55** (early cycle momentum).
   - Weekly RSI between **45 and 60** (healthy expansion).
   - Monthly RSI between **50 and 65** (macro tailwind).
4. **EMA 9 Slope Alignment:** EMA 9 strictly upward-sloping across Daily, Weekly, and Monthly charts.
5. **EMA 9/20 Alignment:** Daily EMA 9 $>$ EMA 20.

### 4.2 De-Boarding / Exit Rules
- Trailing Stop Loss set at **EMA 20** on the execution timeframe.
- Exit immediately if the 30-minute or 1-hour EMA 9 crosses below EMA 20, or if Daily CCI (30/7) drops below 0.

---

## 5. Smart Money Concepts Engine

Implemented in `src/engine/smc.py` and `src/engine/smc_decision.py`:

### 5.1 Structural Markers
- **Swing Highs & Lows:** Identified via configurable fractal bars (default `swing_length=5`).
- **Break of Structure (BOS):** Body close beyond prior swing high (Bullish BOS) or swing low (Bearish BOS) in the prevailing direction.
- **Change of Character (CHoCH):** Reversal structure breaking the swing point opposing the prevailing trend.

### 5.2 Order Blocks (OB) & Mitigation
- **Bullish Order Block:** The lowest down-candle immediately preceding an aggressive impulsive rally that creates a BOS.
- **Bearish Order Block:** The highest up-candle preceding an aggressive impulsive breakdown.
- **Mitigation Logic:** Tapping into an OB tests liquidity. An OB is mitigated and pruned **only when price breaks through the opposite extreme** (the floor for Bullish OB, or the ceiling for Bearish OB).

### 5.3 Capsule SMC Overlaps
Derived from *Smart Money Capsule 1.0*:
- **Farms Overlap:** Monthly Order Block intersecting with a Weekly Order Block.
- **Sunflowers Overlap:** Weekly Order Block intersecting with a Daily Order Block.
- **Seeds Overlap:** Daily Order Block intersecting with a 1H/3H Order Block.
- **Wyckoff Spring:** Sweep of Equal Lows (EQL) followed by an immediate pinbar close back inside the range.
- **Institutional Funding Candle (IFC):** Aggressive liquidity grab candle engineered to trap retail stop losses before moving violently in the intended direction.

---

## 6. LuxAlgo Technical & Market Structure Suite

The `src/engine/lux_*.py` suite brings institutional-grade TradingView indicators to Python:

1. **Stan Weinstein 4-Stage Analysis (`lux_weinstein.py`):**
   - Uses the 30-week (150-day) Moving Average slope and Mansfield Relative Strength (RS vs Nifty 50).
   - **Stage 1 (Base):** Flat 30W MA, oscillating price.
   - **Stage 2 (Markup):** Rising 30W MA, price breaking out on above-average volume.
   - **Stage 3 (Distribution):** Flattening 30W MA with extreme volatility.
   - **Stage 4 (Decline):** Declining 30W MA, price trading below MA.
2. **Inversion Fair Value Gaps (`lux_ifvg_sweeps.py`):**
   - Fair Value Gaps that fail to hold and get violated become Inversion FVGs (support turns resistance or vice-versa).
3. **Volume Spread Analysis (`lux_vsa.py`):**
   - Evaluates Ultra-High Volume, Stopping Volume, Absorption, No Demand, and No Supply bars based on spread-volume dynamics.
4. **Nadaraya-Watson Estimator (`lux_nwe.py`):**
   - Non-parametric kernel regression calculating dynamic Gaussian bands. Triggers mean-reversion signals when price pierces the outer $3\sigma$ bandwidth.
5. **ICT 2022 Model (`lux_model_2022.py`):**
   - Liquidity run $\rightarrow$ Market Structure Shift (MSS) with displacement $\rightarrow$ Return to Fair Value Gap (FVG) at discount ($< 50\%$ equilibrium).

---

## 7. Specialized Market Scanners

Accessible from the main interactive CLI menu (`main.py`):

| Menu ID | Scanner Name | Source Module | Focus / Objective |
|---|---|---|---|
| **`10`** | **Minervini Trend Template** | `src/scanners/minervini_screener.py` | 8-point checklist: $\text{Price} > 150\text{D} > 200\text{D}$, $200\text{D MA}$ trending up for $\ge 1\text{ month}$, price $\ge 25\%$ above 52W low, price within $25\%$ of 52W high, RS Rating $> 70$. |
| **`16`** | **Squeeze Momentum** | `src/scanners/momentum_squeeze.py` | John Carter Bollinger/Keltner compression scanner identifying explosive pre-breakout consolidations. |
| **`18`** | **Cointegration Pair Scanner** | `src/scanners/pair_scanner.py` | Engle-Granger two-step cointegration test for statistical arbitrage pairs, reporting hedge ratios, half-lives, and current spread Z-scores. |
| **`34` / `35`** | **SMC v2 Scanner & Calls** | `src/engine/smc_scanner.py` | Scans for active unmitigated Order Blocks, FVG imbalances, and actionable institutional entries. |
| **`36`** | **LuxAlgo Regimes** | `src/engine/lux_weinstein.py` | Stage Analysis, Volume Spread Analysis, and NWE channel extreme screener. |
| **`39`** | **5-Star Multi-TF Screener** | `src/scanners/capsule_screener.py` | Capsule Academy Monthly Farms, Weekly Sunflowers, and Daily Seeds scanner. |
| **`40`** | **Train No. 920/130 Scanner** | `src/scanners/capsule_screener.py` | 9/20 EMA + CCI 30/7 + Multi-TF RSI boarding momentum setup. |
| **`41`** | **Simple Turnover Surge** | `src/scanners/capsule_screener.py` | Identifies daily volume/turnover spikes $+50\%$ to $+100\%+$ with tight spreads. |
| **`42`** | **Capsule SMC Overlap Finder** | `src/scanners/capsule_screener.py` | Scans for overlapping multi-timeframe OBs, Wyckoff Springs, and IFC candles. |
