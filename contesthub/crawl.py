"""수집 실행: 수집기 → 분류 → 중복 제거 → 저장 (작업지시서 7장 처리 흐름)."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from . import config, overrides, store
from .classify import classify, competitor_hits
from .collectors import COLLECTORS
from .dedupe import find_duplicate
from .http import PoliteClient

log = logging.getLogger(__name__)

DATA = config.ROOT / "data"
SEEN_PATH = DATA / "seen.json"  # 이미 확인한 출처 URL (관련 없는 건도 다시 요청하지 않도록)
LOG_PATH = DATA / "crawl_log.json"


def _load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def run(sites: list[str] | None = None, limit: int | None = None) -> list[dict]:
    contests = store.load()
    seen: dict[str, dict] = _load_json(SEEN_PATH, {})
    for c in contests.values():
        for s in c.sources:
            if s.get("url"):
                seen.setdefault(s["url"], {"relevant": True, "id": c.id})

    site_options = {k: dict(v) for k, v in config.settings()["sites"].items()}
    # 구글 시트의 '키워드'·'수집사이트' 탭이 있으면 그 값을 쓴다
    sheet = overrides.load_sheet()
    config.override_keywords(sheet.keywords)
    for site, enabled in sheet.sites.items():
        if site in site_options:
            site_options[site]["enabled"] = enabled
    today = date.today().isoformat()
    client = PoliteClient()
    report = []
    try:
        for site, cls in COLLECTORS.items():
            opts = site_options.get(site, {})
            if not opts.get("enabled", False) or (sites and site not in sites):
                continue
            stats = {"site": site, "started_at": datetime.now().isoformat(timespec="seconds"),
                     "listed": 0, "already_seen": 0, "irrelevant": 0, "new": 0, "merged": 0,
                     "needs_review": 0, "errors": []}
            collector = cls(opts)
            processed = 0
            try:
                for item in collector.list_items(client):
                    stats["listed"] += 1
                    if item.url in seen:
                        stats["already_seen"] += 1
                        continue
                    if limit is not None and processed >= limit:
                        break
                    processed += 1
                    # 상세 페이지를 받기 전에 제목·분야로 한 번 거른다 (불필요한 요청 줄이기)
                    if collector.needs_detail and not classify(item.title, item.extra.get("field", "")).relevant:
                        seen[item.url] = {"relevant": False, "title": item.title}
                        stats["irrelevant"] += 1
                        continue
                    try:
                        if collector.needs_detail:
                            contest, body = collector.parse_detail(item, client.get_text(item.url))
                        else:
                            contest, body = collector.from_list_item(item)
                    except Exception as e:  # 한 건이 실패해도 나머지는 계속
                        log.exception("상세 처리 실패 %s", item.url)
                        stats["errors"].append(f"{item.url}: {e}")
                        continue

                    expired = contest.end_date and contest.end_date < today
                    if expired or classify(contest.title).excluded:
                        seen[item.url] = {"relevant": False, "title": contest.title}
                        stats["irrelevant"] += 1
                        continue
                    if not contest.categories:
                        result = classify(contest.title, body)
                        if not result.relevant:
                            seen[item.url] = {"relevant": False, "title": contest.title}
                            stats["irrelevant"] += 1
                            continue
                        contest.categories = result.categories
                        contest.subcategories = result.subcategories
                        if not result.confident:
                            contest.review_reasons.append("분류 확인 필요")
                    if not contest.end_date:
                        contest.review_reasons.append("마감일 없음")
                    # 경쟁사 관련 공모전은 본문까지 확인해 표시해 둔다 (사이트 생성 때 승인 전까지 비공개)
                    contest.competitor_hits = competitor_hits(contest.title, contest.organizer, body)
                    contest.needs_review = bool(contest.review_reasons)

                    dup = find_duplicate(contest, contests)
                    if dup:
                        # 이미 분류된 건(노션에서 사람이 정리한 건 포함)에는 자동 분류 경고를 옮기지 않는다
                        if dup.categories and "분류 확인 필요" in contest.review_reasons:
                            contest.review_reasons.remove("분류 확인 필요")
                            contest.needs_review = bool(contest.review_reasons)
                        store.merge(dup, contest)
                        target_id = dup.id
                        stats["merged"] += 1
                    else:
                        contests[contest.id] = contest
                        target_id = contest.id
                        stats["new"] += 1
                        stats["needs_review"] += int(contest.needs_review)
                    seen[item.url] = {"relevant": True, "id": target_id}
            except Exception as e:  # 목록 자체가 실패하면 이 사이트만 건너뛴다
                log.exception("%s 수집 실패", site)
                stats["errors"].append(str(e))
            stats["finished_at"] = datetime.now().isoformat(timespec="seconds")
            report.append(stats)
            # 사이트 하나 끝날 때마다 저장 (중간에 멈춰도 결과 보존)
            store.save(contests)
            _save_json(SEEN_PATH, seen)
    finally:
        client.close()

    history = _load_json(LOG_PATH, [])
    history.extend(report)
    _save_json(LOG_PATH, history[-200:])
    return report
