"""구글 시트(운영 수정용) 읽기와 적용 (작업지시서 6.2).

시트는 '웹에 게시 → CSV'로 공개하고, 탭마다 나오는 CSV 주소를 config/settings.json의 "sheet"에 넣는다.
주소 대신 로컬 CSV 파일 경로를 넣어도 된다 (시험용). 형식이 잘못된 행은 건너뛰고 경고로 남긴다.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from . import config
from .models import CATEGORIES, SUBCATEGORIES, TARGET_LABELS, Contest
from .textutil import clean_url, make_id, parse_date, parse_prize

log = logging.getLogger(__name__)

TARGET_CODES = {v: k for k, v in TARGET_LABELS.items()} | {"일반": "general", "누구나": "general"}
YES = {"o", "O", "y", "yes", "예", "✔", "✓", "true", "TRUE", "숨김", "사용"}


@dataclass
class SheetData:
    edits: dict[str, dict] = field(default_factory=dict)  # 공모전ID → 수정 내용
    additions: list[Contest] = field(default_factory=list)
    keywords: dict | None = None  # config.keywords()와 같은 형태 (시트가 있으면 덮어씀)
    sites: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _read_csv(source: str) -> list[dict[str, str]]:
    if source.startswith(("http://", "https://")):
        r = httpx.get(source, timeout=30, follow_redirects=True)
        r.raise_for_status()
        text = r.content.decode("utf-8-sig")
    else:
        text = Path(source).read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in rows]


def _split(value: str) -> list[str]:
    return [x.strip() for x in value.replace("/", ",").split(",") if x.strip()]


def _checked(value: str, valid: tuple | set, what: str, where: str, warnings: list[str]) -> list[str]:
    out = []
    for x in _split(value):
        if x in valid:
            out.append(x)
        else:
            warnings.append(f"{where}: 알 수 없는 {what} '{x}'")
    return out


def _targets(value: str, where: str, warnings: list[str]) -> list[str]:
    return [TARGET_CODES[x] for x in _checked(value, TARGET_CODES.keys(), "대상", where, warnings)]


def _edits(rows: list[dict], data: SheetData) -> None:
    for n, row in enumerate(rows, start=2):
        cid = row.get("공모전ID", "")
        where = f"수정 탭 {n}행"
        if not cid:
            continue
        edit: dict = {}
        if row.get("숨김", "") in YES:
            edit["hidden"] = True
        if row.get("구분"):
            edit["categories"] = _checked(row["구분"], CATEGORIES, "구분", where, data.warnings)
        if row.get("장르"):
            edit["subcategories"] = _checked(row["장르"], SUBCATEGORIES, "장르", where, data.warnings)
        if row.get("대상"):
            edit["targets"] = _targets(row["대상"], where, data.warnings)
        if row.get("마감일"):
            d = parse_date(row["마감일"])
            if d:
                edit["end_date"] = d.isoformat()
            else:
                data.warnings.append(f"{where}: 마감일 형식 오류 '{row['마감일']}' (예: 2026-11-30)")
        if row.get("제목수정"):
            edit["title"] = row["제목수정"]
        if edit:
            data.edits[cid] = edit


def _additions(rows: list[dict], data: SheetData) -> None:
    for n, row in enumerate(rows, start=2):
        title = row.get("제목", "")
        where = f"직접등록 탭 {n}행"
        if not title:
            continue
        start, end = parse_date(row.get("시작일")), parse_date(row.get("마감일"))
        if not end:
            data.warnings.append(f"{where}: 마감일이 없거나 형식 오류 → 건너뜀")
            continue
        start_s = start.isoformat() if start else None
        targets = _targets(row.get("대상", ""), where, data.warnings)
        url = clean_url(row.get("공식링크"))
        data.additions.append(Contest(
            id=make_id(title, start_s, end.isoformat()),
            title=title,
            official_url=url,
            organizer=row.get("주최") or None,
            categories=_checked(row.get("구분", ""), CATEGORIES, "구분", where, data.warnings),
            subcategories=_checked(row.get("장르", ""), SUBCATEGORIES, "장르", where, data.warnings),
            start_date=start_s,
            end_date=end.isoformat(),
            prize_text=row.get("상금") or None,
            prize_max_krw=parse_prize(row.get("상금")),
            targets=targets,
            student_eligible="yes" if targets else "unknown",
            region="overseas" if row.get("해외", "") in YES else "domestic",
            sources=[{"site": "sheet", "url": url}],
        ))


def _keywords(rows: list[dict], data: SheetData) -> None:
    base = config.keywords()
    kw = {"categories": {k: [] for k in base["categories"]},
          "subcategories": {k: [] for k in base["subcategories"]},
          "exclude_title": []}
    for n, row in enumerate(rows, start=2):
        kind, name, words = row.get("종류", ""), row.get("이름", ""), _split(row.get("키워드", ""))
        if kind == "구분" and name in kw["categories"]:
            kw["categories"][name] += words
        elif kind == "장르" and name in kw["subcategories"]:
            kw["subcategories"][name] += words
        elif kind == "제외":
            kw["exclude_title"] += words
        elif kind or name:
            data.warnings.append(f"키워드 탭 {n}행: 종류 '{kind}' / 이름 '{name}'을 알 수 없음")
    # 시트에 아무 키워드도 없으면 기본값을 그대로 쓴다 (빈 시트로 분류가 멈추지 않도록)
    if any(kw["categories"].values()):
        data.keywords = kw


def load_sheet() -> SheetData:
    sheet = config.settings().get("sheet", {})
    data = SheetData()
    readers = {"edit_csv": _edits, "add_csv": _additions, "keywords_csv": _keywords}
    for key, reader in readers.items():
        source = sheet.get(key, "")
        if not source:
            continue
        try:
            reader(_read_csv(source), data)
        except Exception as e:  # 시트를 못 읽어도 빌드는 계속
            data.warnings.append(f"시트({key})를 읽지 못함: {e}")
    if sheet.get("sites_csv"):
        try:
            for row in _read_csv(sheet["sites_csv"]):
                if row.get("사이트"):
                    data.sites[row["사이트"]] = row.get("사용", "") in YES
        except Exception as e:
            data.warnings.append(f"시트(sites_csv)를 읽지 못함: {e}")
    for w in data.warnings:
        log.warning(w)
    return data


def apply(contests: dict[str, Contest], data: SheetData) -> tuple[dict[str, Contest], list[str]]:
    """수정·직접등록을 적용한 사본을 돌려준다 (data/contests.json 원본은 그대로)."""
    out = {cid: Contest.from_dict(c.to_dict()) for cid, c in contests.items()}
    warnings = list(data.warnings)
    for c in data.additions:
        out.setdefault(c.id, c)
    hidden = set()
    for cid, edit in data.edits.items():
        c = out.get(cid)
        if c is None:
            warnings.append(f"수정 탭: 공모전ID '{cid}'를 찾을 수 없음")
            continue
        if edit.pop("hidden", False):
            hidden.add(cid)
        for k, v in edit.items():
            setattr(c, k, v)
        if {"categories", "subcategories", "targets"} & edit.keys():
            # 사람이 고친 건 자동 분류 경고를 지운다
            c.review_reasons = [r for r in c.review_reasons if r not in ("분류 확인 필요", "제목 확인", "구분 없음")]
            c.needs_review = bool(c.review_reasons)
        if "targets" in edit and edit["targets"]:
            c.student_eligible = "yes"
    for cid in hidden:
        out.pop(cid, None)
    return out, warnings
