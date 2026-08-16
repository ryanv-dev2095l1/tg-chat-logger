import os
import tempfile
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


