"""위비티 (wevity.com). robots.txt 전체 허용."""
from __future__ import annotations

import re
from typing import Iterator
from urllib.parse import parse_qs, urljoin, urlsplit

from ..textutil import parse_date, parse_prize
from .base import Collector, ListItem, build_contest, eligibility_snippet, soup, text_of

BASE = "https://www.wevity.com/"
# 19: 디자인/캐릭터/웹툰, 21: 게임/소프트웨어, 23: 문학/글/시나리오
CATEGORY_IDS = (19, 21, 23)
MODES = ("ing", "future")  # 접수중, 접수예정


def detail_url(ix: str) -> str:
    return f"{BASE}?c=find&s=1&gbn=viewok&ix={ix}"


def parse_list(html: str) -> list[ListItem]:
    items = []
    for li in soup(html).select("div.ms-list ul.list > li"):
        if "top" in (li.get("class") or []):
            continue
        a = li.select_one("div.tit > a")
        if a is None:
            continue
        ix = parse_qs(urlsplit(a.get("href", "")).query).get("ix", [None])[0]
        if not ix:
            continue
        for span in a.select("span"):
            span.decompose()
        items.append(ListItem(
            url=detail_url(ix),
            title=text_of(a),
            status=text_of(li.select_one("span.dday")) or None,
            extra={"organizer": text_of(li.select_one("div.organ")),
                   "field": text_of(li.select_one("div.sub-tit")).removeprefix("분야 : ")},
        ))
    return items


def parse_detail_html(html: str) -> dict:
    s = soup(html)
    info: dict[str, str] = {}
    homepage = None
    for li in s.select("ul.cd-info-list > li"):
        key_el = li.select_one("span.tit")
        key = text_of(key_el)
        if not key:
            continue
        if key == "홈페이지":
            a = li.select_one("a[href]")
            homepage = a["href"] if a else None
        key_el.decompose()
        info[key] = text_of(li)
    poster = s.select_one("div.cd-area div.thumb img[src]")
    return {
        "title": text_of(s.select_one("div.tit-area h6.tit")),
        "info": info,
        "homepage": homepage,
        "body": text_of(s.select_one("#viewContents")),
        "poster": urljoin(BASE, poster["src"]) if poster else "",
    }


class WevityCollector(Collector):
    site = "wevity"

    def parse_poster(self, html: str) -> str:
        return parse_detail_html(html)["poster"]

    def list_items(self, client) -> Iterator[ListItem]:
        max_pages = int(self.options.get("max_pages", 3))
        seen: set[str] = set()
        for cidx in CATEGORY_IDS:
            for mode in MODES:
                for page in range(1, max_pages + 1):
                    url = f"{BASE}?c=find&s=1&gub=1&cidx={cidx}&gbn=list&mode={mode}&gp={page}"
                    items = [i for i in parse_list(client.get_text(url)) if i.url not in seen]
                    if not items:
                        break
                    for item in items:
                        seen.add(item.url)
                        if item.status != "마감":
                            yield item

    def parse_detail(self, item: ListItem, html: str):
        d = parse_detail_html(html)
        info = d["info"]
        period = info.get("접수기간", "")
        start_s, _, end_s = period.partition("~")
        start, end = parse_date(start_s), parse_date(end_s)
        first, total = info.get("1등 상금", ""), info.get("총 상금", "")
        prize_text = " / ".join(x for x in (f"1등 {first}" if first else "", f"총상금 {total}" if total else "") if x)
        organizer = re.split(r"\s*/\s*", info.get("주최/주관", ""))[0] or item.extra.get("organizer")
        target_text = ", ".join(x for x in (info.get("응모대상", ""), eligibility_snippet(d["body"])) if x and x != "기타")
        title = d["title"] or item.title
        contest = build_contest(
            self.site, item, title=title,
            start=start.isoformat() if start else None,
            end=end.isoformat() if end else None,
            organizer=organizer, official_url=d["homepage"],
            prize_text=prize_text, prize_max=parse_prize(first) or parse_prize(total),
            target_text=target_text,
            region="overseas" if "해외" in info.get("분야", "") else "domestic",
            poster_url=d["poster"],
        )
        # 위비티 '분야'는 범위가 넓어서(게임/소프트웨어에 보안 공모전도 포함) 분류 점수에는 넣지 않는다
        return contest, d["body"]
