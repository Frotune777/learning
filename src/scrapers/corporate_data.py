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
        """
        LOGGER.info("Fetching corporate data from NSE...")

        # Define cache paths
        actions_path = os.path.join(self.CACHE_DIR, f"actions_{self.today_str}.parquet")
        ann_path = os.path.join(
            self.CACHE_DIR, f"announcements_{self.today_str}.parquet"
        )
        events_path = os.path.join(self.CACHE_DIR, f"events_{self.today_str}.parquet")
        insider_path = os.path.join(self.CACHE_DIR, f"insider_{self.today_str}.parquet")

        from_date = (datetime.now() - timedelta(days=30)).strftime("%d-%m-%Y")
        to_date = (datetime.now() + timedelta(days=30)).strftime("%d-%m-%Y")
        today = self.today_str

        # 1. Actions
        if not force_refresh and os.path.exists(actions_path):
            self.df_actions = pd.read_parquet(actions_path)
        else:
            self.df_actions = self.nse.get_corporate_action(
                from_date_str=from_date, to_date_str=to_date
            )
            if self.df_actions is not None and not self.df_actions.empty:
                self.df_actions.to_parquet(actions_path)

        # 2. Announcements
        if not force_refresh and os.path.exists(ann_path):
            self.df_announcements = pd.read_parquet(ann_path)
        else:
            self.df_announcements = self.nse.get_corporate_announcement(
                from_date_str=from_date, to_date_str=to_date
            )
            if self.df_announcements is not None and not self.df_announcements.empty:
                self.df_announcements.to_parquet(ann_path)

        # 3. Events Calendar
        if not force_refresh and os.path.exists(events_path):
            self.df_events = pd.read_parquet(events_path)
        else:
            self.df_events = self.nse.get_event_calendar()
            if self.df_events is not None and not self.df_events.empty:
                self.df_events.to_parquet(events_path)

        # 4. Insider Trading
        if not force_refresh and os.path.exists(insider_path):
            self.df_insider = pd.read_parquet(insider_path)
        else:
            self.df_insider = self.nse.get_insider_trading(
                from_date=from_date, to_date=today
            )
            if self.df_insider is not None and not self.df_insider.empty:
                self.df_insider.to_parquet(insider_path)

        LOGGER.info("Corporate data fetch complete.")

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
