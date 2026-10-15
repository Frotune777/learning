"""
File: src/classes/ReportingService.py
Purpose: Handle results display, table formatting, and data preparation using VisualUI.

Dependencies:
External:
- pandas>=2.0.0: [data manipulation and CSV export preparation]
- rich.console: [CLI output handling]
Internal:
- classes.VisualUI: [centralized UI rendering engine]

Key Components:
Classes:
- ReportingService: Manages formatted data output for the Stock Screener application.
Functions:
- print_results_table: Render validated scan results in a rich CLI table.
- prepare_export_data: Flatten complex nested results for persistence layers.
- _generate_reasoning: Synthesize technical signals into human-readable narratives.

Last Modified: 2026-02-19
Modified By: LLM

Open Tasks:
- [ ] [LOW] Add support for PDF report generation [2h]
- [ ] [MEDIUM] Implement localized language support for reasoning narratives [5h]

Related Files:
- src/classes/VisualUI.py: [UI component library used for rendering]
- src/classes/ScanOrchestrator.py: [Orchestrates scans and invokes ReportingService]
"""

from typing import Any, Dict, List, Union

import pandas as pd
from rich.console import Console

from src.ui.VisualUI import VisualUI

console = Console()


class ReportingService:
    """
    Manages the transformation and display of scan results for CLI and export layers.

    Design Pattern: Service Object - encapsulates reporting logic and delegates
    rendering to VisualUI.

    Attributes:
        console (Console): Rich console instance for direct output | Console()
        ui (VisualUI): UI rendering engine for standardized formats | VisualUI()

    Public Methods:
        - print_results_table(validated_results): Renders scan results in CLI.
        - prepare_export_data(results): Flattens data for export.

    Private Methods:
        - _generate_reasoning(...): Creates textual explanation of score.

    Usage Flow:
        1. Instantiate ReportingService
        2. Pass scan results to print_results_table for display
        3. Pass results to prepare_export_data before saving to disk

    State Management:
        - Valid states: Stateless service
        - State transitions: N/A

    Thread Safety: Yes - operations are read-only or local to call stack.

    Dependencies:
        External: pandas, rich
        Internal: VisualUI
    """

    def __init__(self) -> None:
        """Initialize ReportingService with console and UI engine."""
        self.console = console
        self.ui = VisualUI()

    def print_results_table(self, validated_results: list[dict[str, Any]]) -> None:
        """
        Print results using high-performance VisualUI table format.

        Logic:
            Step 1: Iterate through validated results.
            Step 2: Extract relevant metrics (symbol, signal, score, etc.).
            Step 3: Flatten nested objects into a list of simple dictionaries.
            Step 4: Delegate rendering to VisualUI.render_results_table.

        Parameters:
            validated_results (List[Dict[str, Any]]): List of scan result items.

        Returns:
            None: Output is printed to console.

        Example:
            >>> service = ReportingService()
            >>> results = [{"result": {"symbol": "SBIN", ...}, "backtest": {...}}]
            >>> service.print_results_table(results)

        Performance:
            Time Complexity: O(N) [single pass over results]
            Space Complexity: O(N) [temporary list for formatted data]

        Edge Cases Handled:
            - Missing nested keys in result/backtest objects.
            - Empty results list.
        """
        formatted_data = []
        for item in validated_results:
            res = item["result"]
            bt = item["backtest"]
            rm = res.get("risk_management") or {}
            ml = res.get("ml_prediction") or {}

            formatted_data.append(
                {
                    "symbol": res["symbol"],
                    "signal": res["signal"],
                    "score": res.get("score", 0),
                    "confidence": res.get("confidence", 0),
                    "return": bt.get("return", 0),
                    "rr": rm.get("risk_reward_ratio", 0),
                    "ml_dir": ml.get("direction", "NEUTRAL"),
                    "ml_conf": ml.get("confidence", 0),
                }
            )

        self.ui.render_results_table(formatted_data)

    def prepare_export_data(
        self, results: pd.DataFrame | list[dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Helper to flatten complex results for CSV or persistence layers.

        Logic:
            Step 1: Convert input to list of records if it's a DataFrame.
            Step 2: Initialize empty list for flattened data.
            Step 3: For each result, extract nested metrics into flat keys.
            Step 4: Generate human-readable reasoning strings.
            Step 5: Return a new pandas DataFrame.

        Parameters:
            results (Union[pd.DataFrame, List[Dict[str, Any]]]): Input data.

        Returns:
            pd.DataFrame: Flattened data ready for CSV export.

        Example:
            >>> service = ReportingService()
            >>> df = service.prepare_export_data(results)
            >>> df.to_csv("results.csv")

        Performance:
            Time Complexity: O(N * M) [N results, M metrics processed per result]
            Space Complexity: O(N * M) [new DataFrame construction]

        Edge Cases Handled:
            - Input as DataFrame or List.
            - Missing optional indicators or ML predictions.
        """
        data = []
        iterable = (
            results.to_dict("records") if isinstance(results, pd.DataFrame) else results
        )

        for r in iterable:
            row = r.get("result", r)
            bt = r.get("backtest") or {}

            ml_prediction = row.get("ml_prediction") or {}
            ml_dir = ml_prediction.get("direction", "N/A")
            ml_conf = ml_prediction.get("confidence", 0)

            inds = row.get("indicators") or {}
            st = inds.get("supertrend") or {}
            obv = inds.get("obv") or {}
            don = inds.get("donchian") or {}
            rsi = inds.get("rsi") or {}
            macd = inds.get("macd") or {}
            bb = inds.get("bb") or {}
            risk = row.get("risk_management") or {}
            smc = row.get("smc") or {}
            mtf = row.get("mtf_agreement") or {}

            ml_expy = ml_prediction.get("explanation") or {}
            vwap = row.get("vwap") or {}
            vp = row.get("volume_profile") or {}

            data.append(
                {
                    "Stock": row.get("symbol", "Unknown"),
                    "Score": row.get("score", 0),
                    "Signal": row.get("signal", "NEUTRAL"),
                    "Confidence": row.get("confidence", 0),
                    "Reasoning": self._generate_reasoning(
                        row,
                        rsi,
                        macd,
                        bb,
                        st,
                        obv,
                        don,
                        smc,
                        ml_dir,
                        ml_conf,
                        mtf,
                        ml_expy,
                        vwap,
                        vp,
                    ),
                    "Supertrend": st.get("direction", "N/A"),
                    "RSI": rsi.get("value", 0),
                    "RSI_Div": rsi.get("divergence", "None"),
                    "MACD_Hist": macd.get("hist", 0),
                    "MACD_Div": macd.get("divergence", "None"),
                    "BB_Pos": (
                        "Above Mid"
                        if row.get("current_close", 0) > bb.get("mid", 0)
                        else "Below Mid"
                    ),
                    "OBV_Trend": obv.get("direction", "N/A"),
                    "Donchian_Pos": don.get("position", 0),
                    "ML_Expy_Dir": ml_dir,
                    "ML_Conf": ml_conf,
                    "Trend_Agreement": mtf.get("agreement_score", 0),
                    "Trend_Dir": mtf.get("direction", "N/A"),
                    "SMC_Pattern": str(smc.get("Latest_BOS", smc.get("bos", "None"))),
                    "LTP": risk.get("current_price", 0),
                    "Stop_Loss": risk.get("stop_loss", 0),
                    "Target": risk.get("take_profit", 0),
                    "Risk_Reward": risk.get("risk_reward_ratio", 0),
                    "Backtest_Ret": bt.get("return", 0),
                    "Backtest_Sharpe": bt.get("sharpe", 0),
                }
            )
        return pd.DataFrame(data)

    def _generate_reasoning(
        self,
        row: dict[str, Any],
        rsi: dict[str, Any],
        macd: dict[str, Any],
        bb: dict[str, Any],
        st: dict[str, Any],
        obv: dict[str, Any],
        don: dict[str, Any],
        smc: dict[str, Any],
        ml_dir: str,
        ml_conf: int,
        mtf: dict[str, Any],
        ml_expy: dict[str, Any] = None,
        vwap: dict[str, Any] = None,
        vp: dict[str, Any] = None,
    ) -> str:
        """
        Generate a human-readable explanation for technical signals.

        Logic:
            Step 1: Check baseline indicators (Supertrend, RSI, MACD).
            Step 2: Analyze structural confirmations (SMC, Divergences).
            Step 3: Evaluate benchmark relative positions (VWAP, POC).
            Step 4: Integrate AI/ML predictions.
            Step 5: Compose narrative string based on net score.

        Parameters:
            row (Dict[str, Any]): Base stock data.
            rsi (Dict[str, Any]): RSI metrics and divergences.
            macd (Dict[str, Any]): MACD metrics and histogram.
            bb (Dict[str, Any]): Bollinger Band levels.
            st (Dict[str, Any]): Supertrend data.
            obv (Dict[str, Any]): Volume profile data.
            don (Dict[str, Any]): Donchian channel data.
            smc (Dict[str, Any]): Smart Money Concept patterns.
            ml_dir (str): Prediction direction (UP/DOWN/NEUTRAL).
            ml_conf (int): Prediction confidence (0-100).
            mtf (Dict[str, Any]): Multi-timeframe agreement metrics.
            ml_expy (Dict[str, Any]): SHAP/LIME explanation values.
            vwap (Dict[str, Any]): Volume Weighted Average Price info.
            vp (Dict[str, Any]): Volume Profile Point of Control info.

        Returns:
            str: Human-readable narrative description.

        Performance:
            Time Complexity: O(K) [where K is number of individual logic checks]
            Space Complexity: O(S) [size of generated string]

        Edge Cases Handled:
            - None/Missing values in any indicator dictionary.
            - Conflicting signals resulting in neutral score.
        """
        reasons, negatives = [], []

        # SuperTrend
        if st.get("direction") == "Bullish":
            reasons.append("Supertrend is Bullish")
        else:
            negatives.append("Supertrend is Bearish")

        # Momentum (RSI/MACD)
        rsi_val = rsi.get("value", 50)
        if rsi_val > 60:
            reasons.append(f"Strong RSI ({rsi_val:.1f})")
        elif rsi_val < 40:
            negatives.append(f"Weak RSI ({rsi_val:.1f})")

        if macd.get("hist", 0) > 0:
            reasons.append("MACD is Bullish")
        if macd.get("momentum") == "Growing":
            reasons.append("MACD momentum growing")

        # Divergences
        if rsi.get("divergence") == "Bullish":
            reasons.append("RSI Bullish Divergence")
        if macd.get("divergence") == "Bullish":
            reasons.append("MACD Bullish Divergence")
        if rsi.get("divergence") == "Bearish":
            negatives.append("RSI Bearish Divergence")
        if macd.get("divergence") == "Bearish":
            negatives.append("MACD Bearish Divergence")

        if obv.get("direction") == "Bullish":
            reasons.append("Volume flow (OBV) is positive")
        else:
            negatives.append("Volume flow (OBV) is negative")

        if don.get("position", 0) > 50:
            reasons.append("Price in upper Donchian channel")
        else:
            negatives.append("Price in lower Donchian channel")

        bos = str(smc.get("Latest_BOS", smc.get("bos", "")))
        if "Bullish" in bos:
            reasons.append("Bullish Structure Break")
        elif "Bearish" in bos:
            negatives.append("Bearish Structure Break")

        grab = str(smc.get("Latest_Grab", ""))
        if "Bullish" in grab:
            reasons.append("Bullish Liquidity Sweep (Stop Hunt)")
        elif "Bearish" in grab:
            negatives.append("Bearish Liquidity Sweep")

        if str(smc.get("Latest_CISD", "")) == "Bullish CISD":
            reasons.append("Bullish Confirm (CISD)")

        # VWAP & POC
        close = row.get("current_close", 0)
        if vwap and vwap.get("value"):
            if close > vwap["value"]:
                reasons.append("Above Benchmark (VWAP)")
            else:
                negatives.append("Below Benchmark (VWAP)")

        if vp and vp.get("poc"):
            if close > vp["poc"]:
                reasons.append("Above High Volume Level (POC)")
            else:
                negatives.append("Below High Volume Level (POC)")

        if mtf.get("agreement_score", 0) >= 66:
            if mtf.get("direction") == "bullish":
                reasons.append("Strong multi-timeframe alignment")
            elif mtf.get("direction") == "bearish":
                negatives.append("Strong bearish timeframe alignment")

        if ml_dir == "UP" and ml_conf >= 70:
            reason_str = f"AI predicts UP ({ml_conf}%)"
            if ml_expy:
                top_features = list(ml_expy.keys())[:2]
                reason_str += f" driven by {', '.join(top_features)}"
            reasons.append(reason_str)
        elif ml_dir == "DOWN" and ml_conf >= 70:
            reason_str = f"AI predicts DOWN ({ml_conf}%)"
            if ml_expy:
                top_features = list(ml_expy.keys())[:2]
                reason_str += f" driven by {', '.join(top_features)}"
            negatives.append(reason_str)

        score = row.get("score", 0)
        if score > 0:
            narrative = "BUY DRIVERS: " + ", ".join(reasons) + ". "
            if negatives:
                narrative += "CAUTIONS: " + ", ".join(negatives) + "."
        elif score < 0:
            narrative = "SELL DRIVERS: " + ", ".join(negatives) + ". "
            if reasons:
                narrative += "CONTRA_INDICATORS: " + ", ".join(reasons) + "."
        else:
            narrative = "NEUTRAL: Conflicting signals. " + ", ".join(
                reasons + negatives
            )
        return narrative
