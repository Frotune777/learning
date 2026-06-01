# Sharegenius Quantitative Trading Platform — Architecture Review

> **Reviewer Role**: Principal Quant Architect, Python Technical Lead, System Design Reviewer  
> **Review Date**: 2026-06-01  
> **Codebase**: `/mnt/data/Python Project/learning`  
> **Verdict**: Promising foundation with significant gaps before production or capital deployment.

---

## Executive Summary

This codebase represents approximately **6–8 weeks of serious engineering work**. It has a genuine data pipeline, real strategy logic, position sizing, risk metrics, and a nascent backtesting harness. The documentation quality (docstrings, type hints) is above average for a personal quant project.

However, the system currently operates as a **screening tool**, not a trading platform. The architecture is a **monolith masquerading as a pipeline**. The `StockScreener` class at 1,565 lines is a God Object. There is no true Scoring Engine, no Portfolio Engine, no live signal delivery, and no Streamlit dashboard. Backtesting is bolted-on, not architected-in.

**This system should not manage real capital in its current state.**

---

## 1. Architecture Maturity Assessment

| Component | Score | Justification |
|---|---|---|
| **Data Engine** | 3 / 5 | Bhavcopy ingestion is solid. Incremental sync is well-designed. yfinance fallback is fragile. No DuckDB. NSE live data is stub-level. |
| **Indicator Engine** | 2 / 5 | TA-Lib wrappers exist but are not centralised. Indicators are computed redundantly in both `add_ta_indicators()` and inline in `screen_stocks()`. No caching. No persistence of computed indicators. |
| **Bull Run Filter** | 3 / 5 | Implemented with two correct variants (A and B). However the `0.01 ≤ diff_200_DMA ≤ 10.0%` hard-coded range is too narrow and will incorrectly exclude legitimate bull runs. DMA20 is absent from the Bull Run check as specified. |
| **CAR Filter** | 2 / 5 | The expanding-mean approach is a reasonable proxy but does NOT match the textbook CAR definition (Cumulative Average Rule should track the ratio of the current price to its own cumulative average from the 52W high, not simply whether the average is monotonically rising). Logic has edge-case bugs. |
| **Strategy Engine** | 3 / 5 | All 8 strategies are implemented as pure functions. Logic is correct. However, strategies lack a `BaseStrategy` class, they have no independent backtestability, no parameter validation, and no state. |
| **Scoring Engine** | 1 / 5 | `calculate_technical_score()` is a simplistic 100-point rule-based system. There is no true multi-factor weighted scoring engine. No ranking model. Binary filters only. |
| **Portfolio Engine** | 1 / 5 | `position_sizer.py` is excellent for single-trade sizing. But there is zero portfolio-level logic: no allocation matrix, no exposure limits, no rebalancing, no portfolio tracking. |
| **Backtesting Engine** | 2 / 5 | Two backtester classes exist (`VectorBTBacktester` and `NSEEventBacktester`). NSE costs are modeled correctly. T+1 settlement is correctly simulated. However, backtesting is not wired to any strategy. No walk-forward. No parameter optimisation. No cross-strategy comparison. |
| **Dashboard** | 1 / 5 | `daily_signal_reporter.py` produces a plain-text file. There is no Streamlit, no interactive viewer, no chart rendering, no portfolio view. |

---

## 2. Gap Analysis

| Component | Current State | Desired State | Gap | Priority | Effort |
|---|---|---|---|---|---|
| Data Engine | Bhavcopy ZIP + yfinance | NSE official + Bhavcopy primary + yfinance fallback | No primary real-time feed; DuckDB absent | **CRITICAL** | 3–4 weeks |
| Indicator Engine | Inline TA-Lib + pandas rolling | Centralised, cached, persisted indicator library | Recomputed every run; DMA20/150 incomplete | HIGH | 1–2 weeks |
| Bull Run Filter | 2-variant DMA check, narrow diff window | Full 5-DMA stack: CMP > DMA20 > DMA50 > DMA100 > DMA200 | DMA20 and DMA150 missing from filter; range too narrow | HIGH | 2–3 days |
| CAR Filter | Expanding mean monotonicity check | True CAR: cumulative avg from 52W high, slope direction | Logic is a proxy; not the actual CAR algorithm | MEDIUM | 1 week |
| Strategy Engine | 8 pure functions in `strategies.py` | `BaseStrategy` ABC with `generate_signal()`, `backtest()`, `optimize()` | No base class, not independently testable or backtestable | HIGH | 2 weeks |
| Scoring Engine | 100-pt rule-based technical score | Multi-factor weighted scoring: trend + momentum + quality + risk + catalyst | Single dimension score with no ranking | HIGH | 2–3 weeks |
| Portfolio Engine | ATR position sizer for one trade | Full portfolio: capital allocation, exposure limits, correlation matrix, rebalancing | Missing entirely | **CRITICAL** | 4–6 weeks |
| Backtesting Engine | Two isolated backtester classes | Strategy-level backtesting + walk-forward + Monte Carlo + benchmark comparison | Not wired to strategies; no parameter sweep | HIGH | 3–4 weeks |
| Dashboard | Plain-text daily report | Streamlit: portfolio view, signal explorer, backtest visualiser, sector view | Missing entirely | HIGH | 3–5 weeks |
| ML Gatekeeper | Random Forest direction classifier | Calibrated probabilistic gatekeeper with walk-forward + feature store | Trained naively, no persistence, not integrated into signal flow | MEDIUM | 2–3 weeks |
| Data Validation | None | Schema validation, anomaly detection, forward-fill policy | No validation layer | HIGH | 1–2 weeks |
| Corporate Actions | 20% price gap detection heuristic | Full NSE corporate action API integration with adjustment factors | Heuristic only; no authoritative source | HIGH | 2–3 weeks |
| Live Signal Delivery | Text file | Webhooks / Telegram / email with structured signal JSON | Missing | MEDIUM | 1–2 weeks |
| DuckDB Analytics | Not present | In-process OLAP queries over Parquet data | Missing | MEDIUM | 1 week |
| Test Coverage | ~19 test files, partial | 80%+ coverage, integration tests for full pipeline | Tests exist but many are shallow mocks | MEDIUM | 2–3 weeks |

---

## 3. Strategy Coverage Matrix

| Strategy | Implemented | Partially Implemented | Needs Refactor | Missing Indicators | Backtest Ready |
|---|---|---|---|---|---|
| **Bull Run** | ✅ (2 variants) | — | ✅ DMA20 missing from check; narrow diff range | DMA20 in filter, DMA150 in SL variant | ❌ |
| **CAR** | ⚠️ Proxy only | ✅ | ✅ Algorithm is wrong | None | ❌ |
| **GTT (Bottom Out)** | ✅ | — | — | None | ❌ |
| **Turtle Trading** | ✅ | — | — | None (all present) | ❌ |
| **RDX** | ✅ | — | — | None (ADX, DI+, DI-, RSI all present) | ❌ |
| **SMA100** | ✅ | — | ⚠️ Breakout logic requires previous close vs SMA crossover, which is correct but the 6-month low distance filter (≥20%) is arbitrary | 6M Low (present as 126D_LOW) | ❌ |
| **DMADMA** | ✅ (2 sub-variants) | — | ⚠️ Spec says CMP > DMA200 > DMA150; code says DMA150 > DMA200 — **reversed condition** | None | ❌ |
| **ETF Shop** | ✅ | — | — | SMA20 present | ❌ |
| **Buy Low Sell High** | ✅ | — | ⚠️ Uses 200D rolling low, not 52W low as typically defined | 200D Low present | ❌ |
| **Nifty Shop** | ✅ | — | ⚠️ Target is hardcoded at 6.28% regardless of RSI level; no dynamic target | RSI present | ❌ |

### Critical Strategy Bugs Found

1. **DMADMA (Reverse)**: The condition `cmp > sma_200 and cmp > sma_150 and diff > 0.0` where `diff = (sma_150 - sma_200) / sma_200` checks if SMA150 > SMA200 while CMP is above both. This is actually a **golden cross condition**, not a "reverse" recovery. The spec says `CMP > DMA200 > DMA150` which would mean the stock is above the 200 but the 150 hasn't crossed yet — a completely different signal. Needs clarification and likely a rewrite.

2. **Bull Run Filter variant A**: The spec requires `CMP > DMA20 > DMA50 > DMA100 > DMA200`. Current implementation only checks `CMP > DMA50, CMP > DMA100, CMP > DMA200` — **DMA20 is absent from the full bull run filter** and the alignment chain is not enforced.

3. **Nifty Shop**: RSI target of 6.28% is hardcoded for all RSI levels. In the original Sharegenius methodology, the target typically scales with the level (Level 1 = smaller target, Level 3 = larger target).

4. **CAR Algorithm**: The current implementation checks whether the expanding mean of closes from the 52W high is monotonically increasing over the last 10 days. The correct CAR algorithm should check whether the CMP is consistently trading above its own cumulative average (a slope/trend quality filter), not just whether the running average is rising.

---

## 4. Data Layer Review

### ✅ What Works Well
- **Bhavcopy ingestion** (`BhavcopyDownloader`): dual-format column mapping (old/new NSE schema), ZIP parsing, EQ filtering, OHLCV extraction — well-engineered.
- **Incremental Bhavcopy sync** (`BhavcopyIncrementalSync`): 1 HTTP call per missing trading day instead of per symbol — excellent design decision that avoids NSE rate limiting.
- **Parquet storage**: per-symbol flat files with DatetimeIndex — correct and efficient for time-series access.
- **Sync Registry** (`SyncRegistry`): tracks last sync date per symbol, supports resume — professional-grade design.
- **Corporate action detection**: 20% gap heuristic with standard split-factor matching (0.5, 0.2, 0.1, etc.) — pragmatic.
- **yfinance fallback**: with circuit-breaker, rate limiting, and batch chunking.

### ❌ Critical Data Layer Gaps

| Gap | Risk Level | Description |
|---|---|---|
| **No DuckDB** | HIGH | All analytics go through pandas. For 1,800+ symbols × 5+ years, in-memory pandas will hit memory walls. DuckDB would allow SQL queries directly on Parquet. |
| **No data validation schema** | HIGH | No schema enforcement on incoming Bhavcopy data. A column rename by NSE would silently corrupt all downstream calculations. |
| **NSE live data is a stub** | HIGH | `nse_utils.py` is 60KB but the `nse_live` module has only `nse_utils.py` with no live tick/quote feed. Intraday screener is impossible. |
| **yfinance as primary fallback** | MEDIUM | yfinance is a scraping library, not an official data source. It changes response format without warning. NSE Bhavcopy should be the primary source; yfinance should be last resort only. |
| **No survivorship bias protection** | HIGH | The system screens the top 250 by current turnover. Delisted stocks are never included in backtests. All historical backtests are therefore survivorship-biased. |
| **Corporate action handling is heuristic** | MEDIUM | The 20% gap detection is smart but will miss gradual adjustments (rights issues, special dividends). No integration with NSE corporate action announcements API. |
| **No data versioning** | MEDIUM | Parquet files are overwritten. There is no audit trail if data is corrupted by a bad incremental update. |
| **Timezone inconsistency** | MEDIUM | `_fetch_history()` has explicit IST conversion logic and `normalize()` to midnight. This is a band-aid. A proper timezone-aware DatetimeIndex throughout would eliminate this class of bug. |

---

## 5. Indicator Layer Review

### Indicator Availability

| Indicator | Available | Source | Cached | Persisted |
|---|---|---|---|---|
| DMA20 (SMA20) | ✅ | `add_ta_indicators()` | ❌ | ❌ |
| DMA50 (SMA50) | ✅ | TA-Lib | ❌ | ❌ |
| DMA100 (SMA100) | ✅ | TA-Lib | ❌ | ❌ |
| DMA150 (SMA150) | ✅ (inline rolling) | pandas rolling | ❌ | ❌ |
| DMA200 (SMA200) | ✅ | TA-Lib | ❌ | ❌ |
| ATR-14 | ✅ | TA-Lib | ❌ | ❌ |
| RSI-14 | ✅ | TA-Lib | ❌ | ❌ |
| ADX-14 | ✅ | TA-Lib | ❌ | ❌ |
| DI+ (PLUS_DI) | ✅ | TA-Lib | ❌ | ❌ |
| DI- (MINUS_DI) | ✅ | TA-Lib | ❌ | ❌ |
| 52W High | ❌ | Missing | ❌ | ❌ |
| 52W Low | ❌ | Missing | ❌ | ❌ |
| 20D High | ✅ (in screener) | pandas rolling | ❌ | ❌ |
| 20D Low | ✅ (in screener) | pandas rolling | ❌ | ❌ |
| 55D High | ✅ (in screener) | pandas rolling | ❌ | ❌ |

### Critical Indicator Problems

1. **No centralised indicator store**: `add_ta_indicators()` computes indicators on a raw OHLCV DataFrame. The main screener then **duplicates** SMA20, SMA150, 20D_LOW, 55D_HIGH, 126D_LOW, 200D_LOW as inline `df_ticker.rolling()` calls. This means indicators are computed 2× per symbol per run.

2. **No caching or persistence**: Every run recomputes all TA from scratch from the raw OHLCV Parquet. For 250 symbols × 250 trading days × 15+ indicators, this is significant CPU waste.

3. **52-Week High/Low is missing**: The CAR algorithm references the 52W high via `clean_df["High"].idxmax()` over the entire 1-year history — this is the correct approach but not a proper 52W rolling indicator exposed to strategies.

4. **DMA20 used inconsistently**: SMA_20 is computed inline in the screener but is absent from `add_ta_indicators()`. This creates a module boundary violation.

5. **EMA vs SMA ambiguity**: `ta_indicators.py` computes both EMAs (20, 50, 100, 200) and SMAs (50, 100, 200) but the screener primarily uses the SMA variants named `DMA_*`. The distinction is never made explicit to the user.

---

## 6. Strategy Engine Review

### Current Architecture (Actual)

```
StockScreener (God Object, 1565 lines)
  ├── _calculate_car_rating()
  ├── _calculate_bottom_out()
  ├── _calc_nifty_shop()        ← thin wrapper
  ├── _calc_buy_low_sell_high() ← thin wrapper
  ├── _calc_turtle_trading()    ← thin wrapper
  ├── _calc_rdx()               ← thin wrapper
  ├── _calc_100sma_breakout()   ← thin wrapper
  ├── _calc_etf_shop()          ← thin wrapper
  ├── _calc_super_bo()          ← thin wrapper
  ├── _calc_dmadma_reverse()    ← thin wrapper
  └── _calc_dmadma_no_sl()      ← thin wrapper

src/engine/strategies.py (pure functions, stateless)
  ├── calc_nifty_shop()
  ├── calc_buy_low_sell_high()
  ├── calc_turtle_trading()
  ├── calc_rdx()
  ├── calc_100sma_breakout()
  ├── calc_etf_shop()
  ├── calc_super_bo()
  ├── calc_dmadma_reverse()
  └── calc_dmadma_no_sl()
```

### Problems
- The `StockScreener._calc_*` wrapper methods add zero value — they are pure delegation. Remove them.
- Strategies cannot be backtested independently — they receive scalar values, not DataFrames.
- No `BaseStrategy` ABC means no enforced interface.
- Strategies have no parameter exposure — thresholds (25% ATR, 2% ETF pullback) are hardcoded magic numbers.
- No strategy registry — the `scanners/registry.py` exists but is empty.

### Recommended Architecture

```python
# src/strategies/base.py
class BaseStrategy(ABC):
    name: str
    category: str  # "momentum" | "mean_reversion" | "breakout" | "trend"

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> Signal: ...

    @abstractmethod
    def get_parameters(self) -> dict[str, Any]: ...

    def backtest(self, df: pd.DataFrame, **kwargs) -> BacktestResult: ...

# src/strategies/bull_run.py
class BullRunFilter(BaseStrategy):
    name = "Bull Run"
    category = "trend"
    def generate_signal(self, df: pd.DataFrame) -> Signal: ...

# src/strategies/turtle.py
class TurtleStrategy(BaseStrategy):
    name = "Turtle Trading"
    category = "breakout"
    entry_window: int = 55
    exit_window: int = 20
    atr_target_multiple: float = 3.0
    def generate_signal(self, df: pd.DataFrame) -> Signal: ...
```

---

## 7. Scoring Engine Design

### Current State
`calculate_technical_score()` awards points across 5 dimensions (Trend, RSI, MACD, Bollinger Bands, ADX) on a 0–100 scale. The output is a **scalar with no ranking**. Final lists (A/B/C) are binary filters, not scored rankings.

### Why This Is Inadequate
- A stock with RSI=65, above all MAs, and positive MACD scores the same as a stock with the same score but much higher risk.
- There is no factor for: quality (delivery %), momentum quality (Hurst), volatility regime, event risk, or sector strength.
- Binary filters produce no prioritisation within the qualifying set.

### Recommended Multi-Factor Scoring Model

| Factor | Weight | Components |
|---|---|---|
| **Trend Quality** | 25% | Bull Run alignment, DMA stack, % above 200 DMA |
| **Momentum** | 20% | RSI percentile, ADX strength, DI+ vs DI- spread |
| **CAR Quality** | 15% | CAR rating + slope duration |
| **Risk-Adjusted Return** | 15% | Sharpe-1Y, Calmar, Max Drawdown |
| **Volume / Institutional Activity** | 10% | Delivery %, volume spike vs 20D avg |
| **Volatility Regime** | 10% | VaR-1D, GARCH regime (low vol = score up) |
| **Event Catalyst** | 5% | Corporate action proximity, insider score |

```python
# Scoring Engine
class ScoringEngine:
    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        df["TREND_SCORE"]     = self._score_trend(df) * 0.25
        df["MOMENTUM_SCORE"]  = self._score_momentum(df) * 0.20
        df["CAR_SCORE"]       = self._score_car(df) * 0.15
        df["RISK_SCORE"]      = self._score_risk(df) * 0.15
        df["VOLUME_SCORE"]    = self._score_volume(df) * 0.10
        df["VOL_REGIME_SCORE"]= self._score_vol_regime(df) * 0.10
        df["CATALYST_SCORE"]  = self._score_catalyst(df) * 0.05
        df["COMPOSITE_SCORE"] = df[SCORE_COLS].sum(axis=1)
        df["RANK"]            = df["COMPOSITE_SCORE"].rank(ascending=False)
        return df
```

---

## 8. Portfolio Engine Review

### Current State: Effectively Missing

| Capability | Present | Notes |
|---|---|---|
| Single-trade position sizing | ✅ | `position_sizer.py` — excellent ATR-based sizing |
| Risk amount per trade | ✅ | 1% of portfolio per trade |
| Stop price calculation | ✅ | 1.5× ATR below CMP |
| Risk-reward target | ✅ | 2× stop distance |
| Portfolio-level capital allocation | ❌ | No maximum positions cap |
| Sector/correlation exposure limits | ❌ | No sector tracking |
| Portfolio rebalancing | ❌ | No portfolio state |
| Open P&L tracking | ❌ | No live position tracking |
| Kelly criterion / volatility targeting | ❌ | Fixed 1% per trade |
| Portfolio heat (total % at risk) | ❌ | No aggregate risk monitor |

### Recommended Portfolio Engine Architecture

```python
class Portfolio:
    max_positions: int = 15
    max_sector_exposure_pct: float = 0.25   # 25% max in any sector
    max_single_position_pct: float = 0.10   # 10% max in any stock
    total_risk_budget_pct: float = 0.10     # 10% total portfolio at risk
    
    positions: dict[str, Position]
    available_cash: float
    
    def can_add(self, signal: Signal) -> bool: ...
    def add_position(self, signal: Signal) -> None: ...
    def rebalance(self) -> list[Order]: ...
    def get_heat(self) -> float: ...  # Total % at risk across all open positions
    def to_dataframe(self) -> pd.DataFrame: ...

class PortfolioEngine:
    def allocate(self, signals: list[Signal], portfolio: Portfolio) -> list[Order]: ...
    def apply_correlation_filter(self, signals: list[Signal]) -> list[Signal]: ...
```

---

## 9. Backtesting Review

### Current Architecture

**VectorBTBacktester**: Wraps `vbt.Portfolio.from_signals()`. Correct usage. Returns 5 metrics. However:
- `fees=0.0015` flat fee does not match the `calculate_nse_costs()` function which models STT, SEBI charges, exchange fees, and stamp duty separately.
- No position sizing — assumes full capital deployment.
- No parameter for initial cash per position vs total portfolio.

**NSEEventBacktester**: Event-driven loop with T+1 settlement, NSE holiday calendar, circuit filter detection. This is well-designed but:
- Signals are binary (1=buy, 0=sell) — no partial fills, no scaling in/out.
- Allocates **all** available cash to one position — unrealistic.
- No multi-symbol capability — single stock only.
- The circuit filter uses a ±20% static limit but NSE uses 5%/10%/20% tiered limits per stock.

### Missing Backtesting Capabilities

| Feature | Status |
|---|---|
| Multi-symbol portfolio backtest | ❌ Missing |
| Walk-forward optimisation | ❌ Missing |
| Parameter sweep / grid search | ❌ Missing |
| Monte Carlo simulation | ❌ Missing |
| Benchmark comparison (vs Nifty 50) | ❌ Missing |
| Slippage model (market impact) | ❌ Missing |
| Partial fills / scaling | ❌ Missing |
| Strategy-level integration | ❌ Not wired to strategies |
| Cross-strategy correlation | ❌ Missing |

### VectorBT Usage Assessment

VectorBT is being used **correctly but minimally**. The library supports portfolio-level backtesting, parameter sweeps, and Sharpe optimisation natively. Currently only `from_signals()` is used with a 5-metric output. This is 10% of VectorBT's capability.

**Recommendation**: Use `vbt.Portfolio.from_signals()` at portfolio level with position sizing arrays, not a single flat fee, and integrate it with the strategy functions that return entry/exit Series rather than scalar signals.

---

## 10. Dashboard Review

### Current State
`daily_signal_reporter.py` (176 lines) reads CSV files and writes a plain-text advisory file. This is not a dashboard.

### Missing Dashboard Components

| Component | Status | Priority |
|---|---|---|
| Streamlit app skeleton | ❌ | HIGH |
| Daily signal view (sorted by composite score) | ❌ | HIGH |
| Portfolio view (open positions, P&L) | ❌ | HIGH |
| Strategy performance comparator | ❌ | HIGH |
| Backtest results viewer | ❌ | MEDIUM |
| Sector heatmap (correlation matrix) | ❌ | MEDIUM |
| Signal explorer (filter by strategy, RSI, sector) | ❌ | MEDIUM |
| Chart viewer (price + indicators per symbol) | ❌ | MEDIUM |
| Data quality monitor | ❌ | LOW |

### Recommended Dashboard Architecture

```
src/dashboard/
  app.py                    # Streamlit entry point
  pages/
    01_daily_signals.py     # Today's filtered signals, composite score ranked
    02_portfolio.py         # Current positions, P&L, exposure map
    03_strategy_view.py     # Per-strategy signal history, hit rate
    04_backtest_explorer.py # Run backtests, compare strategies
    05_sector_analysis.py   # Sector rotation, correlation heatmap
  components/
    signal_table.py         # Reusable styled signal table
    price_chart.py          # Lightweight chart with indicators
    score_card.py           # Per-stock composite score card
```

---

## 11. Technical Debt Report

### 🔴 Critical

| Debt Item | Location | Why It Matters |
|---|---|---|
| **God Object** — `StockScreener` is 1,565 lines with 6+ responsibilities | `src/screener.py` | Untestable in isolation, cannot be extended without introducing bugs, violates SRP |
| **DMADMA strategy logic is inverted** | `src/engine/strategies.py:282` | Produces wrong signals — would generate buys in wrong market conditions |
| **Bull Run filter missing DMA20** | `src/screener.py:792` | The full 5-DMA stack alignment is the core of the Bull Run definition; missing DMA20 makes this a weaker filter |
| **No portfolio engine** | Entire codebase | Cannot manage real capital without position-level accounting and risk budgeting |
| **Backtesting not integrated with strategies** | `src/nse_bhavcopy/backtester.py` | You cannot run a strategy backtest from a single entry point |
| **yfinance as data source** | `src/data/fetcher/prices/yfinance_fetcher.py` | Not an official data source; breaks on NSE corporate actions; cannot be used for production |

### 🟠 High

| Debt Item | Location | Why It Matters |
|---|---|---|
| **Indicator double-computation** | `screener.py` calls `add_ta_indicators()` then manually re-computes SMA20, SMA150, rolling lows | Wastes CPU, creates divergence risk if one path is updated and the other isn't |
| **CAR algorithm is incorrect** | `screener.py:_calculate_car_rating()` | Expanding mean monotonicity ≠ CAR. Will produce different results than the Sharegenius original |
| **No data validation** | Entire data layer | NSE occasionally changes column names, file formats; a silent schema change would corrupt all data |
| **`add_ta_indicators()` is in wrong module** | `src/nse_bhavcopy/ta_indicators.py` | Belongs in a top-level `indicators/` package, not inside the Bhavcopy ingestor |
| **All strategy thresholds are hardcoded** | `src/engine/strategies.py` | Cannot parameter-sweep, cannot adapt to market regime |
| **`StockScreener` has private `_calc_*` wrappers** | `src/screener.py:1498–1565` | 67 lines of boilerplate delegation; completely unnecessary |
| **`position_sizer.py` uses a for-loop over DataFrame rows** | `src/nse_bhavcopy/position_sizer.py:179` | `iterrows()` over 250 rows is fine now; over 1,800 symbols it's 7× slower than vectorised apply |
| **Survivorship bias in all backtests** | All backtesting code | Top-250 by current turnover means only survivors are tested; historical performance will be overstated |

### 🟡 Medium

| Debt Item | Location | Why It Matters |
|---|---|---|
| **`nse_utils.py` is 60KB with no tests** | `src/nse_live/nse_utils.py` | Single massive utility file with mixed concerns; high risk of hidden bugs |
| **`processed_dir` cache in screener conflicts with `data/historical/`** | `src/screener.py:186` | Two separate Parquet stores for the same data; can diverge |
| **Fyers integration is dead code** | `fyers/` directory | Partial OAuth implementation, not connected to any strategy or data pipeline |
| **`ml_classifier.py` is never called from main pipeline** | `src/ml/ml_classifier.py` | Isolated module with no integration; the ML gatekeeper concept is not used |
| **Walk-forward split is a fixed 80/20 ratio** | `src/ml/ml_classifier.py:291` | Proper walk-forward testing requires rolling windows, not a one-time split |
| **Flat-file report with no output format options** | `src/presentation/daily_signal_reporter.py` | Hard to parse by downstream systems; should produce structured JSON/CSV in addition to text |
| **No retry logic for NSE HTTP downloads** | `src/storage/downloader.py:167` (TODO noted) | Network failures during Bhavcopy download cause data gaps; exponential backoff is essential |

### 🟢 Low

| Debt Item | Location | Why It Matters |
|---|---|---|
| **`scan_profile.prof` committed to repo** | Root | Profiling artifact should be `.gitignore`d |
| **3 exported CSV files committed to repo root** | Root | Output data should not be in version control |
| **`nse_charting_response_TCS.json` (1.1MB) committed** | Root | Test fixture should be in `tests/fixtures/` |
| **`check_data_sources.py` and `check_yfinance_fixed.py` in root** | Root | Investigation scripts should be in `scratch/` or deleted |
| **`SESSION.md`, `MASTER_CONTEXT.md` in root** | Root | Meta-files for AI sessions should not be in the codebase |
| **`structlog` configured but `logging.basicConfig` also set** | `src/core/config.py:278` | Dual logging configuration causes duplicate log entries |

---

## 12. Recommended Future Architecture

```
sharegenius/
├── pyproject.toml
├── README.md
│
├── src/
│   ├── data/
│   │   ├── ingestion/
│   │   │   ├── bhavcopy_downloader.py    # NSE Bhavcopy ZIP → OHLCV
│   │   │   ├── bhavcopy_incremental.py   # Daily incremental sync (1 req/day)
│   │   │   ├── equity_master.py          # NSE symbol universe
│   │   │   └── nse_live_fetcher.py       # Intraday quotes (future)
│   │   ├── storage/
│   │   │   ├── parquet_store.py          # Per-symbol Parquet read/write
│   │   │   ├── duckdb_catalog.py         # DuckDB analytics layer over Parquet
│   │   │   └── sync_registry.py          # Sync state tracking
│   │   └── validation/
│   │       ├── schema.py                 # Pandera / Great Expectations schemas
│   │       └── anomaly_detector.py       # Price gap / outlier detection
│   │
│   ├── indicators/
│   │   ├── base.py                       # AbstractIndicator
│   │   ├── moving_averages.py            # SMA, EMA (all periods)
│   │   ├── momentum.py                   # RSI, ADX, DI+, DI-, MACD
│   │   ├── volatility.py                 # ATR, Bollinger, GARCH
│   │   ├── levels.py                     # 52W high/low, 20D, 55D, 200D highs/lows
│   │   └── indicator_engine.py           # Orchestrator: compute all, cache, persist
│   │
│   ├── filters/
│   │   ├── bull_run_filter.py            # CMP > DMA20 > DMA50 > DMA100 > DMA200
│   │   └── car_filter.py                 # Correct CAR algorithm
│   │
│   ├── strategies/
│   │   ├── base.py                       # BaseStrategy ABC
│   │   ├── gtt_bottom_out.py             # GTT / Bottom Out
│   │   ├── turtle_trading.py             # 55D breakout
│   │   ├── rdx.py                        # ADX + DI + RSI
│   │   ├── sma100_breakout.py            # 100 SMA breakout
│   │   ├── dmadma.py                     # DMADMA variants
│   │   ├── etf_shop.py                   # ETF pullback
│   │   ├── buy_low_sell_high.py          # 200D demand level
│   │   └── nifty_shop.py                 # RSI ladder
│   │
│   ├── scoring/
│   │   ├── scoring_engine.py             # Multi-factor weighted scorer
│   │   ├── factors/
│   │   │   ├── trend_factor.py
│   │   │   ├── momentum_factor.py
│   │   │   ├── risk_factor.py
│   │   │   ├── volume_factor.py
│   │   │   └── catalyst_factor.py
│   │   └── ranking.py                    # Composite score → ranked list
│   │
│   ├── portfolio/
│   │   ├── portfolio.py                  # Portfolio state, positions, cash
│   │   ├── position.py                   # Individual position tracking
│   │   ├── position_sizer.py             # ATR-based sizing (existing, keep)
│   │   ├── allocation_engine.py          # Capital allocation across signals
│   │   ├── risk_manager.py               # Exposure limits, correlation checks
│   │   └── rebalancer.py                 # Periodic rebalancing logic
│   │
│   ├── backtesting/
│   │   ├── vectorbt_runner.py            # VectorBT integration (enhanced)
│   │   ├── event_backtester.py           # NSE event-driven backtester (existing)
│   │   ├── walk_forward.py               # Walk-forward test harness
│   │   ├── monte_carlo.py                # Monte Carlo simulation
│   │   ├── metrics.py                    # Sharpe, Calmar, Sortino, etc.
│   │   └── benchmark.py                  # vs Nifty 50 comparison
│   │
│   ├── ml/
│   │   ├── gatekeeper.py                 # Signal probability filter (integrated)
│   │   ├── feature_store.py              # Persistent feature engineering
│   │   └── model_registry.py             # Versioned model persistence
│   │
│   ├── dashboard/
│   │   ├── app.py                        # Streamlit main entry
│   │   └── pages/
│   │       ├── 01_daily_signals.py
│   │       ├── 02_portfolio.py
│   │       ├── 03_strategy_view.py
│   │       ├── 04_backtest_explorer.py
│   │       └── 05_sector_analysis.py
│   │
│   ├── core/
│   │   ├── config.py                     # (existing, good)
│   │   ├── signal.py                     # Signal dataclass
│   │   ├── events.py                     # Event bus for live trading future
│   │   └── logging.py                    # Unified logging setup
│   │
│   └── reports/
│       ├── daily_advisory.py             # Structured JSON + text report
│       └── performance_report.py         # Portfolio performance summary
│
└── tests/
    ├── unit/
    │   ├── indicators/
    │   ├── strategies/
    │   ├── scoring/
    │   └── portfolio/
    ├── integration/
    │   ├── test_full_pipeline.py
    │   └── test_backtest_pipeline.py
    └── fixtures/
        └── TCS_sample.parquet
```

---

## 13. Implementation Roadmap

### Phase 1 — Foundation Fixes (Weeks 1–2)
**Goal**: Fix critical bugs, clean the God Object, consolidate data paths.

**Tasks**:
- [ ] Fix `DMADMA reverse` condition (inverted logic)
- [ ] Add DMA20 to the Bull Run filter chain
- [ ] Extract `StockScreener` into separate classes: `ScreenerPipeline`, `BullRunFilter`, `CARFilter`, `GTTFilter`
- [ ] Eliminate the `_calc_*` wrapper methods in `StockScreener`
- [ ] Consolidate indicator computation — remove all inline `df_ticker.rolling()` calls in `screener.py`; use only `add_ta_indicators()`
- [ ] Add DMA20 to `add_ta_indicators()` (currently it only computes EMA20/SMA50/100/200)
- [ ] Add 52W High/Low as proper rolling indicators
- [ ] Add data schema validation (Pandera or `pydantic`) on Bhavcopy ingestion
- [ ] Delete `scan_profile.prof`, CSV exports, `SESSION.md`, `MASTER_CONTEXT.md` from repo root
- [ ] Move `check_*.py` investigation scripts to `scratch/`

**Dependencies**: None  
**Deliverables**: Bug-free filtering logic, clean module boundaries  
**Estimated Effort**: 2 developers × 2 weeks  
**Risks**: Refactoring may break existing tests; run full test suite before and after each change

---

### Phase 2 — Indicator Engine (Weeks 3–4)
**Goal**: Centralised, cached, persisted indicator library.

**Tasks**:
- [ ] Create `src/indicators/` package
- [ ] Implement `IndicatorEngine` with a registry of all required indicators
- [ ] Persist computed indicators into the Parquet files (separate columns from OHLCV)
- [ ] Implement incremental indicator update (only compute new rows)
- [ ] Add DuckDB catalog over `data/historical/` Parquet files
- [ ] Implement 52W High/Low, 20D/55D high/low as first-class indicators
- [ ] Add Nifty50 as a benchmark symbol in the data store

**Dependencies**: Phase 1  
**Deliverables**: `IndicatorEngine` class, DuckDB catalog, no more double-computation  
**Estimated Effort**: 2 developers × 2 weeks  
**Risks**: DuckDB integration requires testing across different Parquet schemas

---

### Phase 3 — Strategy Engine Refactor (Weeks 5–7)
**Goal**: `BaseStrategy` ABC, independently testable, independently backtestable strategies.

**Tasks**:
- [ ] Define `BaseStrategy` ABC with `generate_signal(df)`, `get_parameters()`, `backtest(df)`
- [ ] Refactor all 8 strategies to `BaseStrategy` subclasses
- [ ] Fix CAR algorithm to use correct cumulative average comparison
- [ ] Expose all strategy parameters as configurable with defaults
- [ ] Implement `StrategyRegistry` — lookup by name, category
- [ ] Wire each strategy to `NSEEventBacktester` for per-strategy backtesting
- [ ] Add unit tests for each strategy with synthetic OHLCV data

**Dependencies**: Phase 2  
**Deliverables**: 8 strategy classes, each independently backtestable  
**Estimated Effort**: 2 developers × 3 weeks  
**Risks**: Refactoring CAR algorithm may change existing signal output; document the change

---

### Phase 4 — Scoring Engine (Weeks 8–9)
**Goal**: Multi-factor weighted scoring and ranked signal output.

**Tasks**:
- [ ] Design factor weight matrix (see Section 7)
- [ ] Implement `ScoringEngine` with pluggable factors
- [ ] Replace binary `TREND_STATUS == "In Bull Run"` filters with composite score thresholds
- [ ] Implement `FinalList`, `SwingList`, `SuperList` as score-ranked outputs, not binary filters
- [ ] Add `COMPOSITE_SCORE` and `RANK` columns to all output CSVs
- [ ] Integrate `MLClassifier` as an optional signal confidence filter

**Dependencies**: Phase 3  
**Deliverables**: Ranked signal output, scoring factor breakdown per stock  
**Estimated Effort**: 2 developers × 2 weeks  
**Risks**: Changing from binary filters to scored ranking will change the stock lists; validate against historical lists

---

### Phase 5 — Portfolio Engine (Weeks 10–12)
**Goal**: Full portfolio-level capital allocation, risk management, rebalancing.

**Tasks**:
- [ ] Implement `Portfolio` class with position tracking, available cash, sector exposure
- [ ] Implement `PortfolioEngine.allocate()` — converts ranked signals to orders given portfolio constraints
- [ ] Add `max_positions`, `max_sector_exposure`, `total_risk_budget` controls
- [ ] Implement correlation filter — don't add highly correlated positions (r > 0.8)
- [ ] Implement basic rebalancing (weekly/monthly review)
- [ ] Connect `position_sizer.py` to `PortfolioEngine` — size each position against the remaining risk budget
- [ ] Add `Portfolio.to_dataframe()` for dashboard export

**Dependencies**: Phase 4  
**Deliverables**: Portfolio management layer, order generation  
**Estimated Effort**: 2 developers × 3 weeks  
**Risks**: High complexity; start with a simplified allocation model and iterate

---

### Phase 6 — Backtesting Engine (Weeks 13–15)
**Goal**: End-to-end backtestable strategies with walk-forward and benchmark comparison.

**Tasks**:
- [ ] Integrate `BaseStrategy.backtest()` with `NSEEventBacktester`
- [ ] Implement walk-forward testing with rolling windows (e.g. 252-day train, 63-day test)
- [ ] Add multi-symbol portfolio backtest via VectorBT
- [ ] Implement benchmark comparison vs Nifty 50 (Alpha, Beta, Information Ratio)
- [ ] Add Monte Carlo simulation (randomise entry/exit timing within signal window)
- [ ] Implement parameter sweep for each strategy (ATR multiple, RSI thresholds, etc.)
- [ ] Add slippage model: assume execution at next day's open + 0.1% market impact
- [ ] Fix survivorship bias: use the symbol universe as it existed at each historical date

**Dependencies**: Phase 5  
**Deliverables**: Walk-forward backtest runner, parameter optimisation CLI  
**Estimated Effort**: 2 developers × 3 weeks  
**Risks**: Survivorship bias correction requires historical Bhavcopy symbol lists — must archive symbol sets by date

---

### Phase 7 — Dashboard (Weeks 16–19)
**Goal**: Production-grade Streamlit dashboard.

**Tasks**:
- [ ] Create Streamlit app skeleton with multi-page layout
- [ ] Build `Daily Signals` page: scored/ranked signal table, filter by strategy, sector, score
- [ ] Build `Portfolio` page: current positions, P&L, sector exposure pie, risk heat
- [ ] Build `Strategy View` page: per-strategy hit rate, signal history, performance chart
- [ ] Build `Backtest Explorer`: run backtests inline, visualise equity curves, drawdown
- [ ] Build `Sector Analysis`: correlation heatmap, sector rotation chart
- [ ] Add `Price Chart` component with DMA overlays and signal annotations
- [ ] Implement live refresh (auto-refresh after Bhavcopy sync completes)

**Dependencies**: Phase 6  
**Deliverables**: Fully functional Streamlit dashboard  
**Estimated Effort**: 2 developers × 4 weeks  
**Risks**: Streamlit's state management can be tricky for complex pages; use `st.session_state` carefully

---

### Phase 8 — Research and Optimisation (Weeks 20–24)
**Goal**: Institutional-grade signal quality, ML integration, regime-aware parameters.

**Tasks**:
- [ ] Walk-forward optimise all strategy parameters per market regime (bull/bear/sideways)
- [ ] Implement volatility regime-adaptive position sizing (reduce size in high-vol regimes)
- [ ] Train and persist ML gatekeeper model with proper walk-forward CV
- [ ] Implement factor momentum (strategy rotation based on trailing performance)
- [ ] Add sector exposure scoring to the scoring engine
- [ ] Implement live NSE data feed (WebSocket or polling) for intraday screener
- [ ] Add alerting system (Telegram bot or email) for signal delivery
- [ ] Performance attribution analysis: which factors drive returns

**Dependencies**: Phase 7  
**Deliverables**: Regime-aware, ML-enhanced, institutional-grade signal pipeline  
**Estimated Effort**: 2 developers × 5 weeks  
**Risks**: Live data feed integration is complex; intraday screener requires significant infra

---

## Summary: The Brutal Truth

This system has **better bones than most personal quant projects**. The data pipeline is genuine engineering, not a notebook experiment. The strategy logic is correct for 7 of 9 strategies. The risk metrics (Sharpe, Calmar, Beta, VaR, Hurst) are implemented correctly. The NSE event backtester with T+1 settlement and circuit filters is impressive.

But the architecture is **a screening tool trying to become a trading platform**. The `StockScreener` God Object must be dismantled. The portfolio layer must be built from scratch. The backtesting engine must be wired to strategies. The dashboard does not exist.

**Before managing real capital**: Phases 1–5 are non-negotiable. The DMADMA bug alone could generate wrong signals. The lack of a portfolio engine means you have no risk budget tracking. The binary filter system means you're not ranking by quality, just by inclusion.

**Timeline to institutional grade**: 24 weeks of focused development with 2 engineers. This is realistic.
