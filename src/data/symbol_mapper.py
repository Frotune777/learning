"""
File: src/data/symbol_mapper.py
Purpose: Centralised middleware for mapping internal NSE symbols to provider-specific formats.
Last Modified: 2026-05-30
"""


class SymbolMapper:
    """
    Abstracts symbol string manipulation across different data providers.

    Provides static methods to convert a clean internal NSE symbol (e.g. 'TCS')
    into the required format for various APIs (e.g. 'NSE:TCS-EQ', 'TCS.NS').

    Thread Safety: Yes - fully stateless.
    """

    @staticmethod
    def clean(symbol: str) -> str:
        """
        Normalize any symbol to our internal base format (uppercase, stripped).

        Example:
            >>> SymbolMapper.clean(" nse:TCS-EQ ")
            'TCS'
            >>> SymbolMapper.clean("INFY.NS")
            'INFY'
        """
        sym = symbol.strip().upper()
        # Remove Fyers formatting
        if sym.startswith("NSE:"):
            sym = sym.replace("NSE:", "")
        if sym.endswith("-EQ"):
            sym = sym.replace("-EQ", "")
        # Remove YFinance formatting
        if sym.endswith(".NS"):
            sym = sym.replace(".NS", "")
        if sym.endswith(".BO"):
            sym = sym.replace(".BO", "")

        return sym

    @staticmethod
    def to_fyers(symbol: str) -> str:
        """
        Convert to Fyers format: 'NSE:<SYMBOL>-EQ'.

        Example:
            >>> SymbolMapper.to_fyers("TCS")
            'NSE:TCS-EQ'
        """
        clean_sym = SymbolMapper.clean(symbol)
        return f"NSE:{clean_sym}-EQ"

    @staticmethod
    def to_yfinance(symbol: str, exchange: str = "NS") -> str:
        """
        Convert to YFinance format: '<SYMBOL>.NS' or '<SYMBOL>.BO'.

        Example:
            >>> SymbolMapper.to_yfinance("TCS")
            'TCS.NS'
        """
        clean_sym = SymbolMapper.clean(symbol)
        return f"{clean_sym}.{exchange}"
