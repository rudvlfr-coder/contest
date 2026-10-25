"""날짜·상금·URL·제목 정규화."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# ---------------------------------------------------------------- 날짜

_KO_DATE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_NUM_DATE = re.compile(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})")
_KO_TIME = re.compile(r"(오전|오후)\s*(\d{1,2}):(\d{2})")


def parse_date(text: str | None) -> date | None:
    """'2026년 4월 6일', '2026.11.30', '2026-11-30', '2026/11/30' → date."""
    if not text:
        return None
    m = _KO_DATE.search(text) or _NUM_DATE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def parse_datetime(text: str | None) -> datetime | None:
    """'2026년 2월 21일 오전 4:54' → datetime. 시각이 없으면 0시."""
    d = parse_date(text)
    if d is None:
        return None
    hour = minute = 0
    t = _KO_TIME.search(text or "")
    if t:
        hour, minute = int(t.group(2)) % 12, int(t.group(3))
        if t.group(1) == "오후":
            hour += 12
    return datetime(d.year, d.month, d.day, hour, minute)


# ---------------------------------------------------------------- 상금

_HANGUL_DIGITS = dict(zip("일이삼사오육칠팔구", "123456789"))
_SMALL = {"": 1, "십": 10, "백": 100, "천": 1000}
_BIG = {"": 1, "만": 10_000, "억": 100_000_000}
_AMOUNT_TOKEN = re.compile(r"(?:\d+(?:\.\d+)?[십백천]?[만억]?)+")
_CHUNK = re.compile(r"(\d+(?:\.\d+)?)([십백천]?)([만억]?)")


def _eval_amount(token: str) -> int | None:
    chunks = _CHUNK.findall(token)
    if not chunks:
        return None
    # 단위가 하나도 없으면 원 단위 숫자 그대로 (예: 60000000). 작은 숫자는 상금이 아님.
    if all(not s and not b for _, s, b in chunks):
        value = float("".join(n for n, _, _ in chunks))
        return int(value) if value >= 10_000 else None
    total = 0.0
    prev_big = None
    for num, small, big in chunks:
        # '1억5천'처럼 억 뒤에 만이 생략된 경우 → 5천만
        if prev_big == "억" and not big and small:
            big = "만"
        total += float(num) * _SMALL[small] * _BIG[big]
        prev_big = big or prev_big
    if total < 10_000:  # '2pro', '8회' 같은 오탐 방지
        return None
    return int(total)


def parse_prize(text: str | None) -> int | None:
    """상금 문구에서 최대 금액(원)을 추출. 금액이 없으면 None."""
    if not text:
        return None
    s = text.replace(",", "").replace(" ", "")
    s = re.sub(r"([일이삼사오육칠팔구])(?=[십백천만억])", lambda m: _HANGUL_DIGITS[m.group(1)], s)
    s = re.sub(r"(?<![\d.])([십백천])(?=[만억])", r"1\1", s)  # '천만원' → '1천만원'
    amounts = [a for a in (_eval_amount(t) for t in _AMOUNT_TOKEN.findall(s)) if a]
    return max(amounts) if amounts else None


# ---------------------------------------------------------------- URL

_TRACKING_KEYS = {"fbclid", "gclid", "referrer", "airbridge_referrer", "nav_hidden", "iframe"}


def clean_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", url):
        url = "https://" + url
    parts = urlsplit(url)
    path = re.sub(r";jsessionid=[^/?#]*", "", parts.path, flags=re.I)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_KEYS]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), parts.fragment))


# ---------------------------------------------------------------- 제목

def clean_title(title: str) -> tuple[str, bool]:
    """제목 앞뒤 정리. 노션 복제본 표시 '(1)'이 있었는지도 함께 돌려준다."""
    t = title.strip().strip('"').strip()
    t = re.sub(r"\s+", " ", t)
    copied = bool(re.search(r"\s\(\d+\)$", t))
    if copied:
        t = re.sub(r"\s\(\d+\)$", "", t)
    return t, copied


def normalize_title(title: str) -> str:
    """중복 판별용: 공백·기호 제거, 소문자."""
    t, _ = clean_title(title)
    t = t.lower()
    t = re.sub(r"[\s\-_|:·,.!?'\"「」『』<>〈〉\[\]()（）《》“”‘’]+", "", t)
    return t


def make_id(title: str, start: str | None, end: str | None) -> str:
    """공모전 고정 ID: '{연도}-{해시6자리}'. 마감 연장에 흔들리지 않도록 시작일 우선."""
    anchor = start or end or ""
    year = anchor[:4] if anchor else "0000"
    digest = hashlib.sha1(f"{normalize_title(title)}|{anchor}".encode()).hexdigest()[:6]
    return f"{year}-{digest}"
