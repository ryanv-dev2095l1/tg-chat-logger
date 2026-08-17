import asyncio
import logging
import signal
from typing import Optional

from tg_chat_logger.client import TelegramPoller, FloodWaitError
from tg_chat_logger.config import AppConfig
from tg_chat_logger.metrics import (
    MESSAGES_PROCESSED,
    PARSER_ERRORS,
    STORAGE_WRITES,
    POLL_ERRORS,
    start_metrics_server,
)
from tg_chat_logger.parser import parse_raw_message
from tg_chat_logger.storage import LogStorage

logger = logging.getLogger("tg_chat_logger.daemon")


class AlertDaemon:
    """Background worker that drains updates from Telegram and stores parsed logs."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.storage = LogStorage(config.db_path)
        self.poller = TelegramPoller(config.bot_token, config.monitored_chats, timeout=config.poll_timeout)
        self._stopping = False
        self._main_task: Optional[asyncio.Task] = None

    async def process_incoming(self, raw_msg: dict) -> None:
        # print(f"DEBUG: raw payload {raw_msg}")
        chat_id = raw_msg.get("chat", {}).get("id")
        message_id = raw_msg.get("message_id")
        date_ts = raw_msg.get("date")
        text = raw_msg.get("text") or raw_msg.get("caption") or ""

        # Telegram forwards or service notifications might not have text
        if not text.strip():
            return

        try:
            parsed = parse_raw_message(text, chat_id=chat_id, message_id=message_id, timestamp=date_ts)
        except Exception:
            PARSER_ERRORS.labels(chat_id=str(chat_id or "unknown")).inc()
            logger.debug("failed parsing text from chat_id=%s msg_id=%s", chat_id, message_id, exc_info=True)
            return

        if not parsed:
            PARSER_ERRORS.labels(chat_id=str(chat_id or "unknown")).inc()
            return

        MESSAGES_PROCESSED.labels(level=parsed.level, service=parsed.service_name).inc()
        inserted = self.storage.save_entry(parsed)
        if inserted:
            STORAGE_WRITES.labels(status="ok").inc()
        else:
            # Duplicate message received on reconnect
            STORAGE_WRITES.labels(status="duplicate").inc()

    async def _run_loop(self) -> None:
        # TODO: handle channel migration updates (migrate_to_chat_id)
        backoff = 1.0
        while not self._stopping:
            try:
                async for update in self.poller.poll():
                    if self._stopping:
                        break
                    backoff = 1.0  # reset on successful read
                    await self.process_incoming(update)
            except FloodWaitError as err:
                POLL_ERRORS.labels(type="flood_wait").inc()
                wait_sec = min(err.retry_after + 1, 120)
                logger.warning("hit flood limit, sleeping %ds", wait_sec)
                await asyncio.sleep(wait_sec)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                POLL_ERRORS.labels(type="generic").inc()
                logger.error("poll loop error: %s (backoff=%.1fs)", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)

    async def start(self) -> None:
        self.storage.init_db()
        if self.config.metrics_port:
            start_metrics_server(self.config.metrics_port)
            logger.info("prometheus metrics at :%d", self.config.metrics_port)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop)
            except NotImplementedError:
                # Windows fallback
                pass

        logger.info("daemon listening to %d channels", len(self.config.monitored_chats))
        self._main_task = asyncio.create_task(self._run_loop())
        try:
            await self._main_task
        except asyncio.CancelledError:
            pass
        finally:
            self.storage.close()
            logger.info("storage connections closed cleanly")

    def stop(self) -> None:
        if self._stopping:
            return
        logger.info("shutting down daemon...")
        self._stopping = True
        self.poller.stop()
        if self._main_task and not self._main_task.done():
            self._main_task.cancel()
