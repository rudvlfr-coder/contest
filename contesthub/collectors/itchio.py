"""itch.io 게임잼. robots.txt에서 /search는 막혀 있으므로 /jams 목록만 쓴다."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterator

from .base import Collector, ListItem, build_contest, soup, text_of

BASE = "https://itch.io"
LISTS = ("/jams/in-progress", "/jams/upcoming")
KST = timezone(timedelta(hours=9))
# 몇 년씩 열려 있는 상시 잼은 공모전 목록에서 뺀다
MAX_OPEN_DAYS = 120

_DURATION = re.compile(r"(\d+)\s*(minute|hour|day|week|month|year)s?")
_UNIT_DAYS = {"minute": 1 / 1440, "hour": 1 / 24, "day": 1, "week": 7, "month": 30, "year": 365}


def _utc(text: str) -> datetime | None:
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _duration(text: str) -> timedelta | None:
    m = _DURATION.search(text)
    if not m:
        return None
    return timedelta(days=int(m.group(1)) * _UNIT_DAYS[m.group(2)])


def parse_list(html: str) -> list[ListItem]:
    items = []
    for jam in soup(html).select("div.jam"):
        a = jam.select_one("div.primary_info h3 a[href]")
        if a is None:
            continue
        row = jam.select_one("div.timestmap")
        when = _utc(text_of(row.select_one("span.date_countdown"))) if row else None
        label = text_of(row).lower() if row else ""
        duration = _duration(text_of(row.select_one("span.date_duration"))) if row else None
        start = end = None
        if when and label.startswith("starts"):
            start = when
            end = when + duration if duration else None
        elif when:
            end = when
        joined = text_of(jam.select_one("div.jam_stats span.number")).replace(",", "")
        cover = jam.select_one("div.jam_cover[data-background_image]")
        items.append(ListItem(
            url=BASE + a["href"].split("?")[0],
            title=text_of(a),
            status="upcoming" if start else "in-progress",
            extra={
                "start": start, "end": end,
                "joined": int(joined) if joined.isdigit() else 0,
                "summary": text_of(jam.select_one("p.short_text")) or None,
                "hosts": ", ".join(text_of(x) for x in jam.select("div.hosted_by a")),
                "poster": cover["data-background_image"] if cover else "",
            },
        ))
    return items


class ItchioCollector(Collector):
    site = "itchio"
    needs_detail = False

    def list_items(self, client) -> Iterator[ListItem]:
        max_pages = int(self.options.get("max_pages", 2))
        min_joined = int(self.options.get("min_joined", 50))
        now = datetime.now(timezone.utc)
        for path in LISTS:
            for page in range(1, max_pages + 1):
                items = parse_list(client.get_text(f"{BASE}{path}?page={page}"))
                if not items:
                    break
                for item in items:
                    end = item.extra["end"]
                    if item.extra["joined"] < min_joined or end is None:
                        continue
                    if end - now > timedelta(days=MAX_OPEN_DAYS):
                        continue
                    yield item

    def from_list_item(self, item: ListItem):
        start, end = item.extra["start"], item.extra["end"]
        contest = build_contest(
            self.site, item, title=item.title,
            start=start.astimezone(KST).date().isoformat() if start else None,
            end=end.astimezone(KST).date().isoformat(),
            organizer=item.extra["hosts"],
            target_text="누구나 (온라인, 해외 게임잼)",
            region="overseas",
            summary=item.extra["summary"],
            poster_url=item.extra.get("poster", ""),
        )
        contest.categories = ["게임"]
        contest.subcategories = ["프로그래밍", "대회"]
        return contest, ""
