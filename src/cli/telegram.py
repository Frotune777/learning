"""
File: src/cli/telegram.py
Purpose: Lightweight Telegram notification service using the Bot API via requests.
         No extra dependencies — uses the `requests` package already in the project.
Last Modified: 2026-06-09
"""

import logging
import os
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)

_BASE_URL = "https://api.telegram.org/bot{token}/{method}"


class TelegramService:
    """
    Send notifications to a Telegram chat via the Bot HTTP API.

    Attributes:
        bot_token (str): Telegram bot token from @BotFather.
        chat_id (str): Target chat/group/channel ID.
        timeout (int): HTTP request timeout in seconds. | 10

    Public Methods:
        - send_message(text, parse_mode): Send a text message.
        - send_document(file_path, caption): Send a file/document.
        - send_screener_results(csv_path, date_str): Send screener CSV + summary.
        - test_connection(): Verify bot token is valid via getMe.

    Thread Safety: Yes — stateless HTTP calls.
    """

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        timeout: int = 10,
    ) -> None:
        """
        Initialise the Telegram service.

        Parameters:
            bot_token (str | None): Bot token. Falls back to TELEGRAM_BOT_TOKEN env var.
            chat_id (str | None): Chat ID. Falls back to TELEGRAM_CHAT_ID env var.
            timeout (int): Request timeout in seconds. | Default 10.

        Returns:
            None
        """
        self.bot_token: str = bot_token or os.getenv("TELEGRAM_BOT_TOKEN") or ""
        self.chat_id: str = chat_id or os.getenv("TELEGRAM_CHAT_ID") or ""
        self.timeout: int = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, method: str) -> str:
        """Build the full API endpoint URL for a given method."""
        return _BASE_URL.format(token=self.bot_token, method=method)

    def _is_configured(self) -> bool:
        """Return True only if both token and chat_id are non-empty."""
        if not self.bot_token or not self.chat_id:
            LOGGER.warning(
                "Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a text message to the configured Telegram chat.

        Parameters:
            text (str): Message content. | Max 4096 chars (Telegram limit).
            parse_mode (str): 'HTML' or 'Markdown'. | Default 'HTML'.

        Returns:
            bool: True on success, False on failure.

        Complexity:
            Time: O(1) [single HTTP POST]
            Space: O(1)

        Example:
            >>> svc = TelegramService()
            >>> svc.send_message("📈 Screener complete!")
        """
        if not self._is_configured():
            return False
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text[:4096],
            "parse_mode": parse_mode,
        }
        try:
            resp = requests.post(
                self._url("sendMessage"), json=payload, timeout=self.timeout
            )
            resp.raise_for_status()
            LOGGER.info("Telegram message sent successfully.")
            return True
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            if status == 400:
                LOGGER.error(
                    "Telegram 400 Bad Request — the bot cannot message this chat_id. "
                    "Open Telegram, search your bot, and send /start first."
                )
            else:
                LOGGER.error("Telegram HTTP error %s: %s", status, exc)
            return False
        except requests.RequestException as exc:
            LOGGER.error("Failed to send Telegram message: %s", exc)
            return False


    def send_document(self, file_path: str, caption: str = "") -> bool:
        """
        Send a file (CSV, PDF, etc.) to the configured Telegram chat.

        Parameters:
            file_path (str): Absolute path to the file. | Must exist.
            caption (str): Optional caption for the file. | Max 1024 chars.

        Returns:
            bool: True on success, False on failure.

        Complexity:
            Time: O(F) [F = file size upload]
            Space: O(F)

        Example:
            >>> svc.send_document("/data/final_list_20260601.csv", "Today's screener")
        """
        if not self._is_configured():
            return False
        if not os.path.exists(file_path):
            LOGGER.error("File not found for Telegram send: %s", file_path)
            return False
        try:
            with open(file_path, "rb") as fh:
                resp = requests.post(
                    self._url("sendDocument"),
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"document": fh},
                    timeout=self.timeout,
                )
            resp.raise_for_status()
            LOGGER.info("Telegram document sent: %s", file_path)
            return True
        except requests.RequestException as exc:
            LOGGER.error("Failed to send Telegram document: %s", exc)
            return False

    def send_screener_results(
        self,
        hist_dir: str,
        date_str: str,
        lists: list[str] | None = None,
    ) -> bool:
        """
        Send screener output CSVs + a summary message to Telegram.

        Sends a summary text first, then attaches each existing CSV file
        (final_list, swing_list, super_list) as documents.

        Parameters:
            hist_dir (str): Directory containing the screener output CSVs.
            date_str (str): Date string in YYYYMMDD format for filename matching.
            lists (list[str] | None): Which lists to send. Defaults to all three.

        Returns:
            bool: True if at least one file was sent successfully, False otherwise.

        Complexity:
            Time: O(F) [F = number of files to send]
            Space: O(1)

        Example:
            >>> svc.send_screener_results("data/historical", "20260601")
        """
        if not self._is_configured():
            return False

        if lists is None:
            lists = ["final_list", "swing_list", "super_list"]

        sent_any = False
        files_sent: list[str] = []
        files_missing: list[str] = []

        for prefix in lists:
            path = os.path.join(hist_dir, f"{prefix}_{date_str}.csv")
            if os.path.exists(path):
                files_sent.append(prefix.replace("_", " ").title())
            else:
                files_missing.append(prefix.replace("_", " ").title())

        # Summary message first
        lines = [
            f"📈 <b>NSE Screener Results — {date_str}</b>",
            "",
            f"✅ Ready: {', '.join(files_sent) if files_sent else 'None'}",
        ]
        if files_missing:
            lines.append(f"⚠️ Not generated: {', '.join(files_missing)}")

        self.send_message("\n".join(lines))

        # Attach CSVs
        for prefix in lists:
            path = os.path.join(hist_dir, f"{prefix}_{date_str}.csv")
            if os.path.exists(path):
                caption = f"📊 {prefix.replace('_', ' ').title()} — {date_str}"
                if self.send_document(path, caption):
                    sent_any = True

        return sent_any

    def test_connection(self) -> bool:
        """
        Verify the bot token by calling the Telegram getMe endpoint.

        Returns:
            bool: True if the token is valid and the bot is reachable.

        Complexity:
            Time: O(1)
            Space: O(1)

        Example:
            >>> TelegramService().test_connection()
            False
        """
        if not self.bot_token:
            LOGGER.warning("No bot token configured.")
            return False
        try:
            resp = requests.get(self._url("getMe"), timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                username = data.get("result", {}).get("username", "unknown")
                LOGGER.info("Telegram bot connected: @%s", username)
                return True
            return False
        except requests.RequestException as exc:
            LOGGER.error("Telegram connection test failed: %s", exc)
            return False
