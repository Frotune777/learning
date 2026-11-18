"""
File: src/scrapers/corporate_data.py
Purpose: Cache and provide access to NSE Corporate Actions, Announcements, Events, and Insider Trading.
Last Modified: 2026-05-30
"""

import logging
import os
from datetime import datetime, timedelta

import pandas as pd

from src.nse_live.nse_utils import NseUtils

LOGGER = logging.getLogger(__name__)


class CorporateDataScraper:
    """
    Downloads and caches all corporate actions, announcements, and events
    for the entire equities market in a single sweep to prevent rate limiting.
    Provides vectorized filtering for the technical screener.
    """

    CACHE_DIR = "data/corporate_cache"

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        self.nse = NseUtils()
        self.today_str = datetime.now().strftime("%d-%m-%Y")

        self.df_actions = pd.DataFrame()
        self.df_announcements = pd.DataFrame()
        self.df_events = pd.DataFrame()
        self.df_insider = pd.DataFrame()

    def fetch_and_cache_all(self, force_refresh: bool = False):
        """
        Pull 30 days of history and future events. Cache to avoid NSE rate limits.
        When OFFLINE mode is active, uses the newest local cache files without hitting NSE.
        """
        import glob
        import src.core.config as config
        is_offline = config.OFFLINE or config.Config.OFFLINE

        # Define cache paths
        actions_path = os.path.join(self.CACHE_DIR, f"actions_{self.today_str}.parquet")
        ann_path = os.path.join(
            self.CACHE_DIR, f"announcements_{self.today_str}.parquet"
        )
        events_path = os.path.join(self.CACHE_DIR, f"events_{self.today_str}.parquet")
        insider_path = os.path.join(self.CACHE_DIR, f"insider_{self.today_str}.parquet")

        def _load_or_fetch(cache_path: str, glob_pattern: str, fetch_fn):
            if not force_refresh and os.path.exists(cache_path):
                return pd.read_parquet(cache_path)
            if is_offline:
                candidates = sorted(glob.glob(os.path.join(self.CACHE_DIR, glob_pattern)), reverse=True)
                if candidates:
                    return pd.read_parquet(candidates[0])
                return pd.DataFrame()
            try:
                df = fetch_fn()
                if df is not None and not df.empty:
                    df.to_parquet(cache_path)
                return df if df is not None else pd.DataFrame()
            except Exception as exc:
                LOGGER.warning("Could not fetch corporate data (%s): %s", glob_pattern, exc)
                return pd.DataFrame()

        if is_offline:
            LOGGER.info("Offline mode: Loading corporate data from local cache...")
        else:
            LOGGER.info("Fetching corporate data from NSE...")

        from_date = (datetime.now() - timedelta(days=30)).strftime("%d-%m-%Y")
        to_date = (datetime.now() + timedelta(days=30)).strftime("%d-%m-%Y")
        today = self.today_str

        # 1. Actions
        self.df_actions = _load_or_fetch(
            actions_path, "actions_*.parquet",
            lambda: self.nse.get_corporate_action(from_date_str=from_date, to_date_str=to_date)
        )

        # 2. Announcements
        self.df_announcements = _load_or_fetch(
            ann_path, "announcements_*.parquet",
            lambda: self.nse.get_corporate_announcement(from_date_str=from_date, to_date_str=to_date)
        )

        # 3. Events Calendar
        self.df_events = _load_or_fetch(
            events_path, "events_*.parquet",
            lambda: self.nse.get_event_calendar()
        )

        # 4. Insider Trading
        self.df_insider = _load_or_fetch(
            insider_path, "insider_*.parquet",
            lambda: self.nse.get_insider_trading(from_date=from_date, to_date=today)
        )

        LOGGER.info("Corporate data ready.")

    def get_upcoming_actions(self, symbol: str) -> str:
        """Returns string indicating upcoming Dividend, Split, or Bonus."""
        if self.df_actions is None or self.df_actions.empty:
            return "None"

        # Search by symbol
        mask = self.df_actions["symbol"].str.upper() == symbol.upper()
        if not mask.any():
            return "None"

        actions = []
        for _, row in self.df_actions[mask].iterrows():
            subj = str(row.get("subject", "")).lower()
            if "dividend" in subj:
                actions.append("Div")
            if "split" in subj or "sub-division" in subj:
                actions.append("Split")
            if "bonus" in subj:
                actions.append("Bonus")

        return ", ".join(list(set(actions))) if actions else "None"

    def get_recent_announcements(self, symbol: str) -> str:
        """Returns True if a positive catalyst exists (Earnings, Order, Acquisition)."""
        if self.df_announcements is None or self.df_announcements.empty:
            return "No"

        mask = self.df_announcements["symbol"].str.upper() == symbol.upper()
        if not mask.any():
            return "No"

        for _, row in self.df_announcements[mask].iterrows():
            desc = str(row.get("desc", "")).lower()
            subj = str(row.get("subject", "")).lower()
            combined = desc + " " + subj
            if any(
                x in combined
                for x in [
                    "order",
                    "acquisition",
                    "financial results",
                    "fund raising",
                    "upgrade",
                ]
            ):
                return "Yes"
        return "No"

    def get_days_to_next_event(self, symbol: str) -> int:
        """Returns days to next board meeting / event. -1 if none found."""
        if self.df_events is None or self.df_events.empty:
            return -1

        mask = self.df_events["symbol"].str.upper() == symbol.upper()
        if not mask.any():
            return -1

        df_sym = self.df_events[mask].copy()

        # Parse dates
        if "date" in df_sym.columns:
            df_sym["event_date"] = pd.to_datetime(
                df_sym["date"], format="%d-%b-%Y", errors="coerce"
            )
            df_sym = df_sym[df_sym["event_date"] >= pd.Timestamp(datetime.now().date())]
            if df_sym.empty:
                return -1

            next_event = df_sym["event_date"].min()
            days = (next_event - pd.Timestamp(datetime.now().date())).days
            return days
        return -1

    def get_insider_score(self, symbol: str) -> int:
        """
        +3 = Large promoter buy
        +1 = Small promoter buy
         0 = No activity
        -2 = Promoter sell
        -3 = Pledge increase
        """
        if self.df_insider is None or self.df_insider.empty:
            return 0

        mask = self.df_insider["symbol"].str.upper() == symbol.upper()
        if not mask.any():
            return 0

        score = 0
        df_sym = self.df_insider[mask]

        for _, row in df_sym.iterrows():
            person = str(row.get("personCategory", "")).lower()
            acq_mode = str(row.get("acqMode", "")).lower()
            sec_val = pd.to_numeric(row.get("secVal", 0), errors="coerce")
            if pd.isna(sec_val):
                sec_val = 0

            if "promoter" in person:
                if "buy" in acq_mode or "market purchase" in acq_mode:
                    if sec_val > 10000000:  # > 1 crore
                        score += 3
                    else:
                        score += 1
                elif "sell" in acq_mode or "market sale" in acq_mode:
                    score -= 2
                elif "pledge" in acq_mode:
                    score -= 3

        return max(min(score, 3), -3)  # clamp between -3 and 3
