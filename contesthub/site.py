"""정적 사이트 생성 (작업지시서 F-06, F-07). 결과는 site/dist/ — GitHub Pages에 그대로 올린다."""
from __future__ import annotations

import json
import re
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
               ("ai", "AI"), ("comp", "대회"), ("job", "채용"), ("etc", "기타")]
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

_PUBLIC_STAFF: dict = {}  # build()에서 채움: {"default": {...}, "staff": {코드: {...}}}

CONTACT_BAR = """<div class="contactbar" data-contact hidden>
<span class="who" data-contact-name hidden></span>
<a class="btn" data-contact-link="portfolio" href="#" target="_blank" rel="noopener">무료 포트폴리오 상담</a>
<a class="btn primary" data-contact-link="contest" href="#" target="_blank" rel="noopener">공모전 준비 문의</a>
</div>"""


def public_staff(staff_cfg: dict | None) -> dict:
    """관리자 페이지에서 저장한 직원 목록(decisions.json의 _staff) → 페이지에 넣을 공개 정보. http(s) 주소만 통과."""
    def url(u):
        return u if isinstance(u, str) and u.startswith(("http://", "https://")) else ""

    staff_cfg = staff_cfg or {}
    d = staff_cfg.get("default") or {}
    out = {"default": {"name": d.get("name", ""), "form": url(d.get("form")), "contest_form": url(d.get("contest_form"))},
           "staff": {}}
    for s in staff_cfg.get("staff") or []:
        code = re.sub(r"[^a-z0-9_-]", "", str(s.get("code", "")).lower())
        if code and url(s.get("form")):
            out["staff"][code] = {"name": s.get("name", ""), "form": url(s.get("form")),
                                  "contest_form": url(s.get("contest_form"))}
    return out


def page(*, title: str, body: str, prefix: str, name: str, updated: datetime, description: str = "",
         og_url: str = "", noindex: bool = False, scripts: str = "", contact: bool = True,
         body_class: str = "") -> str:
    if contact:
        body += "\n" + CONTACT_BAR
        scripts = json_script("staff", _PUBLIC_STAFF) + "\n" + scripts
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
<body class="{body_class}">
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
                   for v, label in (("", "전체"), ("웹툰", "웹툰"), ("웹소설", "웹소설"), ("게임", "게임"), ("대학", "대학")))
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
<div class="split">
<section class="list-col">
<div class="bar"><span class="count" id="count" aria-live="polite"></span>
<div class="actions">
<button class="btn small" id="copy-link" type="button">필터 링크 복사</button>
<button class="btn small" id="copy-list" type="button">목록 공유 문구</button>
<button class="btn small" id="past" type="button" aria-pressed="false">지난 공모전</button>
</div></div>
<ul class="list" id="list"></ul>
</section>
<aside class="detail-pane" id="detail-pane" aria-live="polite" aria-label="선택한 공모전"></aside>
</div>
</main>"""
    # PC 화면 오른쪽 상세 영역을 그리는 데 필요한 항목까지 함께 넣는다
    fields = PUBLIC_FIELDS + ("official_url", "apply_url", "target_text", "summary", "sources")
    data = [{k: getattr(c, k) for k in fields} for c in contests]
    open_count = sum(1 for c in contests if c.status(updated.date()) != "마감")
    return page(title=name, body=body, prefix="", name=name, updated=updated, body_class="index",
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


# ---------------------------------------------------------------- 관리자 페이지

SITE_NAMES = {"notion": "노션", "wevity": "위비티", "contestkorea": "콘테스트코리아", "mgood": "엠굿",
              "itchio": "itch.io", "sheet": "직접등록"}


def _id_cell(c: Contest) -> str:
    return (f'<code>{escape(c.id)}</code> <button class="btn small" type="button" '
            f'data-copy-text="{escape(c.id)}">복사</button>')


def _source_links(c: Contest) -> str:
    links = [f'<a href="{escape(s["url"])}" target="_blank" rel="noopener">{escape(SITE_NAMES.get(s["site"], s["site"]))}</a>'
             for s in c.sources if s.get("url")]
    if c.official_url and all(s.get("url") != c.official_url for s in c.sources):
        links.append(f'<a href="{escape(c.official_url)}" target="_blank" rel="noopener">공식</a>')
    return " · ".join(links) or "-"


def _table(head: list[str], rows: list[str], empty: str) -> str:
    th = "".join(f"<th>{h}</th>" for h in head)
    body = "".join(rows) or f'<tr><td colspan="{len(head)}">{empty}</td></tr>'
    return f'<div style="overflow-x:auto"><table class="review"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _buttons(cid: str, actions: list[tuple[str, str, str]]) -> str:
    return "".join(f'<button class="btn small {cls}" type="button" data-act="{act}" data-id="{escape(cid)}">{label}</button>'
                   for act, label, cls in actions)


ACTION_LABELS = {"approve": "승인함", "hide": "숨김", "confirm": "확인함"}


def render_admin(public: list[Contest], pending: list[Contest], name: str, updated: datetime,
                 warnings: list[str] | None = None, runs: list[dict] | None = None,
                 decisions: dict | None = None, titles: dict[str, str] | None = None) -> str:
    today = updated.date()
    decisions = decisions or {}
    titles = titles or {}
    pending_open = sorted((c for c in pending if c.status(today) != "마감"), key=lambda c: c.end_date or "9999")
    pending_rows = [
        f'<tr data-row="{escape(c.id)}"><td>{escape(c.title)}<div class="note">{escape(c.organizer or "")} · 마감 {escape(fmt_short(c.end_date))}'
        f' · <code>{escape(c.id)}</code></div></td>'
        f'<td><span class="tag review">{escape(", ".join(c.competitor_hits))}</span></td>'
        f'<td>{_source_links(c)}</td>'
        f'<td class="acts">{_buttons(c.id, [("approve", "승인", "primary"), ("hide", "숨김", "")])}</td></tr>'
        for c in pending_open]
    review_rows = [
        f'<tr data-row="{escape(c.id)}"><td><a href="../c/{escape(c.id)}/" target="_blank">{escape(c.title)}</a>'
        f'<div class="note">{escape(c.organizer or "")} · 마감 {escape(fmt_short(c.end_date))} · <code>{escape(c.id)}</code></div></td>'
        f'<td>{escape(", ".join(c.categories))}{" / " + escape(", ".join(c.subcategories)) if c.subcategories else ""}'
        f'<div class="note">{escape(", ".join(c.review_reasons))}</div></td>'
        f'<td>{_source_links(c)}</td>'
        f'<td class="acts">{_buttons(c.id, [("confirm", "확인", "primary"), ("hide", "숨김", "")])}</td></tr>'
        for c in sorted(public, key=lambda c: c.end_date or "9999") if c.needs_review and c.status(today) != "마감"]
    done_rows = [
        f'<tr data-row="{escape(cid)}"><td>{escape(titles.get(cid, cid))}<div class="note"><code>{escape(cid)}</code></div></td>'
        f'<td>{ACTION_LABELS.get(d.get("action"), d.get("action"))}</td><td>{escape((d.get("at") or "")[:16].replace("T", " "))}</td>'
        f'<td class="acts">{_buttons(cid, [("undo", "되돌리기", "")])}</td></tr>'
        for cid, d in sorted(((k, v) for k, v in decisions.items() if not k.startswith("_") and isinstance(v, dict)),
                             key=lambda kv: kv[1].get("at", ""), reverse=True)[:50]]

    latest: dict[str, dict] = {}
    for r in runs or []:
        latest[r["site"]] = r
    run_rows = [
        f'<tr><td>{escape(SITE_NAMES.get(s, s))}</td><td>{escape((r.get("finished_at") or "")[:16].replace("T", " "))}</td>'
        f'<td>{r.get("listed", 0)}</td><td>{r.get("new", 0)}</td><td>{len(r.get("errors", []))}'
        + (' <span class="tag review">확인 필요</span>' if r.get("listed", 0) == 0 else "") + "</td></tr>"
        for s, r in latest.items()]

    warn_html = ""
    if warnings:
        items = "".join(f"<li>{escape(w)}</li>" for w in warnings)
        warn_html = f'<section class="box"><h2 style="margin:0 0 6px;font-size:16px">구글 시트에서 반영하지 못한 내용</h2><ul class="sources">{items}</ul></section>'

    admin_cfg = {"repo": config.settings().get("github_repo", ""), "path": "data/decisions.json", "branch": "main",
                 "staff": decisions.get("_staff") or {"default": {}, "staff": []}}
    body = header("../", name, updated) + f"""
<main class="wrap detail admin"><h1>관리자</h1>
<p class="note">이 페이지는 검색에 노출되지 않지만 주소를 아는 사람은 볼 수 있습니다. 버튼으로 내린 결정은
<b>GitHub 토큰을 연결한 기기에서만</b> 저장됩니다.</p>
<section class="box" id="token-box">
<div id="token-off"><b>처음 한 번: GitHub 토큰 연결</b>
<p class="note">GitHub → 오른쪽 위 프로필 → Settings → Developer settings → Personal access tokens → <b>Fine-grained tokens</b> →
Generate new token → Repository access: <b>Only select repositories</b>에서 이 저장소 선택 → Permissions의 Repository permissions에서
<b>Contents: Read and write</b> → Generate token → 나온 값을 복사해 아래에 붙여넣기.</p>
<div class="search"><input id="token-input" type="password" placeholder="github_pat_로 시작하는 토큰" autocomplete="off">
<button class="btn primary" id="token-save" type="button">연결</button></div></div>
<div id="token-on" hidden>✅ 이 기기는 GitHub에 연결되어 있습니다. <button class="btn small" id="token-clear" type="button">연결 해제</button></div>
</section>
{warn_html}
<section class="box"><h2>승인 대기 {len(pending_open)}건 — 경쟁사 관련</h2>
<p class="note">사이트에 아직 올라가지 않은 공모전입니다. 출처를 확인하고 <b>승인</b>(사이트에 발행) 또는 <b>숨김</b>(계속 비공개)을 누르세요.
아무것도 누르지 않으면 보류 상태로 남습니다. 마감이 지나면 이 목록에서 자동으로 사라집니다.</p>
{_table(["제목", "걸린 이름", "출처", "처리"], pending_rows, "승인 대기 중인 공모전이 없습니다.")}</section>
<section class="box"><h2>확인 필요 {len(review_rows)}건 — 자동 분류가 애매함</h2>
<p class="note">사이트에는 '확인 필요' 표시와 함께 올라가 있습니다. 맞으면 <b>확인</b>(표시 지움), 맞지 않으면 <b>숨김</b>(사이트에서 내림).</p>
{_table(["제목", "구분 / 사유", "출처", "처리"], review_rows, "없음")}</section>
<section class="box" id="staff-box"><h2>직원 관리 — 직원별 문의 링크</h2>
<p class="note">직원마다 코드(영어 소문자·숫자)와 네이버 폼 주소를 넣으면, 그 직원의 공유 링크로 들어온 학생에게
<b>무료 포트폴리오 상담</b>·<b>공모전 준비 문의</b> 버튼이 그 직원의 폼으로 연결되고 "담당 ○○○"이 표시됩니다.
학생이 친구에게 공유한 링크에도 담당 직원이 따라갑니다. 담당 직원은 학생이 지금 연 링크의 코드로 정해집니다(다른 직원 링크를 열면 그 직원으로 바뀜).
'공모전 문의 폼'을 비워 두면 두 버튼 모두 첫 번째 폼으로 연결됩니다. 저장 후 1~2분 뒤부터 링크가 동작합니다.</p>
<div style="overflow-x:auto"><table class="review staff-table"><thead><tr><th>이름</th><th>코드</th><th>포트폴리오 상담 폼</th><th>공모전 문의 폼 (선택)</th><th>링크</th></tr></thead>
<tbody id="staff-rows"></tbody></table></div>
<p><button class="btn small" id="staff-add" type="button">+ 직원 추가</button></p>
<p class="note" style="margin-bottom:4px">담당 코드 없이 들어온 학생(대표 문의) — 비워 두면 코드 없는 방문자에게는 버튼이 보이지 않습니다.</p>
<div style="overflow-x:auto"><table class="review staff-table"><tbody><tr>
<td><input data-default="name" placeholder="표시 이름 (예: 상담실)"></td>
<td><input data-default="form" placeholder="https://naver.me/... 포트폴리오 상담 폼"></td>
<td><input data-default="contest_form" placeholder="https://naver.me/... 공모전 문의 폼 (선택)"></td></tr></tbody></table></div>
</section>
<div class="qr-modal" id="qr-modal" hidden><div class="box"><p id="qr-title" style="margin:0 0 8px;font-weight:700"></p>
<div id="qr-code"></div><p class="note" id="qr-url" style="word-break:break-all"></p>
<p><a class="btn small" id="qr-download" download="qr.png">QR 이미지 저장</a> <button class="btn small" id="qr-close" type="button">닫기</button></p></div></div>
<section class="box"><h2>처리 내역</h2>
<p class="note">잘못 눌렀다면 <b>되돌리기</b>를 누르세요.</p>
{_table(["제목", "처리", "시각", ""], done_rows, "아직 처리한 공모전이 없습니다.")}</section>
<section class="box"><h2>최근 수집</h2>
{_table(["사이트", "시각", "목록", "신규", "오류"], run_rows, "수집 기록이 없습니다.")}</section>
</main>
<div class="savebar" id="savebar" hidden><span id="save-count"></span>
<button class="btn" id="save-cancel" type="button">취소</button>
<button class="btn primary" id="save-go" type="button">반영하기</button></div>"""
    return page(title=f"관리자 | {name}", body=body, prefix="../", name=name, updated=updated, noindex=True,
                contact=False,
                scripts=json_script("admin-config", admin_cfg)
                + '\n<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js" defer></script>'
                + '\n<script src="../assets/admin.js" defer></script>')


# ---------------------------------------------------------------- 빌드

def build(out: Path = DIST) -> dict:
    # 구글 시트의 숨김·수정·직접등록·승인을 반영 (원본 data/contests.json은 바꾸지 않는다)
    sheet = overrides.load_sheet()
    config.override_keywords(sheet.keywords)
    raw = store.load()
    applied, warnings = overrides.apply(raw, sheet)
    public, pending = overrides.split_pending(applied, sheet)
    contests = list(public.values())
    updated = last_updated()
    name = site_name(updated)
    decisions = overrides.load_decisions(overrides.SheetData())
    global _PUBLIC_STAFF
    _PUBLIC_STAFF = public_staff(decisions.get("_staff"))
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
    admin_dir = out / config.settings()["admin_path"]
    admin_dir.mkdir()
    log_path = config.ROOT / "data" / "crawl_log.json"
    runs = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    (admin_dir / "index.html").write_text(
        render_admin(contests, list(pending.values()), name, updated, warnings, runs,
                     decisions=decisions,
                     titles={cid: c.title for cid, c in raw.items()}), encoding="utf-8")
    return {"name": name, "contests": len(contests), "pending": len(pending), "out": str(out),
            "admin": admin_dir.name, "staff": len(_PUBLIC_STAFF["staff"]), "warnings": warnings}
