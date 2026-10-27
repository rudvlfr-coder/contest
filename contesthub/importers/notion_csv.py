"""노션 데이터베이스 내보내기(_all.csv) 1회 가져오기. 작업지시서 F-09 매핑표 참고."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from ..eligibility import parse_targets
from ..models import CATEGORIES, SUBCATEGORIES, Contest
from ..store import merge
from ..textutil import clean_title, clean_url, make_id, parse_date, parse_datetime, parse_prize

# 제목에 이 중 하나도 없으면 사이트 이름이 제목으로 들어간 것으로 보고 확인 표시
_CONTEST_WORDS = re.compile(
    r"공모|모집|대회|콘테스트|contest|전$|상$|상\b|올림픽|챌린지|challenge|해커톤|hackathon|jam|잼|"
    r"인턴|채용|페스티벌|festival|캠프|camp|지원사업|awards?|cup|프로젝트|리그|투고|스토리콘|이벤트",
    re.I,
)


def _row_to_contest(row: dict[str, str]) -> Contest | None:
    raw_title = (row.get("이름") or "").strip()
    raw_url = (row.get("URL") or "").strip()
    if not raw_title and not raw_url:
        return None

    title, _ = clean_title(raw_title)
    url = clean_url(raw_url)
    start = parse_date(row.get("시작일"))
    end = parse_date(row.get("종료일"))
    created = parse_datetime(row.get("생성 일시"))
    reasons: list[str] = []

    category = (row.get("구분") or "").strip()
    categories = [category] if category in CATEGORIES else []
    if not categories:
        reasons.append("구분 없음")
    subcategories = [s.strip() for s in (row.get("장르") or "").split(",") if s.strip()]
    # 노션에서는 '대학'이 장르였지만 사이트에서는 구분(탭)으로 쓴다
    if "대학" in subcategories:
        subcategories.remove("대학")
        categories.append("대학")
        reasons = [r for r in reasons if r != "구분 없음"]
    unknown_sub = [s for s in subcategories if s not in SUBCATEGORIES]
    if unknown_sub:
        reasons.append(f"알 수 없는 장르: {', '.join(unknown_sub)}")

    organizer = (row.get("주최기관") or "").strip() or None
    apply_url = None
    if organizer and re.match(r"^(https?://|www\.)", organizer):
        apply_url, organizer = clean_url(organizer), None

    target_text = (row.get("참가대상") or "").strip() or None
    targets, eligible = parse_targets(target_text)

    prize_text = (row.get("상금") or "").strip() or None

    if not _CONTEST_WORDS.search(title):
        reasons.append("제목 확인")
    if not url:
        reasons.append("URL 없음")
    if not end:
        reasons.append("마감일 없음")

    start_s = start.isoformat() if start else None
    end_s = end.isoformat() if end else None
    stamp = created.isoformat(timespec="minutes") if created else None
    return Contest(
        id=make_id(title, start_s, end_s),
        title=title,
        official_url=url,
        apply_url=apply_url,
        organizer=organizer,
        categories=categories,
        subcategories=subcategories,
        start_date=start_s,
        end_date=end_s,
        prize_text=prize_text,
        prize_max_krw=parse_prize(prize_text),
        target_text=target_text,
        targets=targets,
        student_eligible=eligible,
        needs_review=bool(reasons),
        review_reasons=reasons,
        sources=[{"site": "notion", "url": url}] if url else [{"site": "notion", "url": None}],
        created_at=stamp,
        updated_at=stamp,
    )


def import_csv(path: Path) -> tuple[dict[str, Contest], dict[str, int]]:
    """CSV → {id: Contest}. 노션에서 분야를 달리하려고 복제한 행은 하나로 합친다."""
    stats = {"rows": 0, "skipped_empty": 0, "merged": 0}
    out: dict[str, Contest] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            stats["rows"] += 1
            c = _row_to_contest(row)
            if c is None:
                stats["skipped_empty"] += 1
                continue
            if c.id in out:
                merge(out[c.id], c)
                stats["merged"] += 1
            else:
                out[c.id] = c
    stats["contests"] = len(out)
    return out, stats
