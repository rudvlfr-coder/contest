"""구글 시트(운영 수정용) 읽기와 적용 (작업지시서 6.2).

시트는 '웹에 게시 → CSV'로 공개하고, 탭마다 나오는 CSV 주소를 config/settings.json의 "sheet"에 넣는다.
주소 대신 로컬 CSV 파일 경로를 넣어도 된다 (시험용). 형식이 잘못된 행은 건너뛰고 경고로 남긴다.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
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
    approvals: dict[str, str] = field(default_factory=dict)  # 공모전ID → '승인' / '거절'
    confirmed: set[str] = field(default_factory=set)  # '확인 필요' 표시를 지울 공모전ID
    manual_info: dict = field(default_factory=dict)  # 직접 등록 key → 자동 채움 결과 (관리자 페이지 표시용)
    warnings: list[str] = field(default_factory=list)


DECISIONS_PATH = config.ROOT / "data" / "decisions.json"
# 관리자 페이지 버튼 → data/decisions.json에 저장되는 값
DECISION_ACTIONS = {"approve": "승인", "hide": "거절", "confirm": "확인"}


MANUAL_PATH = config.CONFIG_DIR / "manual_contests.json"
_MANUAL_FIELDS = ("organizer", "target_text", "prize_text", "summary")


def manual_rows(path: Path = MANUAL_PATH, decisions_path: Path = DECISIONS_PATH) -> tuple[list[dict], str]:
    """직접 등록 목록. 관리자 페이지에서 한 번이라도 저장했으면(decisions.json의 '_manual') 그것만 쓰고,
    아니면 예전 방식의 config/manual_contests.json을 쓴다 (첫 저장 때 관리자 페이지가 옮겨 담음)."""
    if decisions_path.exists():
        try:
            decisions = json.loads(decisions_path.read_text(encoding="utf-8") or "{}")
        except ValueError:
            decisions = {}
        if isinstance(decisions.get("_manual"), list):
            return decisions["_manual"], "admin"
    if path.exists():
        try:
            rows = json.loads(path.read_text(encoding="utf-8")).get("contests", [])
        except ValueError:
            return [], "file-error"
        return [dict(r, key=r.get("key") or f"f{n}") for n, r in enumerate(rows, start=1)], "file"
    return [], "none"


def _naver_webtoon_notice(url: str) -> dict | None:
    """네이버웹툰 공지(comic.naver.com/notice/detail?noticeId=N)는 화면을 스크립트로 그려서 og 태그가 비어 있다.
    네이버가 공지 화면에 쓰는 공개 JSON에서 제목과 첫 이미지를 가져온다."""
    import re

    m = re.match(r"https?://(?:m\.)?comic\.naver\.com/notice/detail\?.*noticeId=(\d+)", url)
    if not m:
        return None
    r = httpx.get(f"https://comic.naver.com/api/notice/detail?noticeId={m.group(1)}", timeout=12,
                  headers={"User-Agent": config.settings()["user_agent"], "Referer": url})
    r.raise_for_status()
    notice = r.json().get("notice") or {}
    img = re.search(r'src="(https://[^"]+)"', notice.get("content") or "")
    return {"title": notice.get("subject") or "", "image": img.group(1) if img else "", "description": ""}


def _usable(meta: dict) -> dict:
    """사이트 이름뿐인 제목('네이버웹툰', '월간 미대입시')과 로고 이미지는 자동 채움에 쓰지 않는다."""
    title = (meta.get("title") or "").strip()
    if len(title.replace(" ", "")) <= 8:
        title = ""
    image = meta.get("image") or ""
    if re.search(r"logo|favicon", image, re.I):
        image = ""
    return {"title": title, "image": image, "description": meta.get("description") or ""}


def fetch_meta(url: str) -> dict:
    """공고 링크를 열어 제목·대표 이미지·설명을 가져온다 (og:title, og:image, <title>). 쓸 수 없는 값은 비운다."""
    from bs4 import BeautifulSoup

    from .http import ssl_context

    special = _naver_webtoon_notice(url)
    if special is not None:
        return _usable(special)
    r = httpx.get(url, timeout=12, follow_redirects=True, verify=ssl_context(),
                  headers={"User-Agent": config.settings()["user_agent"], "Accept-Language": "ko-KR,ko;q=0.9"})
    r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser")

    def meta(*names):
        for n in names:
            tag = s.find("meta", attrs={"property": n}) or s.find("meta", attrs={"name": n})
            if tag and (tag.get("content") or "").strip():
                return tag["content"].strip()
        return ""

    title = meta("og:title", "twitter:title") or (s.title.get_text(strip=True) if s.title else "")
    image = meta("og:image", "twitter:image")
    if image:
        image = str(httpx.URL(str(r.url)).join(image))
    return _usable({"title": title, "image": image if image.startswith("https://") else "",
                    "description": meta("og:description", "description")})


def load_manual(data: SheetData, path: Path = MANUAL_PATH, decisions_path: Path = DECISIONS_PATH,
                fetch: bool = True) -> dict[str, dict]:
    """직접 등록 공모전 → 승인 없이 공개 (출처 'manual').

    제목·포스터가 비어 있으면 공고 링크에서 자동으로 가져온다 (마감 전인 것만). 마감일은 꼭 사람이 넣는다.
    돌려주는 값: 등록 key → {id, title, poster_url, auto, error} (관리자 페이지 목록 표시용)
    """
    rows, origin = manual_rows(path, decisions_path)
    if origin == "file-error":
        data.warnings.append("직접 등록 파일(config/manual_contests.json)을 읽지 못함")
    info: dict[str, dict] = {}
    today = date.today().isoformat()
    for n, row in enumerate(rows, start=1):
        key = row.get("key") or f"m{n}"
        url = clean_url(row.get("url") or row.get("official_url"))
        end = parse_date(row.get("end_date") or "")
        title = (row.get("title") or "").strip()
        poster = row.get("poster_url") if str(row.get("poster_url", "")).startswith("https://") else None
        summary = row.get("summary") or ""
        where = f"직접 등록 '{title or url or key}'"
        auto, error = False, ""
        if not end:
            data.warnings.append(f"{where}: 마감일(YYYY-MM-DD)이 없어 건너뜀")
            info[key] = {"id": "", "title": title, "error": "마감일 없음"}
            continue
        if fetch and url and (not title or not poster) and end.isoformat() >= today:
            try:
                m = fetch_meta(url)
                if not title and m["title"]:
                    title, auto = m["title"], True
                poster = poster or m["image"] or None
                summary = summary or m["description"][:200]
            except Exception as e:
                error = f"링크에서 정보를 가져오지 못함 ({type(e).__name__})"
        if not title:
            data.warnings.append(f"{where}: 제목이 없고 링크에서도 가져오지 못해 건너뜀 — 제목을 직접 입력하세요")
            info[key] = {"id": "", "title": "", "error": error or "제목 없음"}
            continue
        start = parse_date(row.get("start_date") or "")
        start_s = start.isoformat() if start else None
        c = Contest(
            id=make_id(title, start_s, end.isoformat()),
            title=title,
            categories=[x for x in row.get("categories", []) if x in CATEGORIES],
            subcategories=[x for x in row.get("subcategories", []) if x in SUBCATEGORIES],
            targets=[x for x in row.get("targets", []) if x in TARGET_LABELS],
            official_url=url,
            apply_url=clean_url(row.get("apply_url")),
            poster_url=poster,
            prize_max_krw=parse_prize(row.get("prize_text")),
            start_date=start_s,
            end_date=end.isoformat(),
            sources=[{"site": "manual", "url": url}],
        )
        for f in _MANUAL_FIELDS:
            if row.get(f):
                setattr(c, f, row[f])
        if summary:
            c.summary = summary
        c.student_eligible = "yes" if c.targets else "unknown"
        data.additions.append(c)
        info[key] = {"id": c.id, "title": title, "poster_url": poster or "", "auto": auto, "error": error}
    data.manual_info = info
    return info


def load_decisions(data: SheetData, path: Path = DECISIONS_PATH) -> dict:
    """관리자 페이지에서 내린 결정을 반영한다. 시트보다 나중에 적용되므로 시트와 겹치면 이쪽이 우선."""
    if not path.exists():
        return {}
    try:
        decisions = json.loads(path.read_text(encoding="utf-8") or "{}")
    except ValueError as e:
        data.warnings.append(f"관리자 결정 파일(data/decisions.json)을 읽지 못함: {e}")
        return {}
    for cid, d in decisions.items():
        if cid.startswith("_"):  # '_staff' 등 관리자 설정
            continue
        action = d.get("action") if isinstance(d, dict) else None
        if action in ("approve", "hide"):
            data.approvals[cid] = DECISION_ACTIONS[action]
        elif action == "confirm":
            data.confirmed.add(cid)
    return decisions


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
        approval = row.get("승인", "")
        if approval in ("승인", "거절"):
            data.approvals[cid] = approval
        elif approval:
            data.warnings.append(f"{where}: 승인 칸에는 '승인' 또는 '거절'만 적을 수 있음 ('{approval}')")
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
          "exclude_title": [], "universities": [], "univ_subjects": [], "competitors": []}
    for n, row in enumerate(rows, start=2):
        kind, name, words = row.get("종류", ""), row.get("이름", ""), _split(row.get("키워드", ""))
        if kind == "구분" and name in kw["categories"]:
            kw["categories"][name] += words
        elif kind == "장르" and name in kw["subcategories"]:
            kw["subcategories"][name] += words
        elif kind == "제외":
            kw["exclude_title"] += words
        elif kind == "대학":
            kw["universities"] += words
        elif kind == "대학과목":
            kw["univ_subjects"] += words
        elif kind == "경쟁사":
            kw["competitors"] += words
        elif kind or name:
            data.warnings.append(f"키워드 탭 {n}행: 종류 '{kind}' / 이름 '{name}'을 알 수 없음")
    # 시트에 대학 목록이 없으면(예전 양식) 기본값을 쓴다
    for key in ("universities", "univ_subjects", "competitors"):
        kw[key] = kw[key] or list(base.get(key, []))
    # 시트에 구분 키워드가 없으면 분류 키워드는 기본값을 쓴다 (빈 시트로 분류가 멈추지 않도록).
    # 이때도 시트의 대학·경쟁사 목록은 반영한다.
    if any(kw["categories"].values()):
        data.keywords = kw
    elif kw["competitors"] != list(base.get("competitors", [])) or kw["universities"] != list(base.get("universities", [])):
        merged = dict(base)
        for key in ("universities", "univ_subjects", "competitors"):
            merged[key] = kw[key]
        data.keywords = merged


def load_sheet(fetch_manual: bool = False) -> SheetData:
    """시트·직접 등록·관리자 결정을 읽는다. fetch_manual=True면 직접 등록 공모전의 빈 제목·포스터를 링크에서 채운다 (사이트 생성 때)."""
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
    load_manual(data, fetch=fetch_manual)
    load_decisions(data)
    for w in data.warnings:
        log.warning(w)
    return data


def split_pending(contests: dict[str, Contest], data: SheetData) -> tuple[dict[str, Contest], dict[str, Contest]]:
    """공모전을 (공개, 대기)로 나눈다. '거절'(숨김)은 어느 쪽에도 넣지 않는다.

    대기 = 관리자가 공개하기 전까지 사이트에 올리지 않는 공모전 (2026-10-28부터 두 종류 모두 비공개):
    - 경쟁사 관련: 수집할 때 본문에서 찾은 이름 + 지금 목록으로 제목·주최·대상·시상·소개를 다시 확인 → '승인'해야 공개
    - 확인 필요: 자동 분류가 애매하거나 학원·아카데미 관련 → '공개'(확인)해야 공개
    시트 '직접등록'으로 관리자가 넣은 건은 바로 공개한다.
    """
    from .classify import competitor_hits

    public, pending = {}, {}
    for cid, c in contests.items():
        hits = list(dict.fromkeys(c.competitor_hits + competitor_hits(
            c.title, c.organizer, c.target_text, c.prize_text, c.summary)))
        c.competitor_hits = hits
        from_sheet = any(s.get("site") in ("sheet", "manual") for s in c.sources)  # 관리자가 직접 등록한 건
        decision = data.approvals.get(cid)
        if decision == "거절":
            continue
        if from_sheet or decision == "승인":
            public[cid] = c
        elif hits or c.needs_review:  # '확인'을 누른 건은 apply()에서 needs_review가 지워져 여기로 오지 않는다
            pending[cid] = c
        else:
            public[cid] = c
    return public, pending


def apply_school_rules(contests: dict[str, Contest], keep_categories: set[str] = frozenset()) -> None:
    """이미 수집된 공모전에도 대학·학원 규칙을 적용한다 (사이트 생성 때마다, 원본 데이터는 그대로).

    - 제목·주최에 대학교·전문학교 이름이 있고 제목에 과목 단어(웹툰·만화·게임·애니 …)가 있으면 → 구분 '대학' 추가
    - 제목·주최에 학원·아카데미가 있으면 → '확인 필요' (대학 탭에는 넣지 않음, 관리자 '확인'으로 지움)
    """
    from .classify import ACADEMY_REASON, _hits, has_university, is_academy

    subjects = config.keywords().get("univ_subjects", [])
    for cid, c in contests.items():
        if (cid not in keep_categories and c.categories and "대학" not in c.categories
                and has_university(c.title, c.organizer) and _hits(c.title.lower(), subjects)):
            c.categories.append("대학")
        admin_entered = any(s.get("site") in ("sheet", "manual") for s in c.sources)
        if not admin_entered and is_academy(c.title, c.organizer) and ACADEMY_REASON not in c.review_reasons:
            c.review_reasons.append(ACADEMY_REASON)
            c.needs_review = True


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
    # 시트에서 구분을 직접 고친 건은 사람이 정한 값을 그대로 둔다
    apply_school_rules(out, keep_categories={cid for cid, e in data.edits.items() if "categories" in e})
    for cid in data.confirmed:
        c = out.get(cid)
        if c is not None:
            # 관리자가 '확인'을 누른 건: 분류가 맞다고 보고 경고를 지운다
            c.review_reasons = []
            c.needs_review = False
    for cid in hidden:
        out.pop(cid, None)
    return out, warnings
