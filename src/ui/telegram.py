"""Telegram notification service for Screeni-py."""

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
import logging

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for sending notifications via Telegram."""
    
    def __init__(self, bot_token: str, chat_id: str):
        """Initialize Telegram service with bot token and chat ID."""
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token) if bot_token else None
    
    def send_message(self, text: str, parse_mode: str = 'HTML') -> bool:
        """Send a text message to the configured chat."""
        if not self.bot:
            logger.warning("Telegram bot not configured")
            return False
        
        try:
            self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=ParseMode.HTML if parse_mode == 'HTML' else None
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_document(self, file_path: str, caption: str = None) -> bool:
        """Send a document/file to the configured chat."""
        if not self.bot:
            logger.warning("Telegram bot not configured")
            return False
        
        try:
            with open(file_path, 'rb') as f:
                self.bot.send_document(
                    chat_id=self.chat_id,
                    document=f,
                    caption=caption
                )
            return True
        except (TelegramError, IOError) as e:
            logger.error(f"Failed to send document: {e}")
            return False
    
    def send_photo(self, file_path: str, caption: str = None) -> bool:
        """Send a photo to the configured chat."""
        if not self.bot:
            logger.warning("Telegram bot not configured")
            return False
        
        try:
            with open(file_path, 'rb') as f:
                self.bot.send_photo(
                    chat_id=self.chat_id,
                    photo=f,
                    caption=caption
                )
            return True
        except (TelegramError, IOError) as e:
            logger.error(f"Failed to send photo: {e}")
            return False
