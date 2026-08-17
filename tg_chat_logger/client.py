import logging
import time
from typing import Any, Dict, Generator, List, Optional
import httpx

log = logging.getLogger(__name__)


class TelegramClient:
    """Minimal long-polling client for the Telegram Bot API."""

    def __init__(self, token: str, timeout: int = 30):
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout
        # Keep transport timeout larger than the long poll timeout
        self._client = httpx.Client(timeout=httpx.Timeout(timeout + 15.0, connect=10.0))
        self.last_offset: Optional[int] = None

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def drop_pending(self) -> None:
        # Set offset to -1 to flush queued messages on startup
        try:
            res = self._client.get(
                f"{self.base_url}/getUpdates",
                params={"offset": -1, "limit": 1, "timeout": 0},
            )
            if res.is_success:
                data = res.json().get("result", [])
                if data:
                    self.last_offset = data[-1]["update_id"] + 1
                    log.info(f"flushed pending updates up to offset {self.last_offset}")
        except Exception as err:
            log.warning(f"failed to drop pending updates: {err}")

    def fetch_updates(self) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "timeout": self.timeout,
            "allowed_updates": ["message", "channel_post"],
        }
        if self.last_offset is not None:
            params["offset"] = self.last_offset

        res = self._client.get(f"{self.base_url}/getUpdates", params=params)
        # print(f"DEBUG update payload: {res.json()}")

        if res.status_code == 429:
            # Telegram returns retry_after in parameters.retry_after or response headers
            retry_after = 5
            try:
                js = res.json()
                retry_after = js.get("parameters", {}).get("retry_after", 5)
            except Exception:
                pass
            log.warning(f"rate limited by telegram, sleeping {retry_after}s")
            time.sleep(float(retry_after))
            return []

        res.raise_for_status()
        body = res.json()

        if not body.get("ok"):
            desc = body.get("description", "unknown error")
            raise RuntimeError(f"telegram api rejected request: {desc}")

        updates = body.get("result", [])
        if updates:
            highest_id = max(u["update_id"] for u in updates)
            self.last_offset = highest_id + 1
        return updates

    def poll(self, interval: float = 0.5) -> Generator[Dict[str, Any], None, None]:
        backoff = 1.0
        while True:
            try:
                batch = self.fetch_updates()
                backoff = 1.0
                for upd in batch:
                    yield upd
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as net_err:
                log.warning(f"network glitch ({type(net_err).__name__}): {net_err}, retrying in {backoff:.1f}s")
                time.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)
            except httpx.HTTPStatusError as http_err:
                code = http_err.response.status_code
                if code == 401:
                    log.critical("invalid telegram bot token")
                    raise
                log.error(f"unexpected http status {code}: {http_err}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 45.0)
            except Exception as err:
                # TODO: add Sentry breadcrumb here if enabled
                log.error(f"poll loop uncaught error: {err}", exc_info=True)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

            if interval > 0:
                time.sleep(interval)
