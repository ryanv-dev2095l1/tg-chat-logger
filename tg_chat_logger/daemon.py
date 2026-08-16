import asyncio
import logging
from typing import Optional

from tg_chat_logger.client import TelegramPoller
from tg_chat_logger.config import AppConfig
from tg_chat_logger.metrics import (  # type: ignore
    MESSAGES_PROCESSED,
    PARSER_ERRORS,
    STORAGE_WRITES,
    start_metrics_server,
)
from tg_chat_logger.parser import parse_raw_message
from tg_chat_logger.storage import LogStorage

logger = logging.getLogger("tg_chat_logger.daemon")


class AlertDaemon:
    def __init__(self, config: AppConfig):
        self.config = config
        self.storage = LogStorage(config.db_path)
        self.poller = TelegramPoller(config.bot_token, config.monitored_chats)
        self._stopping = False

    async def process_incoming(self, raw_msg: dict) -> None:
        # print(f"DEBUG: raw payload {raw_msg}")
        chat_id = raw_msg.get("chat", {}).get("id")
        message_id = raw_msg.get("message_id")
        text = raw_msg.get("text") or raw_msg.get("caption") or ""

        if not text:
            return

        parsed = parse_raw_message(text, chat_id=chat_id, message_id=message_id)
        if not parsed:
            PARSER_ERRORS.labels(chat_id=str(chat_id)).inc()
            return

        MESSAGES_PROCESSED.labels(level=parsed.level, service=parsed.service_name).inc()
        inserted = self.storage.save_entry(parsed)
        if inserted:
            STORAGE_WRITES.labels(status="ok").inc()

    async def start(self) -> None:
        self.storage.init_db()
        if self.config.metrics_port:
            start_metrics_server(self.config.metrics_port)
            logger.info("metrics listening on port %d", self.config.metrics_port)

        logger.info("starting alert ingest daemon for %d channels", len(self.config.monitored_chats))
        
        while not self._stopping:
            try:
                async for update in self.poller.poll():
                    if self._stopping:
                        break
                    await self.process_incoming(update)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("poll loop crashed, sleeping 5s: %s", exc)
                await asyncio.sleep(5.0)

    def stop(self) -> None:
        self._stopping = True
        self.poller.stop()
        self.storage.close()
