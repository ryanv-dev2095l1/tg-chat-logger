import pytest
from tg_chat_logger.parser import parse_raw_message, extract_traceback


SAMPLE_TRACEBACK = """
ALERT: [worker-billing] Unhandled Exception
Traceback (most recent call last):
  File "/app/worker.py", line 45, in run
    process_invoice(inv_id)
  File "/app/billing/processor.py", line 12, in process_invoice
    raise ValueError("invalid amount: -50")
ValueError: invalid amount: -50
"""


def test_parse_simple_log_line():
    raw = "2023-11-04 12:00:00 [ERROR] payment-gateway: connection timed out to stripe"
    entry = parse_raw_message(raw, chat_id=-100123, message_id=42)
    assert entry is not None
    assert entry.level == "ERROR"
    assert entry.service_name == "payment-gateway"
    assert "connection timed out" in entry.message
    assert entry.chat_id == -100123
    assert entry.message_id == 42


def test_parse_json_dump():
    raw = '```json\n{"level": "CRITICAL", "service": "auth-service", "msg": "database unreachable", "user_id": 101}\n```'
    entry = parse_raw_message(raw, chat_id=-100456, message_id=10)
    assert entry is not None
    assert entry.level == "CRITICAL"
    assert entry.service_name == "auth-service"
    assert entry.message == "database unreachable"
    assert entry.context.get("user_id") == 101


def test_parse_traceback_extraction():
    entry = parse_raw_message(SAMPLE_TRACEBACK, chat_id=-100, message_id=5)
    assert entry is not None
    assert entry.level == "ERROR"
    assert entry.service_name == "worker-billing"
    assert entry.stacktrace is not None
    assert 'raise ValueError("invalid amount: -50")' in entry.stacktrace
    assert "ValueError" in entry.exception_type


def test_extract_traceback_helper():
    tb, exc_type = extract_traceback(SAMPLE_TRACEBACK)
    assert tb is not None
    assert tb.startswith("Traceback (most recent call last):")
    assert exc_type == "ValueError"


def test_extract_traceback_none():
    tb, exc_type = extract_traceback("Just a plain text alert with no traces")
    assert tb is None
    assert exc_type is None


def test_fallback_unstructured():
    raw = "Something went very wrong on worker-03! Please check immediately."
    entry = parse_raw_message(raw, chat_id=-100123, message_id=99)
    assert entry is not None
    assert entry.level == "WARNING"
    assert entry.service_name == "unknown"
    assert "Something went very wrong" in entry.message
