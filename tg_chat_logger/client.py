import logging
import time
from typing import Any, Dict, Generator, List, Optional
import httpx

log = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, token: str, timeout: int = 30):
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout + 10.0)
        self._offset: Optional[int] = None

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def fetch_updates(self) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "timeout": self.timeout,
            "allowed_updates": ["message", "channel_post"],
        }
        if self._offset is not None:
            params["offset"] = self._offset

        res = self._client.get(f"{self.base_url}/getUpdates", params=params)
        # print("raw response:", res.text)
        res.raise_for_status()
        body = res.json()

        if not body.get("ok"):
            raise RuntimeError(f"telegram api error: {body.get('description')}")

        updates = body.get("result", [])
        if updates:
            highest_id = max(u["update_id"] for u in updates)
            self._offset = highest_id + 1
        return updates

    def poll(self, interval: float = 1.0) -> Generator[Dict[str, Any], None, None]:
        backoff = 1.0
        while True:
            try:
                updates = self.fetch_updates()
                backoff = 1.0
                for upd in updates:
                    yield upd
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                log.warning(f"telegram http status {status}: {e}")
                if status == 429:
                    time.sleep(10.0)
                else:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
            except Exception as e:
                log.error(f"poll error: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

            if interval > 0:
                time.sleep(interval)
