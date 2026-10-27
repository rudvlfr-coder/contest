from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup

from ..eligibility import parse_targets
from ..http import PoliteClient
from ..models import Contest
from ..textutil import clean_url, make_id


@dataclass
class ListItem:
    url: str  # 출처 상세 페이지 (정규화된 고정 주소)
    title: str
    status: str | None = None  # 목록에 표시된 상태 (접수중, 마감 등)
    extra: dict = field(default_factory=dict)


class Collector:
    site: str = ""
    # False면 목록에서 바로 Contest를 만든다 (상세 페이지 요청 없음)
    needs_detail: bool = True

    def __init__(self, options: dict | None = None) -> None:
        self.options = options or {}

    def list_items(self, client: PoliteClient) -> Iterator[ListItem]:
        raise NotImplementedError

    def parse_detail(self, item: ListItem, html: str) -> tuple[Contest, str]:
        """(Contest, 분류용 본문 텍스트)."""
        raise NotImplementedError

    def from_list_item(self, item: ListItem) -> tuple[Contest, str]:
        raise NotImplementedError

    def parse_poster(self, html: str) -> str:
        """상세 페이지에서 포스터 주소만 뽑기 (예전에 수집한 공모전 포스터 채우기용). 없으면 ""."""
        return ""


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def text_of(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


# 본문에서 참가 자격 문단을 찾아 대상 판별에 쓴다
_ELIGIBILITY_HEAD = re.compile(r"(참가|응모|지원|참여|신청|공모)\s*(자격|대상)")


def eligibility_snippet(body: str, limit: int = 160) -> str:
    m = _ELIGIBILITY_HEAD.search(body)
    if not m:
        return ""
    return body[m.end():m.end() + limit]


def clean_poster(url: str | None) -> str:
    """포스터 주소는 https 이미지 주소만 받는다 (http는 https로 바꿔 시도)."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url if url.startswith("https://") else ""


def build_contest(site: str, item: ListItem, *, title: str, start: str | None, end: str | None,
                  organizer: str | None = None, official_url: str | None = None,
                  apply_url: str | None = None, prize_text: str | None = None,
                  prize_max: int | None = None, target_text: str | None = None,
                  region: str = "domestic", summary: str | None = None,
                  poster_url: str | None = None) -> Contest:
    targets, eligible = parse_targets(target_text)
    now = datetime.now().isoformat(timespec="minutes")
    return Contest(
        id=make_id(title, start, end),
        title=title,
        official_url=clean_url(official_url) or item.url,
        apply_url=clean_url(apply_url),
        organizer=organizer or None,
        start_date=start,
        end_date=end,
        prize_text=prize_text or None,
        prize_max_krw=prize_max,
        target_text=target_text or None,
        targets=targets,
        student_eligible=eligible,
        region=region,
        summary=summary,
        poster_url=poster_url if poster_url is None else (clean_poster(poster_url) or ""),
        sources=[{"site": site, "url": item.url}],
        created_at=now,
        updated_at=now,
    )
