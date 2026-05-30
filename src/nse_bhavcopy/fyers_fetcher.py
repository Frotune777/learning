"""
File: src/nse_bhavcopy/fyers_fetcher.py
Purpose: Fyers API price fetcher implementing AbstractPriceFetcher for OHLCV data.
Last Modified: 2026-05-30
"""

import hashlib
import logging
import os
import time
from datetime import UTC, datetime

import pandas as pd
import requests

from src.data.fetcher.prices.base import AbstractPriceFetcher
from src.data.symbol_mapper import SymbolMapper

LOGGER: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FYERS_BASE_URL: str = "https://api-t1.fyers.in"
_FYERS_AUTH_URL: str = "https://api-t1.fyers.in/api/v3/validate-authcode"
_TOKEN_CACHE_FILE: str = "data/cache/fyers_token.txt"
_REQUEST_TIMEOUT: int = 30

# Internal timeframe resolution map: our "1d" → Fyers "1D"
_TIMEFRAME_MAP: dict[str, str] = {
    "1d": "1D",
    "1D": "1D",
    "D": "1D",
    "1w": "1D",  # Weekly: fetch daily, resample at caller level
    "1mo": "1D",  # Monthly: same pattern
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "4h": "240",
}

# Max bars per chunk per resolution
_CHUNK_DAYS: dict[str, int] = {
    "1D": 365,  # Fyers allows ~365d per call for daily
    "60": 60,
    "240": 60,
    "5": 30,
    "15": 30,
    "30": 30,
}


def _load_token_from_cache(cache_path: str) -> str | None:
    """
    Load the Fyers access token from a local cache file.

    Parameters:
        cache_path (str): Path to the token cache file. | Readable file path.

    Returns:
        str | None: Stripped token string, or None if file missing/empty.

    Raises:
        None

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> tok = _load_token_from_cache("data/cache/fyers_token.txt")
    """
    try:
        if os.path.exists(cache_path):
            with open(cache_path) as fh:
                tok = fh.read().strip()
                return tok if tok else None
    except OSError as exc:
        LOGGER.warning("Could not read token cache %s: %s", cache_path, exc)
    return None


def _save_token_to_cache(cache_path: str, token: str) -> None:
    """
    Persist the Fyers access token to a local cache file.

    Parameters:
        cache_path (str): Path for the token cache file. | Writable path.
        token (str): Access token string to persist.

    Returns:
        None

    Raises:
        None — OSError is logged and swallowed.

    Complexity:
        Time: O(1)
        Space: O(1)

    Example:
        >>> _save_token_to_cache("data/cache/fyers_token.txt", "abc123")
    """
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as fh:
            fh.write(token)
        LOGGER.info("Fyers token cached to %s", cache_path)
    except OSError as exc:
        LOGGER.warning("Could not write token cache %s: %s", cache_path, exc)


def exchange_auth_code(
    request_token: str,
    api_key: str,
    api_secret: str,
) -> str | None:
    """
    Exchange a Fyers authorization code for an access token via API v3.

    This is a one-time step after the user visits the Fyers login URL and
    receives the code as a query parameter. The access token is valid for
    one trading day and must be refreshed each morning.

    Parameters:
        request_token (str): Authorization code from Fyers login redirect.
        api_key (str): Fyers App ID (BROKER_API_KEY env var).
        api_secret (str): Fyers App Secret (BROKER_API_SECRET env var).

    Returns:
        str | None: Access token string, or None on failure.

    Raises:
        None — all HTTP errors are logged and None is returned.

    Complexity:
        Time: O(1) [single HTTP call]
        Space: O(1)

    Example:
        >>> tok = exchange_auth_code("auth_code_xyz", "APP_KEY", "APP_SECRET")
    """
    checksum = hashlib.sha256(f"{api_key}:{api_secret}".encode()).hexdigest()
    payload = {
        "grant_type": "authorization_code",
        "appIdHash": checksum,
        "code": request_token,
    }
    try:
        resp = requests.post(
            _FYERS_AUTH_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("s") == "ok":
            token: str = data["access_token"]
            LOGGER.info("Fyers token exchange successful.")
            return token
        LOGGER.error("Fyers auth error: %s", data.get("message", "unknown"))
    except requests.RequestException as exc:
        LOGGER.error("Fyers auth HTTP error: %s", exc)
    return None


class FyersFetcher(AbstractPriceFetcher):
    """
    Fyers API-backed implementation of AbstractPriceFetcher for NSE equities.

    Fetches historical OHLCV data from Fyers /data/history endpoint using
    chunked date ranges with automatic retry on transient failures.
    Falls back gracefully to YFinanceFetcher when token is missing/expired.

    Attributes:
        access_token (str | None): Fyers access token. | Loaded from env/cache.
        api_key (str | None): Fyers App ID from FYERS_API_KEY env var.
        token_cache (str): Path to on-disk token cache file.
        rate_delay (float): Sleep between consecutive chunk calls in seconds.
        fallback_enabled (bool): Whether to fall back to YFinance on auth failure.

    Public Methods:
        - fetch(symbol, timeframe, period, from_date, to_date): Fetch OHLCV data.
        - get_quotes(symbols): Return live LTP for a list of NSE symbols.
        - set_token(token): Manually set and cache the access token.
        - login_url(): Return the Fyers login URL for the user to visit.

    Thread Safety: No — token state is not thread-safe.
    """

    def __init__(
        self,
        access_token: str | None = None,
        token_cache: str = _TOKEN_CACHE_FILE,
        rate_delay: float = 0.5,
        fallback_enabled: bool = True,
    ) -> None:
        """
        Initialise FyersFetcher, loading token from env → cache → parameter.

        Priority order for token resolution:
            1. FYERS_ACCESS_TOKEN environment variable
            2. Local token cache file
            3. access_token argument passed directly

        Parameters:
            access_token (str | None): Token override. | Optional.
            token_cache (str): Path to cache file for token persistence.
            rate_delay (float): Seconds between chunk API calls. | >= 0.
            fallback_enabled (bool): Fall back to YFinance if token missing.

        Returns:
            None

        Raises:
            None

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> fetcher = FyersFetcher()
        """
        self.api_key: str | None = os.getenv("FYERS_API_KEY") or os.getenv(
            "BROKER_API_KEY"
        )
        self.token_cache: str = token_cache
        self.rate_delay: float = rate_delay
        self.fallback_enabled: bool = fallback_enabled

        # Resolve token: env → cache file → direct param
        env_token = os.getenv("FYERS_ACCESS_TOKEN")
        cached_token = _load_token_from_cache(token_cache)
        self.access_token: str | None = env_token or cached_token or access_token

        if self.access_token:
            LOGGER.info(
                "FyersFetcher: token loaded from %s.",
                "environment" if env_token else "cache/param",
            )
        else:
            LOGGER.warning(
                "FyersFetcher: no access token found. "
                "Set FYERS_ACCESS_TOKEN env var or call set_token()."
            )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_token(self, token: str) -> None:
        """
        Set the Fyers access token and persist it to the local cache.

        Parameters:
            token (str): Valid Fyers access token string.

        Returns:
            None

        Raises:
            None

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> fetcher.set_token("my_access_token")
        """
        self.access_token = token
        _save_token_to_cache(self.token_cache, token)
        LOGGER.info("Access token updated.")

    def login_url(
        self,
        redirect_uri: str = "https://trade.fyers.in/api-login/redirect-uri/index.html",
    ) -> str:
        """
        Return the Fyers login URL the user must visit to get an auth code.

        After visiting the URL and authenticating, Fyers redirects to
        redirect_uri?code=<auth_code>. Pass that code to exchange_auth_code().

        Parameters:
            redirect_uri (str): Redirect URI registered in the Fyers app config.

        Returns:
            str: Full Fyers login URL.

        Raises:
            RuntimeError: If FYERS_API_KEY / BROKER_API_KEY env var not set.

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> print(fetcher.login_url())
            https://api-t1.fyers.in/api/v3/generate-authcode?...
        """
        if not self.api_key:
            raise RuntimeError(
                "FYERS_API_KEY or BROKER_API_KEY environment variable not set."
            )
        return (
            f"https://api-t1.fyers.in/api/v3/generate-authcode"
            f"?client_id={self.api_key}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&state=nse_pipeline"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """Build the Authorization header for Fyers API requests."""
        return {
            "Authorization": f"{self.api_key}:{self.access_token}",
            "Content-Type": "application/json",
        }

    def _check_rate_limit(self) -> None:
        """
        Check daily usage and block if approaching 100k Fyers requests.
        """
        import json

        limit = 99500
        cache_file = "data/cache/fyers_usage.json"
        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

        count = 0
        try:
            if os.path.exists(cache_file):
                with open(cache_file) as f:
                    data = json.load(f)
                    if data.get("date") == today:
                        count = data.get("count", 0)
        except Exception:
            pass

        if count >= limit:
            LOGGER.critical("Fyers API rate limit reached (%d). Falling back.", count)
            raise RuntimeError("Fyers Rate Limit Exceeded")

        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump({"date": today, "count": count + 1}, f)
        except Exception as exc:
            LOGGER.warning("Could not update rate limit tracker: %s", exc)

    def _get(self, endpoint: str) -> dict[str, object]:
        """
        Execute a GET request to the Fyers API with retry logic.

        Parameters:
            endpoint (str): API path, e.g. '/data/history?...'.

        Returns:
            dict[str, object]: Parsed JSON response dict.

        Raises:
            RuntimeError: On exhausted retries or persistent HTTP errors.

        Complexity:
            Time: O(R) [R = retry attempts]
            Space: O(1)

        Example:
            >>> resp = fetcher._get("/data/quotes?symbols=NSE:TCS-EQ")
        """
        self._check_rate_limit()
        url = f"{_FYERS_BASE_URL}{endpoint}"
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(
                    url,
                    headers=self._headers(),
                    timeout=_REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data: dict[str, object] = resp.json()
                return data
            except requests.RequestException as exc:
                LOGGER.warning(
                    "Fyers GET attempt %d/%d failed: %s", attempt, max_retries, exc
                )
                if attempt < max_retries:
                    time.sleep(2 * attempt)
        raise RuntimeError(f"Fyers API GET failed after {max_retries} retries: {url}")

    @staticmethod
    def _candles_to_df(candles: list[list[float | int]]) -> pd.DataFrame:
        """
        Convert Fyers candle list to a DatetimeIndex OHLCV DataFrame.

        Parameters:
            candles (list): List of [epoch, open, high, low, close, volume] rows.

        Returns:
            pd.DataFrame: OHLCV with DatetimeIndex in IST (UTC+5:30).

        Raises:
            None

        Complexity:
            Time: O(N)
            Space: O(N)

        Example:
            >>> df = FyersFetcher._candles_to_df(
            ...     [[1716940800, 3500, 3550, 3480, 3520, 1e6]]
            ... )
        """
        if not candles:
            return pd.DataFrame()

        cols = ["epoch", "Open", "High", "Low", "Close", "Volume"]
        df = pd.DataFrame(candles, columns=cols[: len(candles[0])])
        # Fyers returns epoch in seconds (UTC)
        df.index = (
            pd.to_datetime(df["epoch"], unit="s", utc=True)
            .dt.tz_convert("Asia/Kolkata")
            .dt.normalize()
            .dt.tz_localize(None)
        )
        df.index.name = "Date"
        df = df.drop(columns=["epoch"], errors="ignore")
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Close"])
        return df

    def _fetch_chunk(
        self,
        fyers_sym: str,
        resolution: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """
        Fetch one date-range chunk from Fyers /data/history endpoint.

        Parameters:
            fyers_sym (str): Fyers symbol e.g. 'NSE:TCS-EQ'.
            resolution (str): Fyers resolution string e.g. '1D', '60'.
            start (datetime): Chunk start date (inclusive).
            end (datetime): Chunk end date (inclusive).

        Returns:
            pd.DataFrame: OHLCV DataFrame for this chunk, possibly empty.

        Raises:
            None — errors are logged and empty DataFrame returned.

        Complexity:
            Time: O(N) [N bars in chunk]
            Space: O(N)

        Example:
            >>> df = fetcher._fetch_chunk("NSE:TCS-EQ", "1D", dt1, dt2)
        """
        import urllib.parse

        sym_enc = urllib.parse.quote(fyers_sym)
        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")
        endpoint = (
            f"/data/history?"
            f"symbol={sym_enc}"
            f"&resolution={resolution}"
            f"&date_format=1"
            f"&range_from={start_str}"
            f"&range_to={end_str}"
            f"&cont_flag=1"
        )
        try:
            data = self._get(endpoint)
            if data.get("s") != "ok":
                LOGGER.warning(
                    "Fyers history error for %s [%s-%s]: %s",
                    fyers_sym,
                    start_str,
                    end_str,
                    data.get("message", "?"),
                )
                return pd.DataFrame()
            candles = data.get("candles", [])
            if not isinstance(candles, list):
                candles = []
            LOGGER.debug(
                "Fyers chunk %s [%s → %s]: %d bars",
                fyers_sym,
                start_str,
                end_str,
                len(candles),
            )
            return self._candles_to_df(candles)
        except RuntimeError as exc:
            LOGGER.error("Chunk fetch failed: %s", exc)
            return pd.DataFrame()

    def _fallback_fetch(
        self,
        symbol: str,
        timeframe: str,
        from_date: int | None,
        to_date: int | None,
    ) -> pd.DataFrame:
        """
        Fall back to YFinanceFetcher when Fyers token is unavailable.

        Parameters:
            symbol (str): NSE equity symbol.
            timeframe (str): Candle resolution.
            from_date (int | None): Start epoch.
            to_date (int | None): End epoch.

        Returns:
            pd.DataFrame: OHLCV data from YFinance.

        Raises:
            None

        Complexity:
            Time: O(N)
            Space: O(N)

        Example:
            >>> df = fetcher._fallback_fetch("TCS", "1d", None, None)
        """
        from src.data.fetcher.prices.yfinance_fetcher import YFinanceFetcher

        LOGGER.info("Fyers token missing — falling back to YFinance for %s.", symbol)
        return YFinanceFetcher().fetch(
            symbol, timeframe=timeframe, from_date=from_date, to_date=to_date
        )

    # ------------------------------------------------------------------
    # AbstractPriceFetcher interface
    # ------------------------------------------------------------------

    def fetch(
        self,
        symbol: str,
        timeframe: str = "1d",
        period: str = "1y",
        from_date: int | None = None,
        to_date: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Fyers API for an NSE equity symbol.

        Automatically handles:
        - Chunked date-range downloads (up to 365 days per call for daily)
        - Epoch-to-DatetimeIndex conversion in IST
        - Graceful fallback to YFinance when Fyers token is unavailable

        Parameters:
            symbol (str): NSE equity symbol e.g. 'TCS'. | Non-empty uppercase.
            timeframe (str): Candle resolution. | '1d', '5m', '15m', '1h', '4h'.
            period (str): Unused (date range preferred). | Default '1y'.
            from_date (int | None): Start UTC epoch seconds. | Default None (5yr back).
            to_date (int | None): End UTC epoch seconds. | Default None (now).

        Returns:
            pd.DataFrame: DatetimeIndex OHLCV DataFrame. Columns:
                Open, High, Low, Close, Volume. Empty on error or no data.

        Raises:
            None — falls back to YFinance on Fyers token errors.

        Complexity:
            Time: O(C * N) [C chunks, N bars per chunk]
            Space: O(C * N)

        Example:
            >>> fetcher = FyersFetcher()
            >>> df = fetcher.fetch("TCS", timeframe="1d", from_date=1609459200)
            >>> print(df.shape)
            (1250, 5)
        """
        if not self.access_token:
            if self.fallback_enabled:
                return self._fallback_fetch(symbol, timeframe, from_date, to_date)
            LOGGER.error("No Fyers token and fallback disabled for %s.", symbol)
            return pd.DataFrame()

        resolution = _TIMEFRAME_MAP.get(timeframe, "1D")
        chunk_days = _CHUNK_DAYS.get(resolution, 365)

        # Determine date range
        if to_date:
            end_dt = datetime.fromtimestamp(to_date, tz=UTC).replace(tzinfo=None)
        else:
            end_dt = datetime.utcnow()

        if from_date:
            start_dt = datetime.fromtimestamp(from_date, tz=UTC).replace(tzinfo=None)
        else:
            # Default: 5 years back
            from datetime import timedelta

            start_dt = end_dt - timedelta(days=5 * 365)

        fyers_sym = SymbolMapper.to_fyers(symbol)
        LOGGER.info(
            "Fyers fetch %s [%s] from %s to %s",
            fyers_sym,
            resolution,
            start_dt.date(),
            end_dt.date(),
        )

        chunks: list[pd.DataFrame] = []
        current = start_dt
        from datetime import timedelta

        while current <= end_dt:
            chunk_end = min(current + timedelta(days=chunk_days - 1), end_dt)
            df_chunk = self._fetch_chunk(fyers_sym, resolution, current, chunk_end)
            if not df_chunk.empty:
                chunks.append(df_chunk)
            current = chunk_end + timedelta(days=1)
            if current <= end_dt:
                time.sleep(self.rate_delay)

        if not chunks:
            LOGGER.warning("Fyers: no data returned for %s.", symbol)
            if self.fallback_enabled:
                return self._fallback_fetch(symbol, timeframe, from_date, to_date)
            return pd.DataFrame()

        result = pd.concat(chunks)
        result = result[~result.index.duplicated(keep="first")].sort_index()

        # For weekly/monthly timeframe requests, resample from daily data
        if timeframe in ("1w",):
            result = (
                result.resample("W-FRI")
                .agg(
                    {
                        "Open": "first",
                        "High": "max",
                        "Low": "min",
                        "Close": "last",
                        "Volume": "sum",
                    }
                )
                .dropna(subset=["Close"])
            )
        elif timeframe in ("1mo",):
            result = (
                result.resample("ME")
                .agg(
                    {
                        "Open": "first",
                        "High": "max",
                        "Low": "min",
                        "Close": "last",
                        "Volume": "sum",
                    }
                )
                .dropna(subset=["Close"])
            )

        LOGGER.info(
            "Fyers fetch complete: %s — %d bars (%s → %s)",
            symbol,
            len(result),
            result.index.min().date() if not result.empty else "n/a",
            result.index.max().date() if not result.empty else "n/a",
        )
        return result

    # ------------------------------------------------------------------
    # Live quotes
    # ------------------------------------------------------------------

    def get_quotes(self, symbols: list[str]) -> dict[str, float]:
        """
        Fetch real-time LTP (last traded price) for a list of NSE symbols.

        Parameters:
            symbols (list[str]): List of NSE equity symbols. | Non-empty.

        Returns:
            dict[str, float]: Map of symbol → LTP. Missing symbols absent.

        Raises:
            None — errors are logged and partial results returned.

        Complexity:
            Time: O(S) [S = number of symbols in batch]
            Space: O(S)

        Example:
            >>> prices = fetcher.get_quotes(["TCS", "INFY", "RELIANCE"])
            >>> print(prices["TCS"])
            3520.5
        """
        if not self.access_token:
            LOGGER.warning("get_quotes: no Fyers token — returning empty dict.")
            return {}

        import urllib.parse

        fyers_syms = [SymbolMapper.to_fyers(s) for s in symbols]
        encoded = urllib.parse.quote(",".join(fyers_syms))
        endpoint = f"/data/quotes?symbols={encoded}"

        result: dict[str, float] = {}
        try:
            data = self._get(endpoint)
            if data.get("s") != "ok":
                LOGGER.error("Fyers quotes error: %s", data.get("message", "unknown"))
                return result

            d_list = data.get("d", [])
            if not isinstance(d_list, list):
                d_list = []

            for item in d_list:
                if not isinstance(item, dict):
                    continue
                v = item.get("v", {})
                if not isinstance(v, dict):
                    v = {}
                raw_sym: str = str(item.get("n", ""))
                # Strip prefix/suffix: 'NSE:TCS-EQ' → 'TCS'
                bare = raw_sym.replace("NSE:", "").replace("-EQ", "")
                ltp = v.get("lp", 0.0)
                result[bare] = float(ltp)
        except RuntimeError as exc:
            LOGGER.error("get_quotes failed: %s", exc)

        return result
