"""사이트에 부담을 주지 않는 HTTP 클라이언트: 요청 간격, 재시도, 명시적 User-Agent."""
from __future__ import annotations

import logging
import ssl
import time

import certifi
import httpx

from . import config

log = logging.getLogger(__name__)


def ssl_context() -> ssl.SSLContext:
    """기본 루트 인증서 + config/certs/의 중간 인증서.

    일부 사이트(엠굿)는 서버가 중간 인증서를 보내지 않아 검증에 실패한다. 브라우저는 빠진 인증서를
    스스로 받아 오지만 Python은 그러지 않으므로, 발급기관(Sectigo) 공식 저장소에서 받은 중간 인증서를
    추가해 정상적으로 검증한다. 인증서 검사를 끄지 않는다.
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    for pem in sorted((config.CONFIG_DIR / "certs").glob("*.pem")):
        ctx.load_verify_locations(cafile=str(pem))
    return ctx


class PoliteClient:
    def __init__(self) -> None:
        s = config.settings()
        self.delay = float(s["request_delay_seconds"])
        self.retries = int(s["retries"])
        self._client = httpx.Client(
            headers={"User-Agent": s["user_agent"], "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5"},
            timeout=float(s["timeout_seconds"]),
            follow_redirects=True,
            verify=ssl_context(),
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
