"""콘테스트코리아 (contestkorea.com). robots.txt 전체 허용."""
from __future__ import annotations

import re
from typing import Iterator
from urllib.parse import parse_qs, urljoin, urlsplit

from ..textutil import parse_date, parse_prize
from .base import Collector, ListItem, build_contest, soup, text_of

LIST_BASE = "https://www.contestkorea.com/sub/list.php"
VIEW_BASE = "https://www.contestkorea.com/sub/view.php"
# 문학•문예, 미술•디자인•웹툰, 학문•과학•IT, 아이디어•건축•창업, The 다양한 분야
CATEGORY_CODES = ("030110001", "030610001", "030310001", "031410001", "031810001")


def detail_url(href: str) -> str | None:
    q = parse_qs(urlsplit(urljoin(VIEW_BASE, href)).query)
    if "str_no" not in q:
        return None
    return f"{VIEW_BASE}?int_gbn=1&Txt_bcode={q.get('Txt_bcode', [''])[0]}&str_no={q['str_no'][0]}"


def parse_list(html: str) -> list[ListItem]:
    items = []
    for li in soup(html).select("div.list_style_2 > ul > li"):
        a = li.select_one("div.title > a[href]")
        if a is None:
            continue
        url = detail_url(a["href"])
        if not url:
            continue
        host = text_of(li.select_one("ul.host li.icon_1")).removeprefix("주최 .").strip()
        target = text_of(li.select_one("ul.host li.icon_2")).removeprefix("대상 .").strip()
        items.append(ListItem(
            url=url,
            title=text_of(a.select_one("span.txt")),
            status=text_of(li.select_one("span.condition")) or None,
            extra={"organizer": host, "target": target},
        ))
    return items


def parse_detail_html(html: str) -> dict:
    s = soup(html)
    info: dict[str, str] = {}
    for tr in s.select("div.txt_area table tr"):
        th, td = tr.select_one("th"), tr.select_one("td")
        if th and td:
            info[text_of(th)] = text_of(td)
    home = s.select_one("a.btn_Homelink[val2]")
    apply = s.select_one("tr a.homepage_go[href^='http']")
    area = s.select_one("div.view_cont_area")
    return {
        "title": text_of(s.select_one("div.view_top_area h1")),
        "info": info,
        "homepage": home["val2"] if home else None,
        "apply": apply["href"] if apply else None,
        "body": text_of(area),
    }


class ContestKoreaCollector(Collector):
    site = "contestkorea"

    def list_items(self, client) -> Iterator[ListItem]:
        max_pages = int(self.options.get("max_pages", 2))
        seen: set[str] = set()
        for code in CATEGORY_CODES:
            for page in range(1, max_pages + 1):
                # 정렬 '접수중'(마감일 오름차순)
                url = (f"{LIST_BASE}?displayrow=50&int_gbn=1&Txt_bcode={code}"
                       f"&Txt_sortkey=a.str_aedate&Txt_sortword=asc&page={page}")
                items = [i for i in parse_list(client.get_text(url)) if i.url not in seen]
                if not items:
                    break
                for item in items:
                    seen.add(item.url)
                    if item.status not in ("마감", "심사중", "발표"):
                        yield item

    def parse_detail(self, item: ListItem, html: str):
        d = parse_detail_html(html)
        info = d["info"]
        start_s, _, end_s = info.get("접수기간", "").partition("~")
        start, end = parse_date(start_s), parse_date(end_s)
        prize_text = info.get("시상내역", "")
        # 콘테스트코리아는 참가대상이 표에 정리되어 있어 본문에서 따로 찾지 않는다
        target_text = re.sub(r"\s*,\s*", ", ", info.get("참가대상", "")).strip(", ")
        contest = build_contest(
            self.site, item, title=d["title"] or item.title,
            start=start.isoformat() if start else None,
            end=end.isoformat() if end else None,
            organizer=info.get("주최 . 주관") or item.extra.get("organizer"),
            official_url=d["homepage"], apply_url=d["apply"],
            prize_text=prize_text, prize_max=parse_prize(prize_text),
            target_text=target_text,
        )
        return contest, d["body"]
