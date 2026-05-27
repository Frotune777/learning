"""
File: src/nse_bhavcopy/heatmap.py
Purpose: Generates a CLI-based tabular heatmap for Nifty Index constituents.
Last Modified: 2026-05-27
"""

import pandas as pd

from src.nse_live.nse_utils import NseUtils


def run_heatmap_cli(index_name: str = "NIFTY 50") -> pd.DataFrame:
    """
    Fetches the index constituents and calculates advances/declines and changes.

    Parameters:
        index_name (str): The Nifty index name (e.g., "NIFTY 50").

    Returns:
        pd.DataFrame: Constituents with their market cap and price change.
    """
    try:
        nse = NseUtils()
        df: pd.DataFrame = nse.get_index_details(index_name, list_only=False)

        if df is None or df.empty:
            print(f"Error: Could not retrieve data for index {index_name}")
            return pd.DataFrame()

        # The DataFrame typically has columns: 'symbol', 'pChange', 'ffmc' etc.
        # We ensure it is formatted nicely.
        if "symbol" not in df.columns:
            # Maybe the column name is different, we'll try to find it
            if "symbol" in [str(c).lower() for c in df.columns]:
                # Just use the original data as is, but we want to make sure
                # we have the right columns for the heatmap.
                pass
            else:
                print("Warning: Expected 'symbol' column not found.")
                return df

        # We will keep relevant columns
        cols_to_keep = []
        for c in [
            "symbol",
            "open",
            "dayHigh",
            "dayLow",
            "lastPrice",
            "pChange",
            "ffmc",
        ]:
            if c in df.columns:
                cols_to_keep.append(c)

        # If no standard columns found, just return everything
        if not cols_to_keep:
            return df

        df = df[cols_to_keep].copy()

        # Convert 'ffmc' (Free Float Market Cap) to a readable format if present
        if "ffmc" in df.columns:
            df["Market_Cap_Cr"] = pd.to_numeric(df["ffmc"], errors="coerce") / 10000000
            df = df.drop(columns=["ffmc"])

        # Sort by Market Cap descending, then by pChange
        if "Market_Cap_Cr" in df.columns:
            df = df.sort_values(by="Market_Cap_Cr", ascending=False)
        elif "pChange" in df.columns:
            df["pChange"] = pd.to_numeric(df["pChange"], errors="coerce")
            df = df.sort_values(by="pChange", ascending=False)

        # Standardize 'symbol' to 'Symbol'
        if "symbol" in df.columns:
            df = df.rename(columns={"symbol": "Symbol"})

        return df

    except Exception as e:
        print(f"Error generating heatmap data: {e}")
        return pd.DataFrame()
