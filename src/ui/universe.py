"""
Stock Universe Selector
Interactive menu for selecting stocks to scan
Based on screenipy.py menu system
"""

import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))


from src.data.Fetcher import Fetcher
from src.utils.config import ConfigManager


class StockUniverseSelector:
    """
    Select stock universe for scanning
    Provides interactive menu similar to screenipy.py
    """

    def __init__(self):
        self.config = ConfigManager()
        self.fetcher = Fetcher(self.config)
        # Invalid/dummy symbols to filter out
        self.invalid_symbols = {
            "DUMMYHDLVR",  # Dummy symbol
            "INVALID123",  # Test symbol
            "TEST",  # Test symbol
            "DUMMY",  # Dummy symbol
        }

    def show_menu(self):
        """Display stock selection menu"""
        print("\n" + "=" * 80)
        print("SELECT STOCK UNIVERSE")
        print("=" * 80 + "\n")
        print("""
 W > Watchlist (from watchlist.xlsx)
 0 > Custom Stocks (enter codes manually)

 --- Nifty Indices ---
 1 > Nifty 50
 2 > Nifty Next 50
 3 > Nifty 100
 4 > Nifty 200
 5 > Nifty 500

 --- Smallcap & Midcap ---
 6 > Nifty Smallcap 50
 7 > Nifty Smallcap 100
 8 > Nifty Smallcap 250
 9 > Nifty Midcap 50
10 > Nifty Midcap 100
11 > Nifty Midcap 150

 --- Other ---
12 > All Stocks (NSE)
14 > F&O Stocks Only
15 > US S&P 500
16 > Sectoral Indices

Enter > Default (Nifty 50)
        """)

        try:
            choice = input("Select option: ").strip().upper()

            if choice == "":
                choice = "1"  # Default to Nifty 50

            stocks = self.get_stocks(choice)

            if stocks:
                print(f"\n✅ Selected {len(stocks)} stocks")
                return stocks
            else:
                print("\n❌ No stocks found!")
                return None

        except KeyboardInterrupt:
            print("\n\n👋 Cancelled")
            return None
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return None

    def get_stocks(self, option):
        """Get stock list based on selection"""
        if option == "W":
            stocks = self._get_watchlist()
        elif option == "0":
            stocks = self._get_custom_stocks()
        elif option.isdigit():
            stocks = self._get_index_stocks(int(option))
        else:
            print(f"Invalid option: {option}")
            return None

        # Filter out invalid symbols
        if stocks:
            stocks = self._validate_symbols(stocks)

        return stocks

    def _validate_symbols(self, symbols):
        """Filter out invalid/dummy symbols"""
        valid_symbols = []
        filtered_out = []

        for symbol in symbols:
            # Check if symbol is in invalid list
            if symbol.upper() in self.invalid_symbols:
                filtered_out.append(symbol)
                continue

            # Check basic format (alphanumeric + hyphen + ampersand, 1-20 chars)
            # Allow: BAJAJ-AUTO, M&M, etc.
            if not symbol or len(symbol) > 20:
                filtered_out.append(symbol)
                continue

            # Check if contains only valid characters
            valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-&")
            if not all(c in valid_chars for c in symbol.upper()):
                filtered_out.append(symbol)
                continue

            valid_symbols.append(symbol)

        if filtered_out:
            print(
                f"  ⚠️  Filtered out {len(filtered_out)} invalid symbols: {', '.join(filtered_out[:5])}"
            )
            if len(filtered_out) > 5:
                print(f"     ... and {len(filtered_out) - 5} more")

        return valid_symbols

    def _get_watchlist(self):
        """Load from watchlist.xlsx"""
        try:
            stocks = self.fetcher.fetchWatchlist()
            if stocks:
                print(f"  Loaded {len(stocks)} stocks from watchlist.xlsx")
                return stocks
            else:
                print("  ❌ watchlist.xlsx not found or empty")
                print("  Create watchlist.xlsx with column 'Stock Code'")
                return None
        except Exception as e:
            print(f"  ❌ Error loading watchlist: {e}")
            return None

    def _get_custom_stocks(self):
        """Get custom stock codes from user"""
        print("\nEnter stock codes (comma-separated):")
        print("Example: SBIN,TCS,INFY,RELIANCE")

        codes = input("\nStock codes: ").strip()

        if not codes:
            return None

        stocks = [s.strip().upper() for s in codes.split(",")]
        return stocks

    def _get_index_stocks(self, index):
        """Fetch stocks from NSE index"""
        index_names = {
            1: "Nifty 50",
            2: "Nifty Next 50",
            3: "Nifty 100",
            4: "Nifty 200",
            5: "Nifty 500",
            6: "Nifty Smallcap 50",
            7: "Nifty Smallcap 100",
            8: "Nifty Smallcap 250",
            9: "Nifty Midcap 50",
            10: "Nifty Midcap 100",
            11: "Nifty Midcap 150",
            12: "All Stocks (NSE)",
            14: "F&O Stocks",
            15: "US S&P 500",
            16: "Sectoral Indices",
        }

        name = index_names.get(index, f"Index {index}")
        print(f"\n  Fetching {name} stocks from NSE...")

        try:
            stocks = self.fetcher.fetchCodes(index)

            if isinstance(stocks, dict):
                # For sectoral indices, show submenu
                return self._select_sectoral_index(stocks)

            return stocks

        except Exception as e:
            print(f"  ❌ Error fetching stocks: {e}")
            return None

    def _select_sectoral_index(self, indices_dict):
        """Select from sectoral indices"""
        print("\n" + "=" * 80)
        print("SELECT SECTORAL INDEX")
        print("=" * 80 + "\n")

        # Convert dict to list for indexing
        indices_list = list(indices_dict.items())

        for i, (symbol, name) in enumerate(indices_list, 1):
            print(f"{i:2d} > {name}")

        print("\nEnter > Cancel")

        try:
            choice = input("\nSelect sector: ").strip()

            if not choice:
                return None

            idx = int(choice) - 1

            if 0 <= idx < len(indices_list):
                symbol, name = indices_list[idx]
                print(f"\n  Selected: {name}")
                # For sectoral indices, return the index symbol
                # User can scan the index constituents separately
                return [symbol]
            else:
                print("Invalid selection")
                return None

        except (ValueError, KeyboardInterrupt):
            return None


def test_selector():
    """Test the selector"""
    selector = StockUniverseSelector()
    stocks = selector.show_menu()

    if stocks:
        print(f"\n📊 Selected Stocks ({len(stocks)}):")
        print(", ".join(stocks[:10]))
        if len(stocks) > 10:
            print(f"... and {len(stocks) - 10} more")
    else:
        print("\n❌ No stocks selected")


if __name__ == "__main__":
    test_selector()
