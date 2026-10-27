"""엠굿·월간 미대입시 (mgood.co.kr). 대학 주최 고등학생 실기대회·공모전 모음.

robots.txt에 일반 수집 제한 없음. 서버가 중간 인증서를 보내지 않아 config/certs/의 Sectigo 중간 인증서로 검증한다.
목록 한 줄에 종류·제목·공모부문·주최·접수기간(연도 포함)·상태가 모두 있어, 상세 페이지는 참가자격만 읽는다.
"""
from __future__ import annotations

import re
from typing import Iterator
from urllib.parse import parse_qs, urlsplit

from ..textutil import parse_date
from .base import Collector, ListItem, build_contest, soup, text_of

BASE = "https://www.mgood.co.kr/contest/"
LISTS = ("21001_contest_list.php?page={page}", "21001_contest_list.php?state=other&page={page}")
_PERIOD = re.compile(r"(\d{4}-\d{2}-\d{2})\([^)]*\)\s*~\s*(\d{4}-\d{2}-\d{2})")


def detail_url(href: str) -> str | None:
    seq = parse_qs(urlsplit(href).query).get("c_seq", [None])[0]
    return f"{BASE}21002_contest_view.php?c_seq={seq}" if seq else None


def parse_list(html: str) -> list[ListItem]:
    items = []
    for a in soup(html).select("a[href*='21002_contest_view']"):
        tr = a.find_parent("tr")
        url = detail_url(a.get("href", ""))
        if tr is None or not url:
            continue
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 5:
            continue
        fields = text_of(cells[1].select_one("div.tt"))
        period = _PERIOD.search(text_of(cells[3]))
        status = text_of(cells[4])
        items.append(ListItem(
            url=url,
            title=text_of(a),
            status="마감" if status.startswith("마감") or "종료" in status else status.split(" ")[0],
            extra={
                "kind": text_of(cells[0]),
                "field": re.sub(r"\s*외 \d+개$", "", fields),
                "organizer": text_of(cells[2]),
                "start": period.group(1) if period else None,
                "end": period.group(2) if period else None,
            },
        ))
    return items


def parse_detail_html(html: str) -> dict:
    info: dict[str, str] = {}
    for th in soup(html).select("th"):
        td = th.find_next_sibling("td")
        if td is not None:
            info[text_of(th)] = text_of(td)
    return info


class MgoodCollector(Collector):
    site = "mgood"

    def list_items(self, client) -> Iterator[ListItem]:
        max_pages = int(self.options.get("max_pages", 2))
        seen: set[str] = set()
        for path in LISTS:
            for page in range(1, max_pages + 1):
                items = [i for i in parse_list(client.get_text(BASE + path.format(page=page))) if i.url not in seen]
                if not items:
                    break
                for item in items:
                    seen.add(item.url)
                    if item.status != "마감":
                        yield item

    def parse_detail(self, item: ListItem, html: str):
        info = parse_detail_html(html)
        target = info.get("참가자격", "")
        start, end = item.extra["start"], item.extra["end"]
        contest = build_contest(
            self.site, item, title=item.title,
            start=start, end=end if parse_date(end or "") else None,
            organizer=item.extra["organizer"],
            target_text=target,
        )
        # 목록의 공모부문(칸만화, 웹툰, 게임컨셉아트 …)을 본문 대신 분류에 쓴다
        return contest, f"{item.extra['field']} {info.get('공모부문', '')}"
