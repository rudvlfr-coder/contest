"""사이트에 부담을 주지 않는 HTTP 클라이언트: 요청 간격, 재시도, 명시적 User-Agent."""
from __future__ import annotations

import logging
import time

import httpx

from . import config

log = logging.getLogger(__name__)


class PoliteClient:
    def __init__(self) -> None:
        s = config.settings()
        self.delay = float(s["request_delay_seconds"])
        self.retries = int(s["retries"])
        self._client = httpx.Client(
            headers={"User-Agent": s["user_agent"], "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5"},
            timeout=float(s["timeout_seconds"]),
            follow_redirects=True,
        )
        self._last = 0.0
        self.requests = 0

    def get_text(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                r = self._client.get(url)
                r.raise_for_status()
                return r.text
            except httpx.HTTPError as e:
                last_error = e
                log.warning("요청 실패 (%d/%d) %s: %s", attempt, self.retries, url, e)
                time.sleep(self.delay * attempt)
        raise RuntimeError(f"{url} 요청 {self.retries}회 실패: {last_error}")

    def close(self) -> None:
        self._client.close()
