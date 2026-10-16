# Unit 16 Phase 0: Baseline & Bug Verification Report

**Date:** 2026-10-16  
**Commit:** `8e93b85` (Unit 15 complete, clean tree)  
**Scope:** Verification of symbol analysis, SMC engine, consensus, scoring, and scanner issues prior to any modifications.

---

## 1. SMC Scan CLI Execution & Setup Breakdown

### Command Executed
```bash
uv run python main.py --data-dir data --hist-dir data/historical smc-scan
```

### Execution Output & Metrics
- **Securities Scanned:** 2,694 / 2,700 Parquet files in `data/historical/1d`.
- **Exit Code:** 0.
- **Total Actionable Decisions Generated:** 53.

### Call Breakdown by Setup Type
| Setup Type | Direction | Count | Percentage |
| :--- | :--- | :--- | :--- |
| `FVG_FILL` | BUY | 47 | 88.7% |
| `OB_DEMAND_TAP` | BUY | 4 | 7.5% |
| `OB_SUPPLY_TAP` | SELL | 2 | 3.8% |
| `FVG_FILL` | SELL | 0 | 0.0% |
| **Total** | | **53** | **100.0%** |

### Evaluation of Bug Claims
1. **Order Block Calls (Demand/Supply Tap):**
   - **Report Claim:** "0 OB_DEMAND_TAP / 0 OB_SUPPLY_TAP".
   - **Verification Finding:** **Partially refuted as absolute zero, but root cause confirmed.** Across the entire 2,694-stock universe, only 6 OB setups triggered (4 demand, 2 supply). The root cause in `src/engine/smc.py:273-293` is verified: `if touch_price <= ob.bar_high: ob.mitigated = True` deletes order blocks prematurely when price touches the top of the demand zone, rather than when price breaches the floor (`low < ob.bar_low`), which directly contradicts the reference LuxAlgo SMC Pine logic (`luxalgo_smc_source.pine:487,493`).
2. **Bearish FVG Calls:**
   - **Verification Finding:** **Confirmed (0 calls).** In `src/engine/smc_decision.py:118-148`, the `2. BEARISH SCENARIOS` block only checks `A. Bearish Order Block Test`. The `B. Bearish FVG Fill` handler is completely absent from the source code.
3. **CLI Formatting Artifact:**
   - **Verification Finding:** **Confirmed.** The scan produced lines:
     ```text
     None: Scanned 2694 securities.
     None: All calls committed to SQLite DB at: data/smc_calls.sqlite
     ```
     This is caused by `print(f"\n{ok('...')}: ...")` where `ok()` in `src/cli/formatters.py:139` prints directly and returns `None`.

---

## 2. Screener/Analyze CLI & Composite Rank Columns

### Code Inspection
- Checked `StockScreener.enrich_analysis` in `src/screener.py:1414-1541`.
- Checked `ScoringEngine` in `src/scoring/scoring_engine.py:15-103`.

### CSV Header Audit
Inspected existing processed outputs in `data/processed/`:
- `top_250_analyzed_20260526.csv`: 16 columns (no factor scores, no composite score, no rank).
- `analysis_results_—_2026-06-09_20260609_1507.csv`: 97 columns (no factor scores, no composite score, no rank).
- `consensus_leaderboard_20260601_1841.csv`: 61 columns (no factor scores, no composite score, no rank).

### Verification Finding
**CONFIRMED.** `ScoringEngine` exists as a complete 7-factor ranking engine (`TREND_FACTOR_SCORE`, `MOMENTUM_FACTOR_SCORE`, `CAR_FACTOR_SCORE`, `RISK_FACTOR_SCORE`, `VOLUME_FACTOR_SCORE`, `VOLATILITY_FACTOR_SCORE`, `CATALYST_FACTOR_SCORE`, `COMPOSITE_SCORE`, `RANK`), but is **never imported or invoked** in `StockScreener.screen_stocks` or `StockScreener.enrich_analysis`. Grep confirmed callers exist only in `src/dashboard/pages/01_daily_signals.py` and `tests/test_scoring.py`.

---

## 3. Data Directory Audit: `user_data/stock_data` vs `data/historical`

### Code Inspection
- `src/data/storage.py:350-353`:
  ```python
  self.timeframe = timeframe
  self.base_path = Path("user_data/stock_data") / timeframe
  ```
- `src/engine/scanner.py:123`:
  ```python
  data = self._get_data_optimized(symbol, primary_tf, "1y", shared_cache)
  # queries self.fetcher.fetch_data -> self.dataRepository.load_data(symbol)
  ```

### Filesystem Audit
- `user_data/stock_data/1d`: Contains **50 files** (Nifty 50), last modified Oct 15 01:44, ending at bar date `2026-10-14`.
- `data/historical/1d`: Contains **2,699 files** (full NSE equity universe), synced to `2026-10-15`.

### Git History & Pipeline Origin
- Checked commit `fa81afb`: `user_data/` is the storage tree imported from the legacy `screeni-py` merge.
- The canonical pipeline built throughout Units 1–15 uses `data/historical/1d`.
- **Finding:** The split was not an intentional architectural design for separate datasets; it is an incomplete convergence artifact. The `Scanner` (`UltraOptimizedMultiTimeframeScanner`) queries `DataRepository` and thus only finds the 50 cached Nifty stocks in `user_data/`, ignoring the 2,649 other stocks in `data/historical/1d`.

---

## 4. Live Path Audit: `src/analysis/patterns.py`

### Grep Audit Across Active Codebase
1. `src/engine/scanner.py:53, 134`:
   ```python
   from src.analysis.patterns import SMCPatterns
   ...
   smc = SMCPatterns.analyze_smc(data)
   ```
2. `src/ml/engineer.py:200-208`:
   ```python
   from src.analysis.SMCPatterns import SMCPatterns, WilliamsFractals
   bos = SMCPatterns.detect_bos(df)
   choch = SMCPatterns.detect_choch(df)
   ```
3. Callers of `scanner.py`:
   - `src/engine/orchestrator.py:15` (`MultiTimeframeScanner`)
   - `src/cli/interactive_scanner.py:198, 200, 202` (interactive Quick Scan, Custom Scan, Watchlist Scan)
   - `src/cli/actions.py:459` (`cmd_train_ml`, `cmd_run_optimizer`)

### Lookahead Analysis in `SMCPatterns.detect_order_blocks`
- Line 83: `next_close = data["Close"].shift(-1)`
- **Finding:** **CONFIRMED on live path.** When running scans through `interactive_scanner.py` or training models via `cmd_train_ml`, `SMCPatterns.analyze_smc` is invoked, which executes `detect_order_blocks` containing `shift(-1)`. This represents an active lookahead leak on that subsystem.

---

## 5. Phase 0 Summary of Findings

| Item | Component | Issue | Verification Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `smc.py` | Order block mitigation inverted | **Confirmed** (6/2,694 OB calls vs 47 FVG) | Fix in Phase 1 |
| 2 | `smc_decision.py` | Missing Bearish FVG fill | **Confirmed** (0 bearish FVG calls, branch missing) | Fix in Phase 1 |
| 3 | `formatters.py` | `ok()` prints and returns `None` | **Confirmed** (`None: Scanned...` in CLI output) | Fix in Phase 3 |
| 4 | `consensus_engine.py` | Dead branch `elif net_score >= 5.0` | **Confirmed** in line 270 | Fix in Phase 2 |
| 5 | `consensus_engine.py` | `is_nifty_bank` mapped to `^CNXPSUBANK` | **Confirmed** in line 68 | Fix in Phase 2 |
| 6 | `scoring_engine.py` | NaN volatility gets penalized 10.0 | **Confirmed** in line 255 | Fix in Phase 2 |
| 7 | `screener.py` | `ScoringEngine` not wired in `enrich_analysis` | **Confirmed** (composite columns missing) | Fix in Phase 2 |
| 8 | `scanner.py` | Sell SL/TP inverted for short calls | **Confirmed** in line 737 | Fix in Phase 3 |
| 9 | `scanner.py` | Rolling mean delta used as fake ATR | **Confirmed** in line 732 | Fix in Phase 3 |
| 10 | `daily_signals.py` | Dashboard prefers analyzed over enriched | **Confirmed** in line 89 | Fix in Phase 3 |
| 11 | `storage.py` | `DataRepository` points to `user_data` (50 stocks) | **Confirmed** merge artifact | Fix in Phase 3 |
| 12 | `patterns.py` | Lookahead `shift(-1)` in order blocks | **Confirmed** on live orchestrator/ML path | Fix in Phase 3 |

---

## 6. Phase 1 Results: SMC Core Fixes

### Before vs. After Universe Call Counts (2,694 Securities)
| Setup Type | Direction | Phase 0 (Before) | Phase 1 (After) | Net Change |
| :--- | :--- | :--- | :--- | :--- |
| `OB_DEMAND_TAP` | BUY | 4 | **36** | +32 (+800%) |
| `OB_SUPPLY_TAP` | SELL | 2 | **23** | +21 (+1050%) |
| `FVG_FILL` | BUY | 47 | **46** | -1 (1 moved to OB) |
| `FVG_FILL` | SELL | 0 | **4** | +4 (new setup) |
| **Total** | | **53** | **109** | **+56 (+105.7%)** |

### Implemented Predicate (`src/engine/smc.py:273-293`)
```python
        # Order Block Mitigation Check
        surviving_obs = []
        for ob in active_order_blocks:
            # Bullish OB (Demand): Mitigated when price violates the floor (bar_low)
            if ob.bias == BULLISH:
                breached = (c < ob.bar_low) if close_mitigation else (l < ob.bar_low)
                if breached:
                    ob.mitigated = True
                    ob.mitigated_bar_index = i
                else:
                    surviving_obs.append(ob)
            # Bearish OB (Supply): Mitigated when price violates the ceiling (bar_high)
            else:
                breached = (c > ob.bar_high) if close_mitigation else (h > ob.bar_high)
                if breached:
                    ob.mitigated = True
                    ob.mitigated_bar_index = i
                else:
                    surviving_obs.append(ob)
        active_order_blocks = surviving_obs[-max_order_blocks:]
```

### Reference Logic
- Sourced from `docs/pine_sources/luxalgo_smc_source.pine:487, 493` (`deleteOrderBlocks`):
  - Bearish OB: `bearishOrderBlockMitigationSource > eachOrderBlock.barHigh`
  - Bullish OB: `bullishOrderBlockMitigationSource < eachOrderBlock.barLow`
  - Source definitions (`luxalgo_smc_source.pine:311, 313`):
    `bearishOrderBlockMitigationSource = orderBlockMitigationInput == CLOSE ? close : high`
    `bullishOrderBlockMitigationSource = orderBlockMitigationInput == CLOSE ? close : low`

### Deliberately Preserved Behavior
1. **Config flag `close_mitigation`:** Maintained as a configurable argument (defaulting to `False`, matching LuxAlgo's default `HIGHLOW` wick-based mitigation).
2. **Proximity and Risk Thresholds in `smc_decision.py`:** Kept exact existing thresholds:
   - Max risk: 6% of CMP (`cmp * 0.06`).
   - Risk/Reward minimum: `rr >= 1.8`.
   - Proximity tap tolerance: 1.5% for OB (`ob.bar_low <= cmp <= ob.bar_high * 1.015`), 1.5x ATR for FVG.
3. **Bearish FVG Parameters:** Built symmetrically to Bullish FVG without introducing any speculative parameters.

---

## 7. Open Questions

### 1. OB Tap Proximity Guard Buffer (1.5% tolerance vs Strict Zone Touch)
- **Code Reference:** `src/engine/smc_decision.py:61, 124`:
  - Bullish OB: `ob.bar_low <= cmp <= ob.bar_high * 1.015` (CMP can be up to 1.5% above zone ceiling).
  - Bearish OB: `ob.bar_low * 0.985 <= cmp <= ob.bar_high` (CMP can be up to 1.5% below zone floor).
- **Observation:** In the INFY verification, the Bearish OB zone is `[1125.60, 1156.00]`. CMP was `1110.00` (1.39% below `ob.bar_low`).
  - The tap was **physically verified**: On the final bar `2026-10-15`, INFY's intraday high was `1126.70`, which crossed above `ob.bar_low` (1125.60) by 1.10 points before closing at `1110.00`.
  - **Issue for review:** The predicate tested only `ob.bar_low * 0.985 <= cmp <= ob.bar_high` (`1108.72 <= 1110.0 <= 1156.0`), allowing any CMP within 1.5% of the zone to trigger a call, even if the bar's wick never actually touched the zone. Consider whether future tuning should require `current_high >= ob.bar_low` (for supply) / `current_low <= ob.bar_high` (for demand), or tighten the 1.5% CMP proximity buffer to ≤0.5%.

### 2. Unclassified Market Regime Fall-Through (`consensus_engine.py:224-234`)
- **Code Reference:** `src/core/consensus_engine.py:224-234`:
  ```python
  if cmp > dma_200 and cmp > dma_50:
      market_state = "BULL RUN"
  elif cmp < dma_200 and cmp > dma_50:
      market_state = "RECOVERY"
  elif cmp < dma_200 and cmp < dma_50:
      market_state = "BEAR TERRITORY"
  ```
- **Unclassified Condition:**
  When `cmp > dma_200 and cmp < dma_50` (price is above long-term 200-day trend line but has pulled back below the intermediate 50-day moving average), none of the three branches match. Price silently falls through to the default `market_state = "SIDEWAYS"`.
- **Proposed Classification for Sign-off:**
  Classify `cmp > dma_200 and cmp < dma_50` explicitly as `"BULLISH_PULLBACK"` (or `"PULLBACK IN UPTREND"`). Behavior is deliberately preserved as `"SIDEWAYS"` in Phase 2 pending user sign-off.

---

## 8. Phase 2 Results: Consensus & Scoring Correctness + Wiring

### Summary of Fixes

| Component | Issue | Before | After | Regression Test |
| :--- | :--- | :--- | :--- | :--- |
| `consensus_engine.py:267-272` | Dead `elif net_score >= 5.0` branch | `if net_score >= 3.5:` swallowed `>= 5.0` | `if net_score >= 5.0:` evaluated first | `test_consensus_aggressive_regime_branch_order` |
| `consensus_engine.py:68` | Wrong Bank index symbol | `"is_nifty_bank": "^CNXPSUBANK"` | `"is_nifty_bank": "^NSEBANK"` | `test_sector_mapping_nifty_bank` |
| `scoring_engine.py:246-256` | NaN volatility penalty | `np.where(vol <= 20, ...)` mapped NaN to `10.0` | `pd.isna(vol)` explicitly maps to neutral `50.0` | `test_volatility_scoring_tiers_and_nan` |
| `screener.py:1414-1541` | `ScoringEngine` uncalled | Screener output omitted composite scores | Wired as Step 7 in `enrich_analysis` | `test_enrich_analysis_wires_scoring_engine` |
| `smc_decision.py:61, 124` | OB proximity guard buffer | CMP-only check (`ob.bar_low <= cmp <= ob.bar_high * 1.015`) | Added wick requirement: `current_low <= ob.bar_high` (Demand) / `current_high >= ob.bar_low` (Supply) | `test_bullish_ob_proximity_requires_wick_into_zone`, `test_bearish_ob_proximity_requires_wick_into_zone` |

### Screener Output CSV Column Diff
- Output file: `data/historical/top_250_enriched_20261016.csv`
- Total columns: **108** (99 before + 9 new composite columns)
- New columns added:
  1. `TREND_FACTOR_SCORE`
  2. `MOMENTUM_FACTOR_SCORE`
  3. `CAR_FACTOR_SCORE`
  4. `RISK_FACTOR_SCORE`
  5. `VOLUME_FACTOR_SCORE`
  6. `VOLATILITY_FACTOR_SCORE`
  7. `CATALYST_FACTOR_SCORE`
  8. `COMPOSITE_SCORE`
  9. `RANK`

### SMC Scan Universe Call Counts (Phase 1 vs. Phase 2B)
Scan executed over 2,694 symbols:

| Setup Type | Direction | Phase 1 | Phase 2B (Tightened Wick) | Delta |
| :--- | :--- | :--- | :--- | :--- |
| `OB_DEMAND_TAP` | BUY | 36 | **31** | -5 (-13.9%) |
| `OB_SUPPLY_TAP` | SELL | 23 | **21** | -2 (-8.7%) |
| **Total OB Calls** | | **59** | **52** | **-7 (-11.9%)** |
| `FVG_FILL` | BUY | 46 | **51** | +5 (+10.9%) |
| `FVG_FILL` | SELL | 4 | **5** | +1 (+25.0%) |
| **Total SMC Calls** | | **109** | **108** | **-1 (-0.9%)** |

> Note: Total OB calls dropped by **11.9%**, well within the ≤40% constraint threshold. Only spurious calls hovering in the 1.5% buffer without a physical zone wick were pruned.

### Open Questions Pending Sign-off
1. **Market Regime Classification (`consensus_engine.py:224-234`):**
   `cmp > dma_200 and cmp < dma_50` currently falls through to `"SIDEWAYS"`. Recommended for sign-off: classify as `"BULLISH_PULLBACK"` in Phase 3.

---

## 9. Phase 3 Results: Scanner, CLI Formatters, DataRepository, Dashboard Order, and Lookahead Fixes

### Summary of Fixes

| Component | Issue | Before | After | Regression Test |
| :--- | :--- | :--- | :--- | :--- |
| `src/engine/scanner.py:726-764` | Fake ATR and hardcoded long SL/TP | `High.rolling(14).mean() - Low.rolling(14).mean()` | Wilder ATR(14) (`talib.ATR` with true range fallback); directional SL/TP (BUY, SELL, NEUTRAL) | `tests/test_scanner.py` (5 tests) |
| `src/engine/scanner.py:881-885` | Bus emission misclassified NEUTRAL as SHORT | `"LONG" if "BUY" in signal else "SHORT"` | `"LONG"` for BUY, `"SHORT"` for SELL, `None` for NEUTRAL | `test_emit_to_bus_neutral_is_not_short` |
| `src/cli/formatters.py:136-154` | `ok/warn/err/tip` print and return `None` | `print(...)` and returns `None` (leading to `"None: ..."` f-strings) | Returns formatted string; statements wrapped in `print()` | `tests/test_cli_formatters.py` (5 tests) |
| `src/data/storage.py:349-361` | Hardcoded `user_data/stock_data` default | Hardcoded `Path("user_data/stock_data") / timeframe` | Defaults `base_path=None` to `Config.get_hist_dir() / timeframe` (`data/historical`) | `tests/test_storage.py` (2 tests) |
| `src/dashboard/pages/01_daily_signals.py:89` | Inverted CSV file priority | `analyzed_files if analyzed_files else enriched_files` | `enriched_files if enriched_files else analyzed_files` | `tests/test_dashboard_file_selection.py` (1 test) |
| `src/dashboard/pages/01_daily_signals.py:107` | Redundant inline scoring block | `ScoringEngine().score(df)` called inline | Removed redundant inline block (enriched CSVs already carry 9 composite factors) | Code inspection & unit test |
| `src/analysis/patterns.py:79-126` | Lookahead in order block detection | `next_close = data["Close"].shift(-1)` | Same-bar confirmation at bar i vs prior close (i-1) | `test_order_blocks_no_lookahead` |
| `src/analysis/patterns.py:129-163` | Lookahead in FVG detection | `shift(-1)` in `n_low` and `n_high` | Strict 3-bar past window `(i-2, i-1, i)` with no negative shifts | `test_fvg_3bar_past_window` |
| `src/analysis/patterns.py:243-269` | Lookahead in Williams Fractals | `shift(-1)` and `shift(-2)` written at peak bar i | 5-bar fractal confirmed and recorded at confirmation bar `i+2`, zero lookahead | `test_williams_fractals_last_2_rows_unconfirmed` |

### SMC Scan Universe Call Counts (Phase 3 Post-Verification)
Full universe scan over 2,694 symbols:
- Output calls: **108** (31 `OB_DEMAND_TAP`, 21 `OB_SUPPLY_TAP`, 51 `FVG_BUY`, 5 `FVG_SELL`).
- Exactly matches Phase 2B call count (108). Zero downstream regressions.
- Test Suite: **255 passed** in 62.54s (`uv run pytest -q`).




