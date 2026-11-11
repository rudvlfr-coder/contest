"""경쟁사 관련 공모전 승인 흐름."""
from datetime import datetime

import pytest

from contesthub import config, overrides, site
from contesthub.classify import competitor_hits
from contesthub.models import Contest


@pytest.fixture
def competitors():
    kw = dict(config.keywords())
    kw["competitors"] = ["OO아카데미", "△△학원"]
    config.override_keywords(kw)
    yield
    config.override_keywords(None)


def make(cid, title, **kw):
    return Contest(id=cid, title=title, end_date="2099-12-31", categories=["웹툰"], **kw)


def test_competitor_hits_ignores_spaces_and_case(competitors):
    assert competitor_hits("제1회 OO 아카데미 X 메디방 일러스트 공모전") == ["OO아카데미"]
    assert competitor_hits("웹툰 공모전", "주최: △△학원") == ["△△학원"]
    assert competitor_hits("일반 웹툰 공모전") == []


def test_empty_competitor_list_holds_nothing():
    config.override_keywords(None)
    assert competitor_hits("OO아카데미 공모전") == []


def test_split_pending(competitors):
    contests = {
        "a": make("a", "일반 웹툰 공모전"),
        "b": make("b", "OO아카데미 콜라보 웹툰 공모전"),                       # 제목에 경쟁사 → 대기
        "c": make("c", "웹툰 공모전", competitor_hits=["△△학원"]),            # 수집 때 본문에서 찾음 → 대기
        "d": make("d", "OO아카데미 웹툰 공모전"),                              # 승인됨 → 공개
        "e": make("e", "OO아카데미 게임 공모전"),                              # 거절 → 어디에도 없음
        "f": make("f", "OO아카데미 직접등록", sources=[{"site": "sheet", "url": None}]),  # 관리자가 직접 넣은 건 → 공개
    }
    data = overrides.SheetData(approvals={"d": "승인", "e": "거절"})
    public, pending = overrides.split_pending(contests, data)
    assert set(public) == {"a", "d", "f"}
    assert set(pending) == {"b", "c"}
    assert pending["b"].competitor_hits == ["OO아카데미"]


def test_review_needed_is_hidden_until_published():
    contests = {
        "r": make("r", "애매한 공모전", needs_review=True, review_reasons=["분류 확인 필요"]),
        "ok": make("ok", "웹툰 공모전"),
        "sheet": make("sheet", "직접 넣은 공모전", needs_review=True, sources=[{"site": "sheet", "url": None}]),
    }
    applied, _ = overrides.apply(contests, overrides.SheetData())
    public, pending = overrides.split_pending(applied, overrides.SheetData())
    assert set(public) == {"ok", "sheet"} and set(pending) == {"r"}
    # 관리자가 '공개'(confirm)를 누르면 사이트에 올라간다
    data = overrides.SheetData(confirmed={"r"})
    applied, _ = overrides.apply(contests, data)
    public, pending = overrides.split_pending(applied, data)
    assert "r" in public and not pending


def test_manual_contests_file(tmp_path):
    p = tmp_path / "manual.json"
    p.write_text('{"contests": ['
                 '{"title": "직접 등록 웹툰 공모전", "categories": ["웹툰", "없는분야"], "start_date": "2026-11-30",'
                 ' "end_date": "2026-12-04", "targets": ["high"], "organizer": "네이버웹툰",'
                 ' "official_url": "https://comic.naver.com/notice", "poster_url": "javascript:x"},'
                 '{"title": "마감일 없는 공모전"}]}', encoding="utf-8")
    data = overrides.SheetData()
    overrides.load_manual(data, p)
    assert len(data.additions) == 1
    c = data.additions[0]
    assert c.categories == ["웹툰"] and c.targets == ["high"] and c.organizer == "네이버웹툰"
    assert (c.start_date, c.end_date) == ("2026-11-30", "2026-12-04") and c.poster_url is None
    assert any("마감일" in w for w in data.warnings)
    out, _ = overrides.apply({}, data)
    public, pending = overrides.split_pending(out, data)
    assert c.id in public and not pending  # 직접 등록은 승인 없이 공개


def test_admin_manual_list_and_autofill(tmp_path, monkeypatch):
    dec = tmp_path / "decisions.json"
    dec.write_text('{"_manual": ['
                   '{"key": "m1", "url": "https://example.com/a", "title": "", "end_date": "2099-12-01",'
                   ' "categories": ["게임"], "targets": ["high"]},'
                   '{"key": "m2", "url": "https://example.com/b", "title": "직접 쓴 제목", "end_date": "2099-12-02",'
                   ' "categories": ["웹툰"], "poster_url": "https://example.com/p.png"},'
                   '{"key": "m3", "url": "https://example.com/c", "title": "", "end_date": "2099-12-03", "categories": ["웹툰"]},'
                   '{"key": "m4", "url": "https://example.com/d", "title": "마감일 없음", "categories": ["웹툰"]}]}',
                   encoding="utf-8")
    file = tmp_path / "manual.json"
    file.write_text('{"contests": [{"title": "예전 파일 공모전", "end_date": "2099-01-01"}]}', encoding="utf-8")

    calls = []

    def fake_fetch(url):
        calls.append(url)
        if url.endswith("/c"):
            raise RuntimeError("접속 실패")
        return {"title": "링크에서 가져온 제목", "image": "https://example.com/og.png", "description": "링크 설명"}

    monkeypatch.setattr(overrides, "fetch_meta", fake_fetch)
    data = overrides.SheetData()
    info = overrides.load_manual(data, path=file, decisions_path=dec, fetch=True)

    titles = {c.title for c in data.additions}
    assert titles == {"링크에서 가져온 제목", "직접 쓴 제목"}  # 관리자 목록이 있으면 예전 파일은 무시
    auto = [c for c in data.additions if c.title == "링크에서 가져온 제목"][0]
    assert auto.poster_url == "https://example.com/og.png" and auto.summary == "링크 설명"
    assert info["m1"]["auto"] and calls.count("https://example.com/b") == 0  # 제목·포스터가 다 있으면 링크를 열지 않음
    assert info["m3"]["error"] and info["m4"]["error"] == "마감일 없음"
    assert any("제목이 없고" in w for w in data.warnings)


def test_real_manual_file_is_valid():
    data = overrides.SheetData()
    overrides.load_manual(data, fetch=False)
    assert not data.warnings
    assert all(c.end_date and c.categories for c in data.additions)


def test_approval_column_in_edit_tab(tmp_path):
    p = tmp_path / "edit.csv"
    p.write_text("공모전ID,승인\n2026-aaaaaa,승인\n2026-bbbbbb,거절\n2026-cccccc,보류\n", encoding="utf-8-sig")
    data = overrides.SheetData()
    overrides._edits(overrides._read_csv(str(p)), data)
    assert data.approvals == {"2026-aaaaaa": "승인", "2026-bbbbbb": "거절"}
    assert any("보류" in w for w in data.warnings)


def test_competitor_keywords_tab_without_categories(tmp_path):
    p = tmp_path / "kw.csv"
    p.write_text("종류,이름,키워드\n경쟁사,,\"OO아카데미, △△학원\"\n", encoding="utf-8-sig")
    data = overrides.SheetData()
    overrides._keywords(overrides._read_csv(str(p)), data)
    assert data.keywords["competitors"] == ["OO아카데미", "△△학원"]
    assert data.keywords["categories"] == config.keywords()["categories"]  # 분류 키워드는 기본값 유지


def test_admin_decisions(tmp_path, competitors):
    p = tmp_path / "decisions.json"
    p.write_text('{"b": {"action": "approve", "at": "2026-10-27T12:00"},'
                 ' "r": {"action": "confirm"}, "x": {"action": "hide"}, "y": {"action": "이상한값"}}', encoding="utf-8")
    data = overrides.SheetData(approvals={"b": "거절"})  # 시트 값보다 관리자 페이지 결정이 우선
    overrides.load_decisions(data, p)
    assert data.approvals == {"b": "승인", "x": "거절"} and data.confirmed == {"r"}

    contests = {
        "b": make("b", "OO아카데미 콜라보 웹툰 공모전"),
        "r": make("r", "애매한 공모전", needs_review=True, review_reasons=["분류 확인 필요"]),
        "x": make("x", "숨길 공모전"),
    }
    applied, _ = overrides.apply(contests, data)
    assert not applied["r"].needs_review and applied["r"].review_reasons == []
    public, pending = overrides.split_pending(applied, data)
    assert set(public) == {"b", "r"} and not pending  # b는 승인돼서 공개, x는 숨김


def test_school_rules_for_existing_contests():
    contests = {
        "a": make("a", "제11회 한아전 웹툰·일러스트 공모전", organizer="한국IT전문학교"),
        "b": make("b", "2026 태권도 굿즈 아이디어 공모전", organizer="전주대학교 태권도학과"),  # 과목 단어 없음
        "c": make("c", "2026 대원 웹소설 아카데미 공모전", organizer="대원씨아이(주)"),
        "d": make("d", "한아전 웹툰 공모전"),  # 시트에서 구분을 직접 고친 건
    }
    data = overrides.SheetData(edits={"d": {"categories": ["웹툰"]}}, confirmed=set())
    out, _ = overrides.apply(contests, data)
    assert "대학" in out["a"].categories
    assert "대학" not in out["b"].categories
    assert "대학" not in out["c"].categories and out["c"].needs_review
    assert out["d"].categories == ["웹툰"]
    # 관리자가 '확인'을 누르면 학원·아카데미 표시가 지워진다
    out, _ = overrides.apply(contests, overrides.SheetData(confirmed={"c"}))
    assert not out["c"].needs_review


def test_broken_decisions_file_is_ignored(tmp_path):
    p = tmp_path / "decisions.json"
    p.write_text("{깨진 파일", encoding="utf-8")
    data = overrides.SheetData()
    assert overrides.load_decisions(data, p) == {}
    assert any("decisions.json" in w for w in data.warnings)


def test_admin_page_lists_pending(competitors):
    pending = [make("2026-bbbbbb", "OO아카데미 콜라보 웹툰 공모전", competitor_hits=["OO아카데미"],
                    sources=[{"site": "wevity", "url": "https://example.com/1"}])]
    html = site.render_admin([], pending, "10.27 공모전", datetime(2026, 10, 27, 18), [], [])
    assert "승인 대기 1건" in html and "2026-bbbbbb" in html and 'content="noindex"' in html
    assert 'href="https://example.com/1"' in html
