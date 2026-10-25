"""여러 출처에 올라온 같은 공모전 찾기 (작업지시서 F-05)."""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher

from .models import Contest
from .textutil import normalize_title

SIMILARITY = 0.85


def _close_dates(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days) <= 1


def core_title(title: str) -> str:
    """'[밀리의서재] ...', '... | 밀리의서재', '... : 네이버 카페'처럼 앞뒤에 붙은 사이트 이름을 뗀다."""
    t = re.sub(r"^\s*[\[【「『][^\]】」』]{1,20}[\]】」』]\s*", "", title)
    t = re.split(r"\s+[|｜]\s+|\s+:\s+(?=[^:]{1,20}$)", t)[0]
    return normalize_title(t)


def _similar(ta: str, tb: str) -> bool:
    if not ta or not tb:
        return False
    shorter, longer = sorted((ta, tb), key=len)
    if len(shorter) >= 8 and shorter in longer:
        return True
    return SequenceMatcher(None, ta, tb).ratio() >= SIMILARITY


def same_contest(a: Contest, b: Contest) -> bool:
    if not _close_dates(a.end_date, b.end_date):
        return False
    return (_similar(normalize_title(a.title), normalize_title(b.title))
            or _similar(core_title(a.title), core_title(b.title)))


def find_duplicate(new: Contest, existing: dict[str, Contest]) -> Contest | None:
    if new.id in existing:
        return existing[new.id]
    for c in existing.values():
        if same_contest(new, c):
            return c
    return None
