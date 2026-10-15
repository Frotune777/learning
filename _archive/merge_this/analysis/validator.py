"""
Symbol Validator
Pre-validates stock symbols against NSE instruments list
Prevents wasting time on invalid/delisted symbols
"""

from pathlib import Path

import pandas as pd


class SymbolValidator:
    """
    Validate stock symbols before scanning
    Prevents 404 errors and wasted API calls
    """

    def __init__(self, instruments_file="user_data/instruments.csv"):
        self.instruments_file = Path(instruments_file)
        self.valid_symbols = self._load_valid_symbols()

    def _load_valid_symbols(self):
        """Load valid symbols from instruments.csv"""
        try:
            if self.instruments_file.exists():
                df = pd.read_csv(self.instruments_file)

                # Get trading symbols
                if "tradingsymbol" in df.columns:
                    symbols = set(df["tradingsymbol"].str.upper())
                elif "SYMBOL" in df.columns:
                    symbols = set(df["SYMBOL"].str.upper())
                else:
                    # Use first column as symbols
                    symbols = set(df.iloc[:, 0].str.upper())

                return symbols
        except Exception as e:
            print(f"Warning: Could not load instruments file: {e}")

        return set()  # Empty set if file not found

    def validate(self, symbols):
        """
        Validate list of symbols

        Args:
            symbols: List of stock symbols

        Returns:
            (valid_symbols, invalid_symbols)
        """
        if not self.valid_symbols:
            # If no instruments file, assume all valid
            return symbols, []

        valid = []
        invalid = []

        for symbol in symbols:
            symbol_upper = symbol.upper()

            # Check exact match or with common suffixes
            if (
                symbol_upper in self.valid_symbols
                or f"{symbol_upper}-EQ" in self.valid_symbols
                or f"{symbol_upper}.NS" in self.valid_symbols
            ):
                valid.append(symbol)
            else:
                invalid.append(symbol)

        return valid, invalid

    def is_valid(self, symbol):
        """Check if single symbol is valid"""
        if not self.valid_symbols:
            return True

        symbol_upper = symbol.upper()
        return (
            symbol_upper in self.valid_symbols
            or f"{symbol_upper}-EQ" in self.valid_symbols
            or f"{symbol_upper}.NS" in self.valid_symbols
        )


# Test
if __name__ == "__main__":
    validator = SymbolValidator()

    test_symbols = ["SBIN", "TCS", "DUMMYHDLVR", "INFY", "INVALID123"]
    valid, invalid = validator.validate(test_symbols)

    print(f"Valid: {valid}")
    print(f"Invalid: {invalid}")
