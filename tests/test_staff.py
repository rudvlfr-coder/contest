"""직원별 문의 링크."""
from datetime import datetime

from contesthub import overrides, site
from contesthub.models import Contest


def test_public_staff_filters_bad_entries():
    cfg = {
        "default": {"name": "상담실", "form": "https://naver.me/main", "contest_form": "javascript:alert(1)"},
        "staff": [
            {"code": "Kim", "name": "김OO 선생님", "form": "https://naver.me/kim", "contest_form": ""},
            {"code": "lee", "name": "이OO", "form": "naver.me/no-scheme"},   # https 없는 주소 → 제외
            {"code": "", "name": "코드 없음", "form": "https://naver.me/x"},  # 코드 없음 → 제외
            {"code": "pa<rk", "name": "박OO", "form": "https://naver.me/park"},
        ],
    }
    out = site.public_staff(cfg)
    assert out["default"] == {"name": "상담실", "form": "https://naver.me/main", "contest_form": ""}
    assert set(out["staff"]) == {"kim", "park"}
    assert out["staff"]["kim"]["name"] == "김OO 선생님"


def test_staff_key_is_not_a_decision(tmp_path):
    p = tmp_path / "decisions.json"
    p.write_text('{"_staff": {"staff": []}, "2026-aaaaaa": {"action": "hide"}}', encoding="utf-8")
    data = overrides.SheetData()
    raw = overrides.load_decisions(data, p)
    assert data.approvals == {"2026-aaaaaa": "거절"} and "_staff" in raw


def test_pages_embed_staff_and_contact_buttons():
    site._PUBLIC_STAFF = site.public_staff({"staff": [{"code": "kim", "name": "김OO", "form": "https://naver.me/kim"}]})
    try:
        c = Contest(id="2026-abc123", title="웹툰 공모전", categories=["웹툰"], end_date="2026-11-30")
        html = site.render_detail(c, "10.27 공모전", datetime(2026, 10, 27, 18))
        assert "무료 포트폴리오 상담" in html and "공모전 준비 문의" in html
        assert '"kim":{"name":"김OO"' in html
        admin = site.render_admin([], [], "10.27 공모전", datetime(2026, 10, 27, 18))
        assert "data-contact " not in admin and "직원 관리" in admin  # 관리자 페이지에는 학생용 문의 버튼 없음
    finally:
        site._PUBLIC_STAFF = {}
