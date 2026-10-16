# Dossier Reconciliation Section Specification (Unit 18)

## 1. Overview & Objective

The Institutional Quantitative Dossier (`src/engine/llm_report.py`) generates a multi-dimensional assessment of an individual symbol across distinct quantitative engines.

### Dossier Section Ordering (Target Layout)
1. **Executive Summary & Market Snapshot** (Includes 10W MA Weinstein Stage + Footnote)
2. **Actionable SMC Trading Setup** (Direction, Entry, SL, TP1/TP2, RR)
3. **Institutional Smart Money Structure** (Swing/Internal bias, Equilibrium, Discount/Premium, FVGs, OBs)
4. **Auction Market & Volume Profile Geometry** (VPOC, VAH, VAL, VSA)
5. **Non-Parametric & Digital Filter Regimes** (NWE Envelope, Savitzky-Golay)
6. **Classical Technical & Indicator Suite** (RSI, ADX, ATR, EMA 20, SMA 50, SMA 200, MACD)
7. **Quantitative Lens Reconciliation** *(Target Position: Inserted before LLM prompting)*
8. **Instructions for LLM Prompting / Strategy Formulation** *(Closing prompt for downstream consumer)*

On complex market setups (e.g., TCS on 2026-10-16), analytical lenses can yield conflicting perspectives across timeframes:
- **Section 1**: Technical Composite Score = 78/100 (`BUY`), yet Weinstein Stage = `Stage 4 (Declining / Markdown)`.
- **Section 3**: SMC Swing Trend = `BULLISH`, Internal Shift = `BULLISH`.
- **Section 5**: NWE Context = `Extreme Overbought (Mean Reversion Short Bias)`.
- **Section 6**: Price is above SMA 50 (`Bullish`), but below SMA 200 (`Secular Bear`).

**Objective:**
Introduce a deterministic **Section 7 — Quantitative Lens Reconciliation** placed immediately before the closing LLM prompting instructions. It systematically parses, contrasts, and explains inter-lens divergences without forcing an artificial single call, leaving the operator and LLM with a structured synthesis of tactical vs. strategic tension.

---

## 2. One-Line Lens Definitions

Every lens operates on a distinct mathematical domain and temporal horizon:

| Quantitative Lens | Temporal Horizon | Operational Definition |
| :--- | :--- | :--- |
| **Weinstein Stage** | Macro / Intermediate (10W / 50D) | Moving-average slope and stage classification defining the broader cyclical regime. |
| **SMC Structure** | Medium-term Swing & Internal | Institutional order-flow structure, liquidity levels, and market structure shifts (BOS/CHoCH). |
| **Composite Score** | Multi-Factor Composite | Weighted multi-metric baseline combining momentum (RSI), trend (ADX/SMA), and volatility (ATR). |
| **Nadaraya-Watson Envelope (NWE)** | Short-term Statistical | Non-parametric kernel regression establishing dynamic volatility bands and mean-reversion extremes. |
| **Savitzky-Golay Filter** | Short-term Digital Filter | Polynomial smoothing derivative identifying rate-of-change inflections and local momentum turning points. |
| **Volume Spread Analysis (VSA)** | Bar-by-Bar / Real-Time | Volume-price spread relationship assessing market conviction (e.g., No-Demand vs. No-Supply). |

---

## 3. Conflict Resolution Table

When two lenses present divergent indications, the reconciliation section must synthesize the tension using explicit, pre-defined phrasing:

| Lens Conflict Pair | Condition Example | Deterministic Phrasing / Reconciliation Synthesis |
| :--- | :--- | :--- |
| **Weinstein vs. SMC** | Weinstein `Stage 4 (Declining)` + SMC `BULLISH` | "Counter-trend rally within a broader markdown regime; treat institutional buy setups as tactical pullbacks rather than secular reversals." |
| **Weinstein vs. SMC** | Weinstein `Stage 2 (Advancing)` + SMC `BEARISH` | "Short-term structural pullback within an advancing macro markup stage; monitor discount zones for trend continuation support." |
| **SMC vs. NWE** | SMC `BULLISH` + NWE `Extreme Overbought` | "Bullish structural expansion has reached an upper statistical volatility extreme; elevated risk of sharp mean-reversion pullback before further upside." |
| **SMC vs. NWE** | SMC `BEARISH` + NWE `Extreme Oversold` | "Bearish structural impulse is extended into the lower statistical envelope; high probability of a short-squeeze or snapback bounce." |
| **Composite vs. Weinstein** | Composite `BUY` (≥70) + Weinstein `Stage 4` | "Intermediate technical momentum and indicator alignment conflict with macro stage headwinds; high-beta rally occurring below declining moving averages." |
| **Composite vs. Weinstein** | Composite `SELL` (≤30) + Weinstein `Stage 2` | "Temporary indicator exhaustion or consolidation within an advancing stage; underlying macro trend remains constructive." |
| **SMC Trend vs. Savitzky-Golay** | SMC `BULLISH` + SG `Bearish Turning Inflection` | "Upward trend showing local deceleration; negative second derivative suggests short-term momentum exhaustion prior to structural confirmation." |
| **SMC Trend vs. Savitzky-Golay** | SMC `BEARISH` + SG `Bullish Turning Inflection` | "Downward trend showing local deceleration; positive second derivative highlights nascent curvature bottoming." |
| **Price Trend vs. VSA** | Price Rallying / Bullish + VSA `No-Demand Bar` | "Upward price progression accompanied by low relative volume and narrow spread, signaling lack of aggressive buying conviction." |
| **Price Trend vs. VSA** | Price Declining / Bearish + VSA `No-Supply Bar` | "Downside progression on dried-up volume and narrow spread, suggesting exhaustion of aggressive selling pressure." |
| **SMA 50 vs. SMA 200** | Price > SMA 50, but Price < SMA 200 | "Intermediate cyclical recovery operating below the secular 200-day moving average; long-term macro resistance remains overhead." |

---

## 3.1 Pairs That Do Not Conflict by Construction

The following 6 lens pairings frequently co-move or measure complementary properties rather than conflicting. The implementation **MUST skip** generating conflict commentary for these pairs:

1. **Composite / SMC**: Composite measures aggregate multi-factor indicator health (0–100), while SMC identifies discrete structural price zones (OB/FVG/liquidity pools); momentum strength and structural location frequently co-move and reinforce each other.
2. **Composite / NWE**: Composite scores trend and momentum persistence, while NWE defines a dynamic kernel envelope; strong trending moves frequently reach outer statistical envelopes during sustained markup/markdown.
3. **Composite / VSA**: Composite aggregates trailing multi-day indicator momentum, while VSA measures single-bar spread-to-volume ratio; single-bar volume spread qualifies candle execution rather than conflicting with aggregate trend.
4. **SMC / VSA**: SMC maps structural levels of institutional interest (order blocks, fair value gaps), while VSA classifies the transaction effort at those levels; VSA acts as a bar-level confirmation filter for SMC zone tests rather than an opposing signal.
5. **NWE / VSA**: NWE establishes statistical distribution boundaries, while VSA describes the volume spread of the boundary contact; touching an envelope on low volume indicates exhaustion while touching on ultra-high volume indicates absorption.
6. **NWE / Savitzky-Golay**: NWE models the spatial envelope around price, while Savitzky-Golay computes digital smoothing derivatives; a curvature inflection near an envelope boundary is complementary curve-fitting telemetry rather than a directional conflict.

---

## 4. Architectural Rules: MUST and MUST NOT

### MUST
1. **Target Position:** Must be rendered as Section 7 (`## 7. Quantitative Lens Reconciliation`), positioned before Section 8 (`## 8. Instructions for LLM Prompting / Strategy Formulation`).
2. **Name Each Disagreement Explicitly:** If Weinstein is Stage 4 and SMC is Bullish, the section MUST explicitly state both readings and characterize the relationship (e.g., counter-trend bounce).
3. **Prioritize Conservative Lens on Risk:** When a short-term lens indicates aggressive opportunity but a macro lens indicates systemic risk (e.g., Weinstein Stage 4), the section MUST emphasize tighter risk management (e.g., reduced position sizing, trailing stop-losses).
4. **Report Coherent Alignment:** If all lenses align (e.g., Stage 2 Advancing + SMC Bullish + NWE Normal + High Composite Score), the section MUST explicitly state full multi-timeframe confluence.
5. **Skip Co-moving Pairs:** Omit conflict generation for the 6 pairs defined in Section 3.1.

### MUST NOT
1. **MUST NOT Resolve into a Single Unified "Call":** The section must never output "Final Verdict: BUY" or replace Section 2's specific SMC trade trigger. Final trade synthesis and trade structuring remain the responsibility of Section 8 / the downstream LLM reasoner.
2. **MUST NOT Invent Phantom Signals:** Never mention "smart money accumulation", "institutional absorption", or "insider footprints" unless supported by explicit quantitative evidence from VSA (`No-Supply`/`No-Demand`) or SMC Order Blocks.
3. **MUST NOT Alter Prior Dossier Sections:** Sections 1 through 6 retain their exact existing structure, keys, and values (with the sole exception of the corrected MA label and footnote in Section 1).

---

## 5. Resolution of the 30W vs. 10W MA Label Bug

### Current Implementation Defect
In `src/engine/llm_report.py`:
- Line 128:
  ```python
  w_res = calculate_weinstein_stage(df_lower, ma_weeks=10, slope_weeks=2, is_daily=True)
  ```
- Line 152:
  ```python
  doc.append(f"- **Macro Weinstein Stage:** `{w_res.stage_name}` (30W MA: ₹{w_res.ma_value:,.2f}, Slope: {w_res.ma_slope_pct:+.2f}%, Vol Ratio: {w_res.volume_ratio:.2f}x)")
  ```

### Consumer Audit of `calculate_weinstein_stage`
A full codebase audit confirms three active call sites for `calculate_weinstein_stage`:
1. `src/cli/menus.py:2430`: `calculate_weinstein_stage(df, ma_weeks=10, slope_weeks=2, is_daily=True)`
2. `src/dashboard/views/quantitative_view.py:105`: `calculate_weinstein_stage(df, ma_weeks=10, slope_weeks=2, is_daily=True)`
3. `src/engine/llm_report.py:128`: `calculate_weinstein_stage(df_lower, ma_weeks=10, slope_weeks=2, is_daily=True)`

**Audit Finding:** All active callers across CLI, Streamlit dashboard, and LLM report explicitly pass `ma_weeks=10, slope_weeks=2, is_daily=True`. Zero callers assume or depend on 30W semantics in downstream calculation or logic.

### Chosen Option: Option A (Retain 10W MA Parameter, Correct Label & Add Footnote)
1. **Stated Justification:**
   - The repository's intermediate quantitative architecture intentionally evaluates a 10-week cycle on daily data (10 weeks × 5 trading days = 50 trading days) to provide responsive stage transitions suitable for swing and position trading across 60+ bar daily histories.
   - Forcing `ma_weeks=30` (150 trading days) would triple the lag, reduce stage sensitivity, and break parity with the existing dashboard and CLI table classifications.
   - The string `"30W MA"` was an erroneous copy-paste label artifact from the Pine Script reference name.
2. **Required Updates:**
   - Change Section 1 label from `30W MA:` to `10W MA:`.
   - Add a one-line explanatory footnote immediately beneath the Weinstein line in Section 1:
     `  * *(Classifier uses a 10W MA, faster than Weinstein's original 30W.)*`
3. **Relationship to Classical TA (Section 6):**
   - **Note on Moving Average Equivalence:** `10W MA ≡ SMA_50 by construction` ($10 \text{ weeks} \times 5 \text{ trading days/week} = 50 \text{ trading days}$).
   - Both references are deliberately retained: Section 1 uses the 10W MA within the Weinstein Stage classification framework (incorporating slope and volume ratio), while Section 6 retains `SMA_50` as part of the standard classical technical benchmarking stack (alongside EMA 20 and SMA 200).

---

## 6. Implementation Design (`_build_reconciliation_section`)

### Function Signature
```python
def _build_reconciliation_section(
    cmp: float,
    smc_res: SMCResult,
    w_res: WeinsteinResult,
    nwe_res: NWEResult,
    sg_res: SGResult,
    vsa_res: VSAResult,
    ta_score_dict: dict[str, Any],
    sma_50: float,
    sma_200: float,
) -> list[str]:
    """
    Synthesize multi-lens disagreements and confluences into Markdown Section 7.
    """
```

### Output Markdown Structure
```markdown
## 7. Quantitative Lens Reconciliation

### 7.1 Macro vs. Micro Structural Alignment
- **Macro Weinstein Stage (`{w_res.stage_name}`):** [Macro cyclical context]
- **SMC Institutional Trend (`{smc_trend}`):** [Order flow direction]
- **Structural Synthesis:** [Specific phrasing from Conflict Resolution Table]

### 7.2 Statistical Extremes & Momentum Tension
- **Composite Technical Score:** {score}/100 (`{rating}`)
- **Nadaraya-Watson Envelope:** {nwe_context}
- **Savitzky-Golay Digital Filter:** {sg_context}
- **Mean-Reversion vs. Continuation:** [Explicit tension or alignment]

### 7.3 Volume Conviction & Auction Context
- **Volume Spread Analysis:** {vsa_status}
- **Value Area Position:** {cmp_va_pos}
- **Volume Confirmation Assessment:** [Conviction commentary strictly without invented signals]
```
