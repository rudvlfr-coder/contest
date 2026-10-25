"""정적 사이트 생성 (작업지시서 F-06, F-07). 결과는 site/dist/ — GitHub Pages에 그대로 올린다."""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from . import config, overrides, store
from .models import TARGET_LABELS, Contest

ASSETS = config.ROOT / "site" / "assets"
DIST = config.ROOT / "site" / "dist"
WEEK = "월화수목금토일"
PUBLIC_FIELDS = ("id", "title", "organizer", "categories", "subcategories", "start_date", "end_date",
                 "prize_max_krw", "prize_text", "targets", "student_eligible", "region", "needs_review", "created_at")
SUB_OPTIONS = [("prog", "프로그래밍"), ("art", "원화"), ("plan", "기획"), ("bgm", "BGM"), ("gfx", "그래픽"),
               ("ai", "AI"), ("comp", "대회"), ("univ", "대학"), ("job", "채용"), ("etc", "기타")]
SUB_CODE = {name: code for code, name in SUB_OPTIONS}


# ---------------------------------------------------------------- 사이트 이름

def last_updated(log_path: Path = config.ROOT / "data" / "crawl_log.json") -> datetime:
    """마지막으로 수집에 성공한 시각. 실패한 실행은 날짜를 바꾸지 않는다 (작업지시서 F-06)."""
    if log_path.exists():
        runs = json.loads(log_path.read_text(encoding="utf-8"))
        ok = [r["finished_at"] for r in runs if r.get("listed", 0) > 0 and r.get("finished_at")]
        if ok:
            return datetime.fromisoformat(max(ok))
    return datetime.now()


def site_name(when: datetime | date) -> str:
    return f"{when.month}.{when.day:02d} 공모전"


# ---------------------------------------------------------------- 표시용 문구

def fmt_day(iso: str | None) -> str:
    if not iso:
        return "미정"
    d = date.fromisoformat(iso)
    return f"{d.year}.{d.month}.{d.day}({WEEK[d.weekday()]})"


def fmt_short(iso: str | None) -> str:
    if not iso:
        return "미정"
    d = date.fromisoformat(iso)
    return f"{d.month}/{d.day}({WEEK[d.weekday()]})"


def fmt_won(n: int | None) -> str:
    if not n:
        return ""
    eok, man = divmod(n, 100_000_000)
    man = round(man / 10_000)
    parts = ([f"{eok}억"] if eok else []) + ([f"{man:,}만"] if man else [])
    return (" ".join(parts) or f"{n:,}") + " 원"


def prize_line(c: Contest) -> str:
    if c.prize_max_krw:
        return f"최대 {fmt_won(c.prize_max_krw)}"
    return (c.prize_text or "")[:60]


def target_line(c: Contest) -> str:
    labels = [TARGET_LABELS[t] for t in c.targets if t in TARGET_LABELS]
    return ", ".join(labels) if labels else "자격 확인 필요"


def json_script(element_id: str, data) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="{element_id}">{payload}</script>'


# ---------------------------------------------------------------- 공통 틀

def page(*, title: str, body: str, prefix: str, name: str, updated: datetime, description: str = "",
         og_url: str = "", noindex: bool = False, scripts: str = "") -> str:
    s = config.settings()
    contact = s.get("contact_email") or ""
    og = [f'<meta property="og:type" content="website">',
          f'<meta property="og:title" content="{escape(title)}">',
          f'<meta property="og:site_name" content="{escape(name)}">']
    if description:
        og.append(f'<meta property="og:description" content="{escape(description)}">')
        og.append(f'<meta name="description" content="{escape(description)}">')
    if og_url:
        og.append(f'<meta property="og:url" content="{escape(og_url)}">')
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    contact_html = (f' · 정보 수정·삭제 요청: <a href="mailto:{escape(contact)}">{escape(contact)}</a>'
                    if contact else "")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
{chr(10).join(og)}
{robots}
<link rel="stylesheet" href="{prefix}assets/site.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%233b5bdb'/%3E%3Ctext x='32' y='44' font-size='34' text-anchor='middle' fill='white' font-family='sans-serif' font-weight='700'%3E공%3C/text%3E%3C/svg%3E">
</head>
<body>
{body}
<footer><div class="wrap">공모전 정보는 각 출처에서 자동으로 모은 것입니다. 지원 전에 반드시 공식 공고를 확인하세요.
마지막 수집 {updated:%Y-%m-%d %H:%M}{contact_html}</div></footer>
{scripts}
<script src="{prefix}assets/site.js"></script>
</body>
</html>
"""


def header(prefix: str, name: str, updated: datetime, extra: str = "") -> str:
    return f"""<header class="top"><div class="wrap">
<div class="title-row"><p class="site-name"><a href="{prefix}">{escape(name)}</a></p>
<span class="updated">{updated:%m.%d %H:%M} 기준</span></div>
{extra}
</div></header>"""


# ---------------------------------------------------------------- 목록

def render_index(contests: list[Contest], name: str, updated: datetime) -> str:
    cats = "".join(f'<button class="chip" type="button" data-cat="{v}">{label}</button>'
                   for v, label in (("", "전체"), ("웹툰", "웹툰"), ("웹소설", "웹소설"), ("게임", "게임")))
    genres = "".join(f'<option value="{n}">{n}</option>' for _, n in SUB_OPTIONS)
    targets = "".join(f'<option value="{k}">{v}</option>' for k, v in TARGET_LABELS.items())
    controls = f"""<div class="search">
<input id="q" type="search" placeholder="공모전 이름, 주최 검색" aria-label="검색">
<button class="btn" id="toggle" type="button" aria-expanded="false" aria-controls="panel">필터</button>
</div>
<div class="chips" role="group" aria-label="구분">{cats}</div>
<div class="panel" id="panel">
<label>장르<select id="f-genre"><option value="">전체</option>{genres}</select></label>
<label>참가 대상<select id="f-target"><option value="">전체</option>{targets}</select></label>
<label>마감<select id="f-due"><option value="">전체</option><option value="7">7일 이내</option><option value="30">30일 이내</option></select></label>
<label>국내/해외<select id="f-region"><option value="">전체</option><option value="domestic">국내</option><option value="overseas">해외</option></select></label>
<label>정렬<select id="f-sort"><option value="due">마감 임박순</option><option value="new">최근 등록순</option><option value="prize">상금 많은순</option></select></label>
<label class="check"><input type="checkbox" id="f-prize"> 상금 있는 것만</label>
<button class="btn small" id="reset" type="button">필터 초기화</button>
</div>"""
    body = header("", name, updated, controls) + """
<main class="wrap">
<div class="bar"><span class="count" id="count" aria-live="polite"></span>
<div class="actions">
<button class="btn small" id="copy-link" type="button">필터 링크 복사</button>
<button class="btn small" id="copy-list" type="button">목록 공유 문구</button>
<button class="btn small" id="past" type="button" aria-pressed="false">지난 공모전</button>
</div></div>
<ul class="list" id="list"></ul>
</main>"""
    data = [{k: getattr(c, k) for k in PUBLIC_FIELDS} for c in contests]
    open_count = sum(1 for c in contests if c.status(updated.date()) != "마감")
    return page(title=name, body=body, prefix="", name=name, updated=updated,
                description=f"웹툰·웹소설·게임 분야 학생 공모전 {open_count}건 (마감 임박순)",
                og_url=config.settings().get("site_url", ""), scripts=json_script("data", data))


# ---------------------------------------------------------------- 상세

def render_detail(c: Contest, name: str, updated: datetime) -> str:
    prefix = "../../"
    tags = "".join(f'<span class="tag cat-{escape(x)}">{escape(x)}</span>' for x in c.categories)
    tags += "".join(f'<span class="tag">{escape(x)}</span>' for x in c.subcategories)
    if c.region == "overseas":
        tags += '<span class="tag">해외</span>'
    if c.needs_review:
        tags += f'<span class="tag review" title="{escape(", ".join(c.review_reasons))}">확인 필요</span>'

    rows = [("접수 기간", f"{fmt_day(c.start_date)} ~ {fmt_day(c.end_date)}" if c.start_date else f"~ {fmt_day(c.end_date)}")]
    if c.organizer:
        rows.append(("주최", escape(c.organizer)))
    target = escape(target_line(c))
    if c.target_text:
        target += f'<div class="note">{escape(c.target_text[:200])}</div>'
    rows.append(("참가 대상", target))
    if c.prize_text or c.prize_max_krw:
        prize = escape(prize_line(c))
        if c.prize_text and c.prize_max_krw:
            prize += f'<div class="note">{escape(c.prize_text[:200])}</div>'
        rows.append(("시상", prize))
    if c.summary:
        rows.append(("소개", escape(c.summary)))
    facts = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)

    links = []
    if c.official_url:
        links.append(f'<a class="btn primary" href="{escape(c.official_url)}" target="_blank" rel="noopener">공식 공고 보기</a>')
    if c.apply_url and c.apply_url != c.official_url:
        links.append(f'<a class="btn" href="{escape(c.apply_url)}" target="_blank" rel="noopener">접수 페이지</a>')
    links.append('<button class="btn" type="button" data-copy="share">공유 문구 복사</button>')
    links.append('<button class="btn" type="button" data-copy="link">링크 복사</button>')
    if c.end_date:
        links.append('<a class="btn" href="event.ics" download>캘린더에 마감일 추가</a>')

    site_names = {"notion": "기존 노션 목록", "wevity": "위비티", "contestkorea": "콘테스트코리아", "itchio": "itch.io"}
    sources = "".join(
        f'<li>{escape(site_names.get(s["site"], s["site"]))}'
        + (f' — <a href="{escape(s["url"])}" target="_blank" rel="noopener">원문</a>' if s.get("url") else "") + "</li>"
        for s in c.sources)

    body = header(prefix, name, updated) + f"""
<main class="wrap detail">
<div class="tags">{tags}</div>
<div class="card-head"><h1>{escape(c.title)}</h1><span class="dday" data-dday>{escape(fmt_short(c.end_date))}</span></div>
<div class="cta">{"".join(links)}</div>
<section class="box"><dl class="facts">{facts}</dl></section>
<section class="box"><p class="note" style="margin:0 0 6px">출처</p><ul class="sources">{sources}</ul>
<p class="note" style="margin:10px 0 0">공모전 ID <code>{escape(c.id)}</code>
<button class="btn small" type="button" data-copy="id">ID 복사</button> — 정보가 틀렸다면 운영자에게 이 ID를 알려 주세요.</p></section>
<p><a class="btn" href="{prefix}">← 전체 목록</a></p>
</main>"""
    description = f"마감 {fmt_short(c.end_date)} · 대상 {target_line(c)}"
    if prize_line(c):
        description += f" · 상금 {prize_line(c)}"
    base = config.settings().get("site_url", "").rstrip("/")
    detail_data = {k: getattr(c, k) for k in PUBLIC_FIELDS}
    return page(title=f"{c.title} | {name}", body=body, prefix=prefix, name=name, updated=updated,
                description=description, og_url=f"{base}/c/{c.id}/" if base else "",
                scripts=json_script("contest", detail_data))


def _ics_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def render_ics(c: Contest, page_url: str) -> str:
    d = date.fromisoformat(c.end_date)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ContestHub//KO", "CALSCALE:GREGORIAN",
             "BEGIN:VEVENT", f"UID:{c.id}@contesthub", f"DTSTAMP:{stamp}",
             f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
             f"SUMMARY:{_ics_text('[마감] ' + c.title)}",
             f"DESCRIPTION:{_ics_text((c.official_url or '') + chr(10) + page_url)}",
             "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------- 운영자용 확인 페이지

def render_review(contests: list[Contest], name: str, updated: datetime, warnings: list[str] | None = None) -> str:
    warn_html = ""
    if warnings:
        items = "".join(f"<li>{escape(w)}</li>" for w in warnings)
        warn_html = f'<section class="box"><p class="note" style="margin:0 0 6px">구글 시트에서 반영하지 못한 내용</p><ul class="sources">{items}</ul></section>'
    rows = "".join(
        f'<tr><td><code>{escape(c.id)}</code></td><td><a href="../c/{escape(c.id)}/">{escape(c.title)}</a></td>'
        f'<td>{escape(", ".join(c.categories))} / {escape(", ".join(c.subcategories))}</td>'
        f'<td>{escape(fmt_short(c.end_date))}</td><td>{escape(", ".join(c.review_reasons))}</td></tr>'
        for c in contests if c.needs_review and c.status(updated.date()) != "마감")
    body = header("../", name, updated) + f"""
<main class="wrap detail"><h1>확인 필요 목록</h1>
<p class="note">자동 분류가 애매하거나 정보가 빠진 진행 중 공모전입니다. 고칠 내용은 구글 시트 '수정' 탭에 공모전 ID와 함께 적어 주세요.</p>
{warn_html}
<div style="overflow-x:auto"><table class="review"><thead><tr><th>ID</th><th>제목</th><th>구분 / 장르</th><th>마감</th><th>사유</th></tr></thead>
<tbody>{rows or '<tr><td colspan="5">없음</td></tr>'}</tbody></table></div></main>"""
    return page(title=f"확인 필요 | {name}", body=body, prefix="../", name=name, updated=updated, noindex=True)


# ---------------------------------------------------------------- 빌드

def build(out: Path = DIST) -> dict:
    # 구글 시트의 숨김·수정·직접등록을 반영 (원본 data/contests.json은 바꾸지 않는다)
    applied, warnings = overrides.apply(store.load(), overrides.load_sheet())
    contests = list(applied.values())
    updated = last_updated()
    name = site_name(updated)
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    for f in ASSETS.iterdir():
        shutil.copy2(f, out / "assets" / f.name)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    (out / "index.html").write_text(render_index(contests, name, updated), encoding="utf-8")
    base = config.settings().get("site_url", "").rstrip("/")
    for c in contests:
        d = out / "c" / c.id
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(render_detail(c, name, updated), encoding="utf-8")
        if c.end_date:
            (d / "event.ics").write_text(render_ics(c, f"{base}/c/{c.id}/" if base else ""), encoding="utf-8", newline="")
    (out / "review").mkdir()
    (out / "review" / "index.html").write_text(render_review(contests, name, updated, warnings), encoding="utf-8")
    return {"name": name, "contests": len(contests), "out": str(out), "warnings": warnings}
