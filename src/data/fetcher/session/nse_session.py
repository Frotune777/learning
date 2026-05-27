"""
File: src/data/fetcher/session/nse_session.py
Purpose: Cookie warm-up initializer for querying official NSE market APIs.

Dependencies:
External:
- requests>=2.32.3: Connection calls for warming up cookies
Internal:
- src.data.fetcher.session.manager: [SessionManager]

Key Components:
Classes:
- NSESessionInitializer: Handles page warming requests to extract cookies.
Functions:
- None

Last Modified: 2026-05-27
Modified By: Fortune

Open Tasks:
- [ ] [HIGH] Add automatic cookie re-warming when connection times out

Related Files:
- src/data/fetcher/prices/nse_charts.py: Warns the initializer prior to downloads.
"""

import logging
import time

from src.data.fetcher.session.manager import SessionManager

logger = logging.getLogger(__name__)


class NSESessionInitializer:
    """
    NSE CONNECTION WARM-UP MANAGER POPULATING SESSION COOKIES.

    Design Pattern: Lazy Initializer / Flyweight - Acquires session cookies
    from the main page once before initiating technical chart queries.

    Attributes:
        sm (SessionManager): Persistent HTTP session manager.
        main_url (str): Target landing page. | Default 'https://charting.nseindia.com/'
        initialized (bool): Track if landing cookies have been retrieved.

    Public Methods:
        - ensure_initialized(): Warms up connections and sets target cookies.

    Private Methods:
        None

    Usage Flow:
        1. Instantiate NSESessionInitializer with active SessionManager.
        2. Execute ensure_initialized() inside retrieval loops.

    Example:
        >>> sm = SessionManager()
        >>> init = NSESessionInitializer(session_manager=sm)
        >>> init.ensure_initialized()

    State Management:
        - Valid states: 'initialized' (True/False)
        - State transitions: Automatically shifts to True on successful fetch.

    Thread Safety: Partial - State changes are not lock-guarded.

    Dependencies:
        External: requests
        Internal: SessionManager
    """

    def __init__(
        self,
        session_manager: SessionManager,
        main_url: str = "https://charting.nseindia.com/",
    ) -> None:
        """Initialize with active session manager and targeted URL."""
        self.sm = session_manager
        self.main_url = main_url
        self.initialized = False

    def ensure_initialized(self) -> None:
        """
        EXECUTE PAGE COOKIE RETRIEVAL TO WARM UP CONNECTION CHANNELS.

        Logic:
            Step 1: Check if already initialized. If yes, bypass execution.
            Step 2: Get persistent requests session.
            Step 3: Execute GET call on target landing URL.
            Step 4: Check response code, log success, and set initialized=True.

        Parameters:
            None

        Returns:
            None

        Raises:
            requests.exceptions.HTTPError: Failed response on landing connection.

        Example:
            >>> sm = SessionManager()
            >>> init = NSESessionInitializer(sm)
            >>> init.ensure_initialized()

        Performance:
            Time Complexity: O(1) [Static landing page fetch]
            Space Complexity: O(1) [Session updates]

        Edge Cases Handled:
            - Bypasses fetch on subsequent runs to prevent heavy overheads.
        """
        if self.initialized:
            return

        logger.info("Initializing NSE Session: warming up cookies at %s", self.main_url)
        session = self.sm.get_session()
        proxy = self.sm.get_proxy()

        resp = session.get(
            self.main_url,
            headers={
                **self.sm.headers,
                "Accept": (
                    "text/html,application/xhtml+xml,xml;q=0.9," "image/webp,*/*;q=0.8"
                ),
            },
            timeout=25,
            proxies=proxy,
        )

        if resp.status_code != 200:
            logger.error(
                "Failed to warm up session cookies: Status %d", resp.status_code
            )
            resp.raise_for_status()

        # Warm up symbol page if main url is charting.nseindia.com
        if "charting.nseindia.com" in self.main_url:
            time.sleep(0.5)
            session.get(
                f"{self.main_url}/?symbol=TCS-EQ",
                headers={
                    **self.sm.headers,
                    "Accept": (
                        "text/html,application/xhtml+xml,xml;q=0.9,"
                        "image/webp,*/*;q=0.8"
                    ),
                },
                timeout=25,
                proxies=proxy,
            )

        logger.info(
            "NSE session warmed up successfully. Cookies: %s",
            session.cookies.get_dict(),
        )
        self.initialized = True
