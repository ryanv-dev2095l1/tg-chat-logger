import hashlib
import re
from datetime import datetime
from typing import Optional, Tuple, List
from tg_chat_logger.models import RawMessage, LogEvent


LEVEL_PATTERN = re.compile(
    r"\b(?P<level>CRITICAL|FATAL|ERROR|WARN(?:ING)?|INFO|DEBUG|TRACE)\b",
    re.IGNORECASE
)

SERVICE_PATTERN = re.compile(
    r"(?:\[|\b)(?:app|service|svc)[:=](?P<kv_service>[a-zA-Z0-9_-]+)|(?:\[(?P<bracket_service>[a-zA-Z0-9_.-]+)\])"
)

PYTHON_TRACEBACK_RE = re.compile(
    r"Traceback \(most recent call last\):[\s\S]+?(?=\n\s*\n[a-zA-Z0-9\[]|\]|\Z)",
    re.MULTILINE
)

GO_PANIC_RE = re.compile(
    r"panic: [^\n]+(?:\n\ngoroutine \d+ \[[^\n]+\]:[\s\S]+)?(?=\n\s*\n|\Z)",
    re.MULTILINE
)

JAVA_STACK_RE = re.compile(
    r"(?:Exception|Error): [^\n]+(?:\n\s+at [^\n]+)+",
    re.MULTILINE
)

EXCEPTION_LINE_RE = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_.]*(?:Error|Exception|Panic)):\s*(.*)$",
    re.MULTILINE
)

HASHTAG_RE = re.compile(r"#([a-zA-Z0-9_-]+)")


def _compute_fingerprint(service: str, exc_type: Optional[str], message: str) -> str:
    # Normalizes message prefix so alerts group cleanly
    clean_msg = re.sub(r"\b[0-9a-f]{8,}\b", "<HEX>", message)
    clean_msg = re.sub(r"\b\d+\b", "<N>", clean_msg)
    key = f"{service}:{exc_type or ''}:{clean_msg[:120]}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


class MessageParser:
    def __init__(self, default_service: str = "unknown"):
        self.default_service = default_service

    def _extract_stacktrace(self, text: str) -> Tuple[Optional[str], Optional[str], str]:
        # Returns (stacktrace, exception_type, text_without_trace)
        for pattern in (PYTHON_TRACEBACK_RE, GO_PANIC_RE, JAVA_STACK_RE):
            match = pattern.search(text)
            if match:
                trace = match.group(0).strip()
                exc_type = None
                exc_match = EXCEPTION_LINE_RE.search(trace)
                if exc_match:
                    exc_type = exc_match.group(1)
                elif trace.startswith("panic:"):
                    exc_type = "panic"
                
                cleaned = text[:match.start()] + text[match.end():]
                return trace, exc_type, cleaned.strip()
        return None, None, text

    def parse(self, raw: RawMessage) -> Optional[LogEvent]:
        text = raw.text.strip()
        if not text:
            return None

        # print(f"DEBUG: parsing msg {raw.message_id} len={len(text)}")

        # Extract log level, fallback to ERROR if message contains a traceback
        stacktrace, exc_type, cleaned_text = self._extract_stacktrace(text)
        
        lvl_match = LEVEL_PATTERN.search(cleaned_text or text)
        if lvl_match:
            level = lvl_match.group("level").upper()
            if level == "WARNING":
                level = "WARN"
        elif stacktrace:
            level = "ERROR"
        else:
            level = "INFO"

        # Extract service identifier
        service = self.default_service
        svc_match = SERVICE_PATTERN.search(cleaned_text or text)
        if svc_match:
            candidate = svc_match.group("kv_service") or svc_match.group("bracket_service")
            # Ignore bracket matches that are just log levels like [ERROR]
            if candidate and candidate.upper() not in ("ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE", "CRITICAL"):
                service = candidate

        tags: List[str] = HASHTAG_RE.findall(text)

        # Trim noisy headers and blank lines to get a concise primary message
        lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
        if lines:
            summary = lines[0]
            # Some alert bots prepend level like 'ERROR: something broke'
            summary = re.sub(r"^(?:\[?\w+\]?:?\s*)+", "", summary).strip() or lines[0]
        else:
            summary = exc_type or "Empty alert payload"

        # TODO: parse nested JSON logfmt payloads if bot forwards docker logs directly
        fingerprint = _compute_fingerprint(service, exc_type, summary)

        return LogEvent(
            raw_id=raw.message_id,
            chat_id=raw.chat_id,
            timestamp=raw.date,
            level=level,
            message=summary,
            service=service,
            tags=tags,
            exception_type=exc_type,
            stacktrace=stacktrace,
            fingerprint=fingerprint,
        )
