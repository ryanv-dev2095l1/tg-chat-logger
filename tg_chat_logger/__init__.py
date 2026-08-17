"""Telegram alert channel scraper and parser."""

from tg_chat_logger.models import LogRecord, ParsedEvent
from tg_chat_logger.parser import parse_message

__version__ = "0.2.0"
__all__ = ["LogRecord", "ParsedEvent", "parse_message", "__version__"]
