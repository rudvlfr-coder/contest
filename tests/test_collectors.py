"""사이트별 파서 회귀 테스트. 픽스처는 2026-10-25에 저장한 실제 페이지."""
from pathlib import Path

from contesthub.classify import classify
from contesthub.collectors import contestkorea, itchio, mgood, wevity
from contesthub.collectors.base import ListItem
from contesthub.dedupe import same_contest
from contesthub.models import Contest

FIX = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def test_wevity_list():
    items = wevity.parse_list(read("wevity_list.html"))
    assert len(items) >= 10
    first = items[0]
    assert first.title == "2026 대경권 캠퍼스 IR 챔피언십 (창업 공모전)"
    assert first.url == "https://www.wevity.com/?c=find&s=1&gbn=viewok&ix=111768"
    assert first.status == "접수중"
    assert first.extra["organizer"] == "(주)포항연합기술지주"


def test_wevity_detail():
    item = ListItem(url=wevity.detail_url("111767"), title="")
    c, body = wevity.WevityCollector().parse_detail(item, read("wevity_view.html"))
    assert c.title == "2026 충북글로벌게임센터 AI 게임 개발 공모전"
    assert (c.start_date, c.end_date) == ("2026-10-26", "2026-10-30")
    assert c.organizer == "청주시문화산업진흥재단"
    assert c.prize_max_krw == 8_000_000
    assert c.official_url.startswith("https://cbgame.org/")
    assert "충청북도" in body
    assert c.sources == [{"site": "wevity", "url": item.url}]


def test_contestkorea_list():
    items = contestkorea.parse_list(read("contestkorea_list.html"))
    assert len(items) == 50
    assert items[0].title == "제18회 전국초등학생 웹툰공모전"
    assert items[0].url.startswith("https://www.contestkorea.com/sub/view.php?int_gbn=1&Txt_bcode=030610001&str_no=")


def test_contestkorea_detail():
    item = ListItem(url="https://www.contestkorea.com/sub/view.php?int_gbn=1&Txt_bcode=030610001&str_no=202610230020", title="")
    c, _ = contestkorea.ContestKoreaCollector().parse_detail(item, read("contestkorea_view.html"))
    assert c.title == "2026 제2회 대한민국 AI 창조공모대전"
    assert (c.start_date, c.end_date) == ("2026-11-23", "2026-11-27")
    assert c.official_url == "http://koreaaiart.com/"
    assert c.prize_max_krw == 1_500_000
    assert {"elementary", "middle", "high", "univ", "grad", "general"} <= set(c.targets)
    assert c.target_text == "누구나, 유치원, 초등학생, 중학생, 고등학생, 대학생, 대학원생, 일반인, 외국인"


def test_itch_lists():
    progress = itchio.parse_list(read("itch_in_progress.html"))
    upcoming = itchio.parse_list(read("itch_upcoming.html"))
    assert len(progress) == 50 and len(upcoming) == 50
    assert all(i.extra["end"] is not None for i in progress + upcoming)
    # upcoming 목록에도 이미 시작한 잼('Submission closes in')이 일부 섞여 있다
    assert sum(i.extra["start"] is not None for i in upcoming) >= 40
    assert all(i.url.startswith("https://itch.io/jam/") for i in progress + upcoming)
    c, _ = itchio.ItchioCollector().from_list_item(upcoming[0])
    assert c.categories == ["게임"] and c.region == "overseas"
    assert c.end_date >= c.start_date


def test_mgood_list_and_detail():
    items = mgood.parse_list(read("mgood_list.html"))
    assert len(items) == 20
    first = items[0]
    assert first.title == "2026 제5회 서원대학교 웹툰 콘텐츠 공모전"
    assert first.url == "https://www.mgood.co.kr/contest/21002_contest_view.php?c_seq=4455"
    assert first.status == "접수중"
    assert (first.extra["start"], first.extra["end"]) == ("2026-10-19", "2026-12-10")
    assert first.extra["organizer"] == "서원대학교"
    assert first.extra["field"].startswith("칸만화")
    assert sum(i.status == "마감" for i in items) >= 15
    c, body = mgood.MgoodCollector().parse_detail(first, read("mgood_view.html"))
    assert c.target_text == "중등부 고등1부 고등2부"
    assert c.targets == ["middle", "high"]
    assert set(classify(c.title, body).categories) == {"웹툰", "대학"}


def test_classify_university():
    # 대학 이름 + 과목 단어 → '대학' 구분
    assert "대학" in classify("2026년 제12회 전국 중.고교생 서강 게임/애니/만화 아이디어 공모전 서강대학교").categories
    assert "대학" in classify("2026 청강대 실기대전 [2차]", "만화/컬러 스크롤 웹툰").categories
    assert "대학" in classify("2026[대학]한국영상대공모전", "웹툰[디지털]").categories
    # 과목과 무관한 대학 대회는 제외
    assert not classify("2026 인하대학교 전국 고등학생 디자인 실기대회", "기초디자인").relevant
    # '대학생' 대상 공모전이나 '세종대왕'은 대학 이름이 아님
    assert "대학" not in classify("대학생 웹툰 공모전").categories
    assert "대학" not in classify("세종대왕 이야기 웹툰 공모전").categories


def test_classify():
    r = classify("2026 충북글로벌게임센터 AI 게임 개발 공모전")
    assert r.relevant and r.confident and r.categories == ["게임"]
    assert {"프로그래밍", "AI"} <= set(r.subcategories)
    assert classify("제18회 전국초등학생 웹툰공모전").categories == ["웹툰"]
    assert not classify("동작구 관내 공원 시설명칭 공모").relevant
    assert not classify("2026 대경권 캠퍼스 IR 챔피언십 (창업 공모전)").relevant
    assert not classify("[수상자 발표] 2026 웹툰 공모전").relevant
    assert not classify("[초록우산] 동광 제121권 제2호 투고 논문 모집").relevant
    assert not classify("Minimalist TTRPG Jam 5").relevant
    assert classify("드골2: 자유의 시대 포스터·굿즈 공모전").categories == ["게임"]
    # 영문 키워드는 단어 경계로만 ('ai'가 'main'에 걸리지 않음)
    assert "AI" not in classify("Main 웹툰 공모전").subcategories


def test_same_contest():
    a = Contest(id="a", title="2026 밀리로드 출간 공모전 | 밀리의서재", end_date="2026-11-30")
    b = Contest(id="b", title="[밀리의서재] 2026 밀리로드 출간 공모전", end_date="2026-11-30")
    c = Contest(id="c", title="2026 밀리로드 출간 공모전", end_date="2026-08-31")
    assert same_contest(a, b)
    assert not same_contest(a, c)
