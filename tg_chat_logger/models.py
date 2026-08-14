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


