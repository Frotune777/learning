"""
File: src/nse_bhavcopy/etf_screener.py
Purpose: Screens equity ETFs for the most liquid instrument per sector by turnover.
Last Modified: 2026-05-27
"""

from typing import Any

import pandas as pd

from src.nse_live.nse_utils import NseUtils


from src.core.signal import Signal
from datetime import datetime
from src.scanners.registry import register_scanner

@register_scanner
def run_liquid_etf_screener() -> list[Signal]:
    """
    Fetches the ETF master from the NSE website, filters for equity-based ETFs,
    and returns the most liquid ETF for each major sector/category.

    Returns:
        list[Signal]: A list of Signal objects representing the most liquid ETF per category.
    """
    nse = NseUtils()
    df = nse.get_etf_list()

    if df is None or df.empty:
        print("Failed to fetch ETF data from NSE.")
        return []

    df = df[["symbol", "assets", "open", "high", "low", "ltP", "qty"]]
    df.columns = pd.Index(
        ["ETF", "Underlying", "Open", "High", "Low", "Close", "Volume"]
    )

    # Data Cleanup
    df = df[df["Volume"] != "-"].copy()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")

    # Calculate Weight / Turnover
    df["Weight"] = df["Close"] * df["Volume"]

    # Filter #1: Minimum 10k volume
    df = df[df["Volume"] >= 10000]

    # Filter #2: Remove all debt/ipo related ETFs
    filter_string = ["Bond", "GSEC", "G-Sec", "GILT", "LIQ", "Liquid", "IPO"]
    for scan_str in filter_string:
        df = df[
            ~df["Underlying"].astype(str).str.contains(scan_str, case=False, na=False)
        ]
        df = df[~df["ETF"].astype(str).str.contains(scan_str, case=False, na=False)]

    # Filter #3: Remove one-off / unwanted etfs from list
    filter_etfs = ["GROWWNET", "INTERNET", "SHARIABEES", "GROWWNXT50"]
    df = df[~df["ETF"].isin(filter_etfs)]

    # Category Mapping
    cross_ref = {
        "Midcap 150": "MIDCAP",
        "Nifty 100": "NIFTY 100",
        "MIDCAP 100": "MIDCAP",
        "Nifty 200": "NIFTY 200",
        "Nifty 500": "NIFTY 500",
        "Nifty 50": "NIFTY 50",
        "Silver": "SILVER",
        "Gold": "GOLD",
        "S&P": "S&P",
        "Next 50": "NIFTY NEXT 50",
        "Junior": "NIFTY NEXT 50",
        "Nifty50": "NIFTY 50",
        "Nifty200": "NIFTY 200",
        "Nifty Total Market Index": "NIFTY 500",
        "Private Bank": "PRIVATE BANK",
        "Oil & Gas": "OIL & GAS",
        "PSU": "PSU",
        "Metal": "METAL",
        "MNC": "MNC",
        "Consumption": "CONSUMPTION",
        "Healthcare": "HEALTHCARE",
        "Financial Services": "FIN SERVICES",
        "FMCG": "FMCG",
        "EV": "EV",
        "Nifty Bank": "BANK NIFTY",
        "Auto": "AUTO",
        "Low-Volatility 30 ": "LOW VOL 30",
        "Momentum 50": "MOMENTUM 50",
        "Nasdaq": "NASDAQ",
        "NYSE": "NASDAQ",
        "Alpha 50": "NIFTY 50",
        "Smallcap 250": "SMALLCAP",
        "Realty": "REALTY",
        "MidSmallcap400": "MID SMALL CAP",
        "Low Vol 30": "LOW VOL 30",
        "Infrastructure": "INFRA",
        "Hang Seng": "HANG SENG",
        "CPSE": "PSU",
        "PSE": "PSU",
        "Commodity": "GOLD",
        "Power": "POWER",
        "Defence": "DEFENCE",
        "Pharma": "PHARMA",
        " IT": "IT",
        "SENSEX": "SENSEX",
        "Nifty Top 10 Equal Weight": "NIFTY 50",
        "Insurance": "INSURANCE",
        "Manufacturing": "MANUFACTURING",
        "Digital": "DIGITAL",
        "Capital Market": "NIFTY 500",
        "NIFTY Growth": "NIFTY 500",
        "50 TRI": "NIFTY 50",
        "Nifty Top 15 Equal Weight": "NIFTY 50",
        "BSE 200": "NIFTY 200",
        "ESG": "ESG",
        "Commodities": "GOLD",
        "Infra": "INFRA",
        "NIFTY100": "NIFTY 100",
        "Tourism": "TOURISM",
        "Midcap 50": "MIDCAP",
        "Top 20 Equal Weight": "NIFTY 50",
        "MSCI": "LARGE MID CAP",
        "Nifty Smallcap 100 Index": "SMALLCAP",
        "Nifty Index 50 Index": "NIFTY 50",
        "Nifty Chemicals Index (TRI)": "CHEMICAL",
        "Nifty Chemicals Index - TRI": "CHEMICAL",
        "Nifty Energy": "ENERGY",
        "Nifty Energy Index": "ENERGY",
    }

    def get_benchmark(underlying: Any) -> str:
        """Map underlying name to category"""
        under_str = str(underlying).upper()
        for search_str, value in cross_ref.items():
            if search_str.upper() in under_str:
                return value
        return "Unknown"

    df["Category"] = df["Underlying"].apply(get_benchmark)
    df = df[~df["Category"].isin(["Unknown"])]

    # Retain the top ETF per category based on highest weight
    df = (
        df.sort_values(["Category", "Weight"], ascending=False)
        .groupby("Category")
        .head(1)
    )
    df.sort_values(by="Weight", ascending=False, inplace=True)
    df.reset_index(inplace=True, drop=True)

    signals = []
    now = datetime.now()
    max_weight = df["Weight"].max() if not df.empty else 1.0
    
    for _, row in df.iterrows():
        symbol = row["ETF"]
        weight = row["Weight"]
        category = row["Category"]
        
        # Conviction based on relative turnover (weight)
        conv = min(1.0, float(weight / max_weight)) if max_weight > 0 else 1.0
        
        sig = Signal(
            symbol=symbol,
            strategy_name="etf_screener",
            action=1,  # Selected liquid ETFs are implicitly positive candidates
            conviction=round(conv, 2),
            timestamp=now,
            meta={
                "category": category,
                "weight": weight,
                "volume": row["Volume"],
                "cmp": row["Close"],
                "underlying": row["Underlying"]
            }
        )
        signals.append(sig)

    return signals
