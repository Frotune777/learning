"""
File: src/nse_bhavcopy/minervini_screener.py
Purpose: Screens stocks against Mark Minervini's Trend Template using yfinance data.
Last Modified: 2026-05-27
"""

from datetime import date, timedelta
from typing import Any

import pandas as pd
import yfinance as yf


def get_historical_data(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Fetches historical OHLCV data for a given symbol using yfinance.

    Parameters:
        symbol (str): The stock symbol.
        start_date (date): Start date for data fetch.
        end_date (date): End date for data fetch.

    Returns:
        pd.DataFrame: DataFrame containing historical data.

    Raises:
        Exception: If the yfinance download fails unexpectedly.
    """
    try:
        yf_symbol = f"{symbol}.NS"
        df: pd.DataFrame = yf.download(
            yf_symbol, start=start_date, end=end_date, progress=False
        )
        if df.empty:
            return pd.DataFrame()

        # yfinance returns multi-index columns if downloading multiple tickers,
        # but for a single ticker it's usually flat or multi-index with ticker.
        # We ensure it's flat.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[["Close", "High", "Low", "Volume"]].copy()
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()


def load_universe(
    symbols: list[str], start_date: date, end_date: date
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads historical data for a list of symbols into aligned DataFrames.

    Parameters:
        symbols (list[str]): List of stock symbols to fetch.
        start_date (date): Start date.
        end_date (date): End date.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
            Close, High, Low, and Volume DataFrames.
    """
    close_dict: dict[str, Any] = {}
    high_dict: dict[str, Any] = {}
    low_dict: dict[str, Any] = {}
    volume_dict: dict[str, Any] = {}

    for s in symbols:
        df = get_historical_data(s, start_date, end_date)
        if df.empty or len(df) < 256:
            continue

        close_dict[s] = df["Close"]
        high_dict[s] = df["High"]
        low_dict[s] = df["Low"]
        volume_dict[s] = df["Volume"]

    close_df = pd.DataFrame(close_dict)
    high_df = pd.DataFrame(high_dict)
    low_df = pd.DataFrame(low_dict)
    volume_df = pd.DataFrame(volume_dict)

    return close_df, high_df, low_df, volume_df


def compute_rs_rating(close: pd.DataFrame) -> pd.Series:
    """
    Computes Relative Strength rating based on multi-timeframe performance.

    Parameters:
        close (pd.DataFrame): DataFrame of closing prices.

    Returns:
        pd.Series: RS ratings for each stock.
    """
    r12 = close.pct_change(252, fill_method=None)
    r6 = close.pct_change(126, fill_method=None)
    r3 = close.pct_change(63, fill_method=None)
    r1 = close.pct_change(21, fill_method=None)

    rs = (0.4 * r12) + (0.2 * r6) + (0.2 * r3) + (0.2 * r1)
    latest_rs = rs.iloc[-1]
    rs_rating = latest_rs.rank(pct=True) * 100
    return rs_rating


def compute_trend_template(
    close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame
) -> pd.Series:
    """
    Evaluates Minervini's specific trend template conditions.

    Parameters:
        close (pd.DataFrame): Closing prices.
        high (pd.DataFrame): High prices.
        low (pd.DataFrame): Low prices.

    Returns:
        pd.Series: Trend template score (0-9) for each stock.
    """
    sma50 = close.rolling(50).mean()
    sma150 = close.rolling(150).mean()
    sma200 = close.rolling(200).mean()

    high_52 = high.rolling(252).max()
    low_52 = low.rolling(252).min()
    sma200_shift = sma200.shift(30)

    score = (
        (close > sma50).astype(int)
        + (close > sma150).astype(int)
        + (close > sma200).astype(int)
        + (sma50 > sma150).astype(int)
        + (sma50 > sma200).astype(int)
        + (sma150 > sma200).astype(int)
        + (close >= low_52 * 1.30).astype(int)
        + (close >= high_52 * 0.75).astype(int)
        + (sma200 > sma200_shift).astype(int)
    )
    return score.iloc[-1]


def compute_relative_volume(volume: pd.DataFrame) -> pd.Series:
    """
    Computes relative volume against 50-day average.

    Parameters:
        volume (pd.DataFrame): Volume data.

    Returns:
        pd.Series: Relative volume.
    """
    avg_vol = volume.rolling(50).mean()
    rvol = volume / avg_vol
    return rvol.iloc[-1]


def compute_high_proximity(close: pd.DataFrame, high: pd.DataFrame) -> pd.Series:
    """
    Computes proximity of current close to 52-week high.

    Parameters:
        close (pd.DataFrame): Closing prices.
        high (pd.DataFrame): High prices.

    Returns:
        pd.Series: Proximity ratio.
    """
    high_52 = high.rolling(252).max()
    latest_close = close.iloc[-1]
    latest_high = high_52.iloc[-1]
    return latest_close / latest_high


def compute_stage2(close: pd.DataFrame) -> pd.Series:
    """
    Determines if stock is in Stage 2 uptrend based on moving averages.

    Parameters:
        close (pd.DataFrame): Closing prices.

    Returns:
        pd.Series: Boolean mask for Stage 2.
    """
    sma150 = close.rolling(150).mean()
    sma200 = close.rolling(200).mean()
    cond1 = close.iloc[-1] > sma150.iloc[-1]
    cond2 = sma150.iloc[-1] > sma200.iloc[-1]

    sma50 = close.rolling(50).mean()
    cond3 = sma50.iloc[-1] > sma50.iloc[-10]

    return cond1 & cond2 & cond3


def compute_pivot_breakout(
    close: pd.DataFrame, high: pd.DataFrame
) -> tuple[pd.Series, pd.Series]:
    """
    Calculates if current price is breaking out from a 60-day base.

    Parameters:
        close (pd.DataFrame): Closing prices.
        high (pd.DataFrame): High prices.

    Returns:
        Tuple[pd.Series, pd.Series]: The pivot prices and boolean breakout flags.
    """
    base_high = high.rolling(60).max()
    pivot = base_high.iloc[-1]
    latest_close = close.iloc[-1]
    breakout = latest_close > pivot
    return pivot, breakout


def compute_pocket_pivot(close: pd.DataFrame, volume: pd.DataFrame) -> pd.Series:
    """
    Detects pocket pivot volume signatures.

    Parameters:
        close (pd.DataFrame): Closing prices.
        volume (pd.DataFrame): Volume data.

    Returns:
        pd.Series: Boolean pocket pivot indicators.
    """
    down_days = close.diff() < 0
    down_volume = volume.where(down_days)
    max_down_volume = down_volume.rolling(10).max()
    pocket = volume.iloc[-1] > max_down_volume.iloc[-1]
    return pocket


def compute_vcp(close: pd.DataFrame) -> pd.Series:
    """
    Detects Volatility Contraction Pattern (VCP).

    Parameters:
        close (pd.DataFrame): Closing prices.

    Returns:
        pd.Series: Boolean indicating VCP setup.
    """
    ranges = close.pct_change(fill_method=None).abs()
    vol20 = ranges.rolling(20).mean()
    contraction = vol20.iloc[-1] < vol20.iloc[-40]
    return contraction


def run_minervini_screener(symbols: list[str]) -> pd.DataFrame:
    """
    Orchestrates the Mark Minervini screener.

    Parameters:
        symbols (list[str]): List of stock symbols to screen.

    Returns:
        pd.DataFrame: A DataFrame with calculated technical metrics.
    """
    end = date.today()
    start = end - timedelta(days=400)

    close, high, low, volume = load_universe(symbols, start, end)

    if close.empty:
        return pd.DataFrame()

    rs_rating = compute_rs_rating(close)
    template_score = compute_trend_template(close, high, low)
    rvol = compute_relative_volume(volume)
    proximity = compute_high_proximity(close, high)
    stage2 = compute_stage2(close)
    vcp = compute_vcp(close)
    pivot, breakout = compute_pivot_breakout(close, high)
    pocket = compute_pocket_pivot(close, volume)

    df = pd.DataFrame(
        {
            "RS_Rating": rs_rating,
            "Template_Score": template_score,
            "RVOL": rvol,
            "High_Proximity": proximity,
            "Stage2": stage2,
            "VCP": vcp,
            "Pivot": pivot,
            "Breakout": breakout,
            "PocketPivot": pocket,
        }
    )
    return df


def filter_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters candidates based on strict Minervini criteria.

    Parameters:
        df (pd.DataFrame): DataFrame of calculated technical metrics.

    Returns:
        pd.DataFrame: The filtered and sorted candidates.
    """
    if df.empty:
        return pd.DataFrame()

    candidates = df[
        (df["RS_Rating"] >= 70)
        & (df["Template_Score"] >= 8)
        & (df["Stage2"])
        & (df["High_Proximity"] >= 0.85)
        & (df["RVOL"] >= 1.2)
    ]

    return candidates.sort_values("RS_Rating", ascending=False).reset_index()


from src.core.signal import Signal
from datetime import datetime
from src.scanners.registry import register_scanner

@register_scanner
def run_minervini_cli() -> list[Signal]:
    """
    Entry point for CLI Minervini screener execution.

    Returns:
        list[Signal]: The final sorted candidates as Signal objects.
    """
    symbols = [
        "360ONE",
        "3MINDIA",
        "AADHARHFC",
        "AARTIIND",
        "AAVAS",
        "ABB",
        "ABBOTINDIA",
        "ABCAPITAL",
        "ABFRL",
        "ABLBL",
        "ABREL",
        "ABSLAMC",
        "ACC",
        "ACE",
        "ACMESOLAR",
        "ADANIENSOL",
        "ADANIENT",
        "ADANIGREEN",
        "ADANIPORTS",
        "ADANIPOWER",
        "AEGISLOG",
        "AEGISVOPAK",
        "AFCONS",
        "AFFLE",
        "AGARWALEYE",
        "AIAENG",
        "AIIL",
        "AJANTPHARM",
        "AKUMS",
        "AKZOINDIA",
        "ALKEM",
        "ALKYLAMINE",
        "ALOKINDS",
        "AMBER",
        "AMBUJACEM",
        "ANANDRATHI",
        "ANANTRAJ",
        "ANGELONE",
        "APARINDS",
        "APLAPOLLO",
        "APLLTD",
        "APOLLOHOSP",
        "APOLLOTYRE",
        "APTUS",
        "ARE&M",
        "ASAHIINDIA",
        "ASHOKLEY",
        "ASIANPAINT",
        "ASTERDM",
        "ASTRAL",
        "ASTRAZEN",
        "ATGL",
        "ATHERENERG",
        "ATUL",
        "AUBANK",
        "AUROPHARMA",
        "AWL",
        "AXISBANK",
        "BAJAJ-AUTO",
        "BAJAJFINSV",
        "BAJAJHFL",
        "BAJAJHLDNG",
        "BAJFINANCE",
        "BALKRISIND",
        "BALRAMCHIN",
        "BANDHANBNK",
        "BANKBARODA",
        "BANKINDIA",
        "BASF",
        "BATAINDIA",
        "BAYERCROP",
        "BBTC",
        "BDL",
        "BEL",
        "BEML",
        "BERGEPAINT",
        "BHARATFORG",
        "BHARTIARTL",
        "BHARTIHEXA",
        "BHEL",
        "BIKAJI",
        "BIOCON",
        "BLS",
        "BLUEDART",
        "BLUEJET",
        "BLUESTARCO",
        "BOSCHLTD",
        "BPCL",
        "BRIGADE",
        "BRITANNIA",
        "BSE",
        "BSOFT",
        "CAMPUS",
        "CAMS",
        "CANBK",
        "CANFINHOME",
        "CAPLIPOINT",
        "CARBORUNIV",
        "CASTROLIND",
        "CCL",
        "CDSL",
        "CEATLTD",
        "CENTRALBK",
        "CENTURYPLY",
        "CERA",
        "CESC",
        "CGCL",
        "CGPOWER",
        "CHALET",
        "CHAMBLFERT",
        "CHENNPETRO",
        "CHOICEIN",
        "CHOLAFIN",
        "CHOLAHLDNG",
        "CIPLA",
        "CLEAN",
        "COALINDIA",
        "COCHINSHIP",
        "COFORGE",
        "COHANCE",
        "COLPAL",
        "CONCOR",
        "CONCORDBIO",
        "COROMANDEL",
        "CRAFTSMAN",
        "CREDITACC",
        "CRISIL",
        "CROMPTON",
        "CUB",
        "CUMMINSIND",
        "CYIENT",
        "DABUR",
        "DALBHARAT",
        "DATAPATTNS",
        "DBREALTY",
        "DCMSHRIRAM",
        "DEEPAKFERT",
        "DEEPAKNTR",
        "DELHIVERY",
        "DEVYANI",
        "DIVISLAB",
        "DIXON",
        "DLF",
        "DMART",
        "DOMS",
        "DRREDDY",
        "ECLERX",
        "EICHERMOT",
        "EIDPARRY",
        "EIHOTEL",
        "ELECON",
        "ELGIEQUIP",
        "EMAMILTD",
        "EMCURE",
        "ENDURANCE",
        "ENGINERSIN",
        "ENRIN",
        "ERIS",
        "ESCORTS",
        "ETERNAL",
        "EXIDEIND",
        "FACT",
        "FEDERALBNK",
        "FINCABLES",
        "FINPIPE",
        "FIRSTCRY",
        "FIVESTAR",
        "FLUOROCHEM",
        "FORCEMOT",
        "FORTIS",
        "FSL",
        "GAIL",
        "GESHIP",
        "GICRE",
        "GILLETTE",
        "GLAND",
        "GLAXO",
        "GLENMARK",
        "GMDCLTD",
        "GMRAIRPORT",
        "GODFRYPHLP",
        "GODIGIT",
        "GODREJAGRO",
        "GODREJCP",
        "GODREJIND",
        "GODREJPROP",
        "GPIL",
        "GRANULES",
        "GRAPHITE",
        "GRASIM",
        "GRAVITA",
        "GRSE",
        "GSPL",
        "GUJGASLTD",
        "GVT&D",
        "HAL",
        "HAPPSTMNDS",
        "HAVELLS",
        "HBLENGINE",
        "HCLTECH",
        "HDFCAMC",
        "HDFCBANK",
        "HDFCLIFE",
        "HEG",
        "HEROMOTOCO",
        "HEXT",
        "HFCL",
        "HINDALCO",
        "HINDCOPPER",
        "HINDPETRO",
        "HINDUNILVR",
        "HINDZINC",
        "HOMEFIRST",
        "HONASA",
        "HONAUT",
        "HSCL",
        "HUDCO",
        "HYUNDAI",
        "ICICIBANK",
        "ICICIGI",
        "ICICIPRULI",
        "IDBI",
        "IDEA",
        "IDFCFIRSTB",
        "IEX",
        "IFCI",
        "IGIL",
        "IGL",
        "IIFL",
        "IKS",
        "INDGN",
        "INDHOTEL",
        "INDIACEM",
        "INDIAMART",
        "INDIANB",
        "INDIGO",
        "INDUSINDBK",
        "INDUSTOWER",
        "INFY",
        "INOXINDIA",
        "INOXWIND",
        "INTELLECT",
        "IOB",
        "IOC",
        "IPCALAB",
        "IRB",
        "IRCON",
        "IRCTC",
        "IREDA",
        "IRFC",
        "ITC",
        "ITCHOTELS",
        "ITI",
        "J&KBANK",
        "JBCHEPHARM",
        "JBMA",
        "JINDALSAW",
        "JINDALSTEL",
        "JIOFIN",
        "JKCEMENT",
        "JKTYRE",
        "JMFINANCIL",
        "JPPOWER",
        "JSL",
        "JSWCEMENT",
        "JSWENERGY",
        "JSWINFRA",
        "JSWSTEEL",
        "JUBLFOOD",
        "JUBLINGREA",
        "JUBLPHARMA",
        "JWL",
        "JYOTHYLAB",
        "JYOTICNC",
        "KAJARIACER",
        "KALYANKJIL",
        "KARURVYSYA",
        "KAYNES",
        "KEC",
        "KEI",
        "KFINTECH",
        "KIMS",
        "KIRLOSBROS",
        "KIRLOSENG",
        "KOTAKBANK",
        "KPIL",
        "KPITTECH",
        "KPRMILL",
        "KSB",
        "LALPATHLAB",
        "LATENTVIEW",
        "LAURUSLABS",
        "LEMONTREE",
        "LICHSGFIN",
        "LICI",
        "LINDEINDIA",
        "LLOYDSME",
        "LODHA",
        "LT",
        "LTF",
        "LTFOODS",
        "LTM",
        "LTTS",
        "LUPIN",
        "M&M",
        "M&MFIN",
        "MAHABANK",
        "MAHSCOOTER",
        "MAHSEAMLES",
        "MANAPPURAM",
        "MANKIND",
        "MANYAVAR",
        "MAPMYINDIA",
        "MARICO",
        "MARUTI",
        "MAXHEALTH",
        "MAZDOCK",
        "MCX",
        "MEDANTA",
        "METROPOLIS",
        "MFSL",
        "MGL",
        "MINDACORP",
        "MMTC",
        "MOTHERSON",
        "MOTILALOFS",
        "MPHASIS",
        "MRF",
        "MRPL",
        "MSUMI",
        "MUTHOOTFIN",
        "NAM-INDIA",
        "NATCOPHARM",
        "NATIONALUM",
        "NAUKRI",
        "NAVA",
        "NAVINFLUOR",
        "NBCC",
        "NCC",
        "NESTLEIND",
        "NETWEB",
        "NEULANDLAB",
        "NEWGEN",
        "NH",
        "NHPC",
        "NIACL",
        "NIVABUPA",
        "NLCINDIA",
        "NMDC",
        "NSLNISP",
        "NTPC",
        "NTPCGREEN",
        "NUVAMA",
        "NUVOCO",
        "NYKAA",
        "OBEROIRLTY",
        "OFSS",
        "OIL",
        "OLAELEC",
        "OLECTRA",
        "ONESOURCE",
        "ONGC",
        "PAGEIND",
        "PATANJALI",
        "PAYTM",
        "PCBL",
        "PERSISTENT",
        "PETRONET",
        "PFC",
        "PFIZER",
        "PGEL",
        "PGHH",
        "PHOENIXLTD",
        "PIDILITIND",
        "PIIND",
        "PNB",
        "PNBHOUSING",
        "POLICYBZR",
        "POLYCAB",
        "POLYMED",
        "POONAWALLA",
        "POWERGRID",
        "POWERINDIA",
        "PPLPHARMA",
        "PRAJIND",
        "PREMIERENE",
        "PRESTIGE",
        "PTCIL",
        "PVRINOX",
        "RADICO",
        "RAILTEL",
        "RAINBOW",
        "RAMCOCEM",
        "RBLBANK",
        "RCF",
        "RECLTD",
        "REDINGTON",
        "RELIANCE",
        "RELINFRA",
        "RHIM",
        "RITES",
        "RKFORGE",
        "RPOWER",
        "RRKABEL",
        "RVNL",
        "SAGILITY",
        "SAIL",
        "SAILIFE",
        "SAMMAANCAP",
        "SAPPHIRE",
        "SARDAEN",
        "SAREGAMA",
        "SBFC",
        "SBICARD",
        "SBILIFE",
        "SBIN",
        "SCHAEFFLER",
        "SCHNEIDER",
        "SCI",
        "SHREECEM",
        "SHRIRAMFIN",
        "SHYAMMETL",
        "SIEMENS",
        "SIGNATURE",
        "SJVN",
        "SOBHA",
        "SOLARINDS",
        "SONACOMS",
        "SONATSOFTW",
        "SRF",
        "STARHEALTH",
        "SUMICHEM",
        "SUNDARMFIN",
        "SUNDRMFAST",
        "SUNPHARMA",
        "SUNTV",
        "SUPREMEIND",
        "SUZLON",
        "SWANCORP",
        "SWIGGY",
        "SYNGENE",
        "SYRMA",
        "TARIL",
        "TATACHEM",
        "TATACOMM",
        "TATACONSUM",
        "TATAELXSI",
        "TATAINVEST",
        "TATAPOWER",
        "TATASTEEL",
        "TATATECH",
        "TBOTEK",
        "TCS",
        "TECHM",
        "TECHNOE",
        "TEJASNET",
        "THELEELA",
        "THERMAX",
        "TIINDIA",
        "TIMKEN",
        "TITAGARH",
        "TITAN",
        "TMPV",
        "TORNTPHARM",
        "TORNTPOWER",
        "TRENT",
        "TRIDENT",
        "TRITURBINE",
        "TRIVENI",
        "TTML",
        "TVSMOTOR",
        "UBL",
        "UCOBANK",
        "ULTRACEMCO",
        "UNIONBANK",
        "UNITDSPR",
        "UNOMINDA",
        "UPL",
        "USHAMART",
        "UTIAMC",
        "VBL",
        "VEDL",
        "VENTIVE",
        "VGUARD",
        "VIJAYA",
        "VMM",
        "VOLTAS",
        "VTL",
        "WAAREEENER",
        "WELCORP",
        "WELSPUNLIV",
        "WHIRLPOOL",
        "WIPRO",
        "WOCKPHARMA",
        "YESBANK",
        "ZEEL",
        "ZENSARTECH",
        "ZENTEC",
        "ZFCVINDIA",
        "ZYDUSLIFE",
    ]

    results = run_minervini_screener(symbols)
    candidates = filter_candidates(results)
    
    signals = []
    if candidates.empty:
        return signals
        
    candidates = candidates.rename(columns={"index": "Symbol"})
    now = datetime.now()
    
    for _, row in candidates.iterrows():
        symbol = row["Symbol"]
        # Conviction based on RS_Rating (70 to 100 maps to 0.0 to 1.0)
        rs_rating = float(row.get("RS_Rating", 70.0))
        conv = min(1.0, max(0.0, (rs_rating - 70.0) / 30.0))
        
        sig = Signal(
            symbol=symbol,
            strategy_name="minervini_screener",
            action=1,  # Passing candidates are buys
            conviction=round(conv, 2),
            timestamp=now,
            meta={
                "rs_rating": round(rs_rating, 2),
                "template_score": row.get("Template_Score"),
                "stage2": row.get("Stage2"),
                "high_proximity": round(float(row.get("High_Proximity", 0)), 2),
                "rvol": round(float(row.get("RVOL", 0)), 2)
            }
        )
        signals.append(sig)

    return signals
