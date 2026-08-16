from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class RawMessage:
    message_id: int
    chat_id: int
    text: str
    date: datetime
    sender_name: Optional[str] = None


@dataclass
class LogEvent:
    """Structured log record extracted from a Telegram message."""
    raw_id: int
    chat_id: int
    timestamp: datetime
    level: str
    message: str
    service: str = "unknown"
    tags: List[str] = field(default_factory=list)
    stacktrace: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FilterParams:
    min_level: str = "INFO"
    services: List[str] = field(default_factory=list)
    ignore_patterns: List[str] = field(default_factory=list)
