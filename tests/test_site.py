import json
from datetime import date, datetime

from contesthub import site
from contesthub.models import Contest


def test_site_name():
    assert site.site_name(date(2026, 10, 25)) == "10.25 공모전"
    assert site.site_name(date(2027, 1, 5)) == "1.05 공모전"


def test_last_updated_ignores_failed_runs(tmp_path):
    log = tmp_path / "log.json"
    log.write_text(json.dumps([
        {"site": "a", "listed": 10, "finished_at": "2026-10-24T18:00:00"},
        {"site": "a", "listed": 0, "errors": ["x"], "finished_at": "2026-10-25T08:00:00"},
    ]), encoding="utf-8")
    assert site.last_updated(log) == datetime(2026, 10, 24, 18, 0)


def test_fmt_won():
    assert site.fmt_won(10_000_000) == "1,000만 원"
    assert site.fmt_won(150_000_000) == "1억 5,000만 원"
    assert site.fmt_won(300_000_000) == "3억 원"
    assert site.fmt_won(None) == ""


def test_detail_and_ics():
    c = Contest(id="2026-abc123", title="테스트 웹툰 공모전, 제1회", categories=["웹툰"], end_date="2026-11-30",
                start_date="2026-11-01", targets=["high"], prize_max_krw=5_000_000,
                official_url="https://example.com/a?b=1&c=2", sources=[{"site": "wevity", "url": "https://w/1"}])
    html = site.render_detail(c, "10.25 공모전", datetime(2026, 10, 25, 18))
    assert "<title>테스트 웹툰 공모전, 제1회 | 10.25 공모전</title>" in html
    assert 'og:description" content="마감 11/30(월) · 대상 고등학생 · 상금 최대 500만 원"' in html
    assert 'href="https://example.com/a?b=1&amp;c=2"' in html
    ics = site.render_ics(c, "")
    assert "DTSTART;VALUE=DATE:20261130" in ics and "DTEND;VALUE=DATE:20261201" in ics
    assert "SUMMARY:[마감] 테스트 웹툰 공모전\\, 제1회" in ics


def test_json_script_escapes_closing_tag():
    out = site.json_script("data", [{"title": "</script><b>"}])
    assert "</script><b>" not in out.removesuffix("</script>")
