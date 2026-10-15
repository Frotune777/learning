"""
Scanning Criteria Selector
Define filtering criteria for stock screening
"""


class ScanningCriteria:
    """
    Define scanning criteria and filters
    """

    def show_menu(self):
        """Display criteria selection menu"""
        print("\n" + "=" * 80)
        print("SELECT SCREENING CRITERIA")
        print("=" * 80 + "\n")
        print("""
 0 > Full Scan (no filters, show all)
 1 > High Score (>= 7, STRONG BUY only)
 2 > Buy Signals (>= 4, BUY or better)
 3 > Bullish MTF (>= 66% timeframe agreement)
 4 > ML Confident (>= 75% ML confidence)
 5 > Backtest Validated (>= 15% return)
 6 > Breakout Stocks (near 52-week high)
 7 > Reversal Signals (oversold + bullish)
 9 > Auto-Strategy (best strategy per stock) 🤖 NEW!
 10 > Specific Strategies (PKScreener Parity) 🎯
 11 > Custom Filters (configure manually)

Enter > Default (Score >= 4)
        """)

        try:
            choice = input("Select option: ").strip()

            if choice == "":
                choice = "2"  # Default to Buy Signals

            criteria = self.get_criteria(choice)

            if criteria:
                print(f"\n✅ Criteria: {criteria['name']}")
                return criteria
            else:
                print("\n❌ Invalid criteria!")
                return None

        except KeyboardInterrupt:
            print("\n\n👋 Cancelled")
            return None

    def get_criteria(self, option):
        """Get filtering criteria based on selection"""
        if option == "10":
            return self._specific_strategies_menu()
        elif option == "11":
            return self._custom_filters()

        criteria_map = {
            "0": {
                "name": "Full Scan",
                "min_score": -100,  # Show all
                "description": "No filters applied",
            },
            "1": {
                "name": "High Score (STRONG BUY)",
                "min_score": 7,
                "description": "Only stocks with score >= 7",
            },
            "2": {
                "name": "Buy Signals",
                "min_score": 4,
                "description": "Stocks with score >= 4",
            },
            "3": {
                "name": "Bullish MTF",
                "min_score": 0,
                "min_mtf": 66,
                "description": "Multi-timeframe agreement >= 66%",
            },
            "4": {
                "name": "ML Confident",
                "min_score": 0,
                "min_ml_conf": 75,
                "description": "ML prediction confidence >= 75%",
            },
            "5": {
                "name": "Backtest Validated",
                "min_score": 0,
                "min_backtest_return": 15,
                "description": "Historical return >= 15%",
            },
            "6": {
                "name": "Breakout Stocks",
                "min_score": 0,
                "breakout": True,
                "description": "Price in upper 25% of range",
            },
            "7": {
                "name": "Reversal Signals",
                "min_score": 0,
                "reversal": True,
                "description": "Oversold + bullish signal",
            },
            "8": {
                "name": "ML Bullish",
                "min_score": 0,
                "ml_direction": "UP",
                "min_ml_conf": 70,
                "description": "ML predicts UP with >= 70% confidence",
            },
            "9": {
                "name": "Auto-Strategy Selection",
                "min_score": 0,
                "auto_strategy": True,
                "description": "Auto-select best strategy per stock",
            },
        }

        return criteria_map.get(option)

    def _specific_strategies_menu(self):
        """Show PKScreener specific strategies sub-menu"""
        print("\n" + "=" * 80)
        print("SPECIFIC STRATEGIES (PKScreener Parity)")
        print("=" * 80 + "\n")
        print(" 8 > CCI outside range")
        print(" 9 > Volume gainers")
        print(" 10 > Price Momentum (2% up in 3 days)")
        print(" 11 > Ichimoku Bullish")
        print(" 12 > Intraday Breakout (Price & Vol)")
        print(" 13 > Bullish RSI & MACD")
        print(" 14 > NR4 Daily")
        print(" 15 > 52-Week Low Breakout")
        print(" 17 > 52-Week High Breakout")
        print(" 20 > Bullish for Next Day")
        print(" 24 > SuperTrend Bullish")
        print(" 27 > ATR Cross")
        print(" 31 > High Momentum")
        print(" 34 > Bullish Anchored VWAP")
        print("\n 0 > Cancel")

        try:
            op = input("\nSelect strategy: ").strip()
            if op == "0":
                return None

            # Map keys to names
            names = {
                "8": "CCI Range",
                "9": "Volume Gainers",
                "10": "Price Momentum",
                "11": "Ichimoku Bullish",
                "12": "Intraday Breakout",
                "13": "RSI + MACD",
                "14": "NR4 Daily",
                "15": "52W Low Breakout",
                "17": "52W High Breakout",
                "20": "Next Day Bullish",
                "24": "SuperTrend",
                "27": "ATR Cross",
                "31": "High Momentum",
                "34": "Bullish AVWAP",
            }

            if op in names:
                return {
                    "name": names[op],
                    "min_score": -100,  # Show all matches regardless of score
                    "executeOption": int(op),
                    "description": f"Strategy: {names[op]}",
                }
            else:
                print("Invalid option!")
                return None
        except Exception:
            return None

    def _custom_filters(self):
        """Get custom filter parameters from user"""
        print("\n" + "=" * 80)
        print("CUSTOM FILTERS")
        print("=" * 80 + "\n")

        try:
            min_score = input("  Minimum Score (0-12, default 4): ").strip()
            min_score = int(min_score) if min_score else 4

            min_mtf = input("  Minimum MTF Agreement % (0-100, default 0): ").strip()
            min_mtf = int(min_mtf) if min_mtf else 0

            min_ml = input("  Minimum ML Confidence % (0-100, default 0): ").strip()
            min_ml = int(min_ml) if min_ml else 0

            min_backtest = input("  Minimum Backtest Return % (default 10): ").strip()
            min_backtest = float(min_backtest) if min_backtest else 10

            auto_strat = (
                input("  Use Auto-Strategy Selection? (y/n, default n): ")
                .strip()
                .lower()
            )
            auto_strat = auto_strat == "y"

            return {
                "name": "Custom",
                "min_score": min_score,
                "min_mtf": min_mtf if min_mtf > 0 else None,
                "min_ml_conf": min_ml if min_ml > 0 else None,
                "min_backtest_return": min_backtest if min_backtest > 0 else None,
                "auto_strategy": auto_strat,
                "description": f"Score>={min_score}, MTF>={min_mtf}%, ML>={min_ml}%",
            }
        except (ValueError, KeyboardInterrupt):
            return {
                "name": "Buy Signals",
                "min_score": 4,
                "description": "Default criteria",
            }


def test_criteria():
    """Test the criteria selector"""
    selector = ScanningCriteria()
    criteria = selector.show_menu()

    if criteria:
        print("\n📊 Selected Criteria:")
        print(f"  Name: {criteria['name']}")
        print(f"  Min Score: {criteria.get('min_score', 'N/A')}")
        if "min_mtf" in criteria:
            print(f"  Min MTF: {criteria['min_mtf']}%")
        if "min_ml_conf" in criteria:
            print(f"  Min ML: {criteria['min_ml_conf']}%")
        if criteria.get("auto_strategy"):
            print("  Auto-Strategy: Enabled")
    else:
        print("\n❌ No criteria selected")


if __name__ == "__main__":
    test_criteria()
