import time
import pytest
from tg_chat_logger.models import LogEntry
from tg_chat_logger.storage import LogStorage


@pytest.fixture
def storage(tmp_path):
    db_file = tmp_path / "test_logs.db"
    s = LogStorage(str(db_file))
    s.init_db()
    yield s
    s.close()


def _make_entry(mid: int, level: str, svc: str, ts: int) -> LogEntry:
    return LogEntry(
        chat_id=-1001,
        message_id=mid,
        level=level,
        service_name=svc,
        message=f"msg {mid}",
        stacktrace=None,
        exception_type=None,
        context={},
        timestamp=ts,
    )


def test_insert_and_deduplication(storage):
    e = _make_entry(1, "ERROR", "cart", 1699000000)
    assert storage.save_entry(e) is True
    assert storage.save_entry(e) is False

    res = storage.query_entries(limit=5)
    assert len(res) == 1
    assert res[0].message_id == 1


def test_query_filtering(storage):
    storage.save_entry(_make_entry(10, "INFO", "auth", 100))
    storage.save_entry(_make_entry(11, "ERROR", "auth", 200))
    storage.save_entry(_make_entry(12, "CRITICAL", "billing", 300))
    storage.save_entry(_make_entry(13, "ERROR", "billing", 400))

    # filter by level
    errors = storage.query_entries(level="ERROR")
    assert len(errors) == 2
    assert {e.message_id for e in errors} == {11, 13}

    # filter by service
    billing = storage.query_entries(service="billing")
    assert len(billing) == 2
    assert {e.message_id for e in billing} == {12, 13}

    # combined filter
    crit_billing = storage.query_entries(service="billing", level="CRITICAL")
    assert len(crit_billing) == 1
    assert crit_billing[0].message_id == 12


def test_prune_older_than(storage):
    now = int(time.time())
    storage.save_entry(_make_entry(20, "INFO", "svc", now - 86400 * 10))  # 10 days old
    storage.save_entry(_make_entry(21, "INFO", "svc", now - 3600))        # 1 hour old

    deleted = storage.prune_older_than(days=7)
    assert deleted == 1

    remaining = storage.query_entries()
    assert len(remaining) == 1
    assert remaining[0].message_id == 21
