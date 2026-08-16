import re
from datetime import datetime
from typing import Optional
from tg_chat_logger.models import RawMessage, LogEvent


LEVEL_PATTERN = re.compile(
    r"\b(?P<level>CRITICAL|FATAL|ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE)\b",
    re.IGNORECASE
)

SERVICE_PATTERN = re.compile(
    r"(?:\[|\()(?P<service>[a-zA-Z0-9_-]{2,32})(?:\]|\))|service=(?P<kv_service>[a-zA-Z0-9_-]+)"
)

PYTHON_TRACEBACK_RE = re.compile(
    r"Traceback \(most recent call last\):[\s\S]+?(?=\n\n|\Z)",
    re.MULTILINE
)

HASHTAG_RE = re.compile(r"#([a-zA-Z0-9_]+)")


class MessageParser:
    def __init__(self, default_service: str = "unknown"):
        self.default_service = default_service

    def parse(self, raw: RawMessage) -> Optional[LogEvent]:
        text = raw.text.strip()
        if not text:
            return None

        # Extract log level
        lvl_match = LEVEL_PATTERN.search(text)
        level = lvl_match.group("level").upper() if lvl_match else "INFO"
        if level == "WARNING":
            level = "WARN"

        # Try service tag from [service-name] or service=foo
        service = self.default_service
        svc_match = SERVICE_PATTERN.search(text)
        if svc_match:
            service = svc_match.group("service") or svc_match.group("kv_service")

        # Extract tags like #prod #auth
        tags = HASHTAG_RE.findall(text)

        # Pull traceback if present
        stacktrace = None
        tb_match = PYTHON_TRACEBACK_RE.search(text)
        if tb_match:
            stacktrace = tb_match.group(0).strip()
            # Strip trace from main message body so it's readable in sqlite summaries
            cleaned_text = text.replace(tb_match.group(0), "").strip()
        else:
            cleaned_text = text

        first_line = cleaned_text.splitlines()[0] if cleaned_text else text.splitlines()[0]

        return LogEvent(
            raw_id=raw.message_id,
            chat_id=raw.chat_id,
            timestamp=raw.date,
            level=level,
            message=first_line,
            service=service,
            tags=tags,
            stacktrace=stacktrace,
        )
