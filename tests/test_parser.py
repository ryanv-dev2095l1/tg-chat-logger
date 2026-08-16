import pytest
from tg_chat_logger.parser import parse_raw_message


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
    raw = '{"level": "CRITICAL", "service": "auth-service", "msg": "database unreachable", "user_id": 101}'
    entry = parse_raw_message(raw, chat_id=-100456, message_id=10)
    assert entry is not None
    assert entry.level == "CRITICAL"
    assert entry.service_name == "auth-service"
    assert entry.message == "database unreachable"
    assert entry.context.get("user_id") == 101


def test_fallback_unstructured():
    raw = "Something went very wrong on worker-03! Please check immediately."
    entry = parse_raw_message(raw, chat_id=-100123, message_id=99)
    assert entry is not None
    assert entry.level == "WARNING"  # default fallback when exclamation mark appears
    assert entry.service_name == "unknown"
    assert "Something went very wrong" in entry.message
