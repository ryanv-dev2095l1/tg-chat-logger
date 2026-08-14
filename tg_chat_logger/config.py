import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class Config:
    """Runtime configuration parsed from TOML and environment variables."""
    bot_token: str
    chat_ids: List[int] = field(default_factory=list)
    db_path: Path = Path("alerts.sqlite3")
    poll_timeout: int = 30
    poll_interval: float = 1.0
    prometheus_port: int = 9102
    log_level: str = "INFO"
    drop_pending_updates: bool = False


def _parse_chat_ids(val: str) -> List[int]:
    ids = []
    for part in val.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def load_config(config_path: Optional[Path] = None) -> Config:
    data = {}
    if config_path and config_path.is_file():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

    tg_sec = data.get("telegram", {})
    store_sec = data.get("storage", {})
    prom_sec = data.get("metrics", {})
    app_sec = data.get("app", {})

    # Env overrides take precedence
    token = os.getenv("TG_BOT_TOKEN", tg_sec.get("token", ""))
    if not token:
        raise ValueError("bot token is required (set TG_BOT_TOKEN or config telegram.token)")

    env_chats = os.getenv("TG_CHAT_IDS")
    if env_chats is not None:
        chat_ids = _parse_chat_ids(env_chats)
    else:
        raw_ids = tg_sec.get("chat_ids", [])
        chat_ids = [int(x) for x in raw_ids if str(x).lstrip("-").isdigit()]

    db_str = os.getenv("TG_DB_PATH", store_sec.get("db_path", "alerts.sqlite3"))
    prom_port = int(os.getenv("TG_METRICS_PORT", prom_sec.get("port", 9102)))
    poll_to = int(os.getenv("TG_POLL_TIMEOUT", tg_sec.get("poll_timeout", 30)))
    poll_int = float(os.getenv("TG_POLL_INTERVAL", tg_sec.get("poll_interval", 1.0)))
    log_lvl = os.getenv("TG_LOG_LEVEL", app_sec.get("log_level", "INFO")).upper()
    drop_pend = os.getenv("TG_DROP_PENDING", str(tg_sec.get("drop_pending_updates", False))).lower() in ("1", "true", "yes")

    return Config(
        bot_token=token,
        chat_ids=chat_ids,
        db_path=Path(db_str),
        poll_timeout=poll_to,
        poll_interval=poll_int,
        prometheus_port=prom_port,
        log_level=log_lvl,
        drop_pending_updates=drop_pend,
    )
