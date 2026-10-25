from contesthub import overrides
from contesthub.models import Contest


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8-sig")
    return str(p)


def test_edits_and_additions(tmp_path):
    data = overrides.SheetData()
    edit_rows = overrides._read_csv(write(tmp_path, "edit.csv",
        "공모전ID,제목(참고용),숨김,구분,장르,대상,마감일,제목수정,메모\n"
        "2026-aaaaaa,가,O,,,,,,\n"
        "2026-bbbbbb,나,,\"웹툰, 게임\",원화,\"고등학생, 대학생\",2026-12-01,,\n"
        "2026-cccccc,다,,만화,,,내일,,\n"
        "2026-zzzzzz,없는 ID,,웹툰,,,,,\n"))
    overrides._edits(edit_rows, data)
    add_rows = overrides._read_csv(write(tmp_path, "add.csv",
        "제목,구분,장르,시작일,마감일,주최,대상,상금,공식링크,해외,메모\n"
        "직접 등록 공모전,웹소설,,2026-11-01,2026-11-30,어딘가,고등학생,1천만원,example.com,,\n"
        "마감일 없는 공모전,웹툰,,,,,,,,,\n"))
    overrides._additions(add_rows, data)

    contests = {
        "2026-aaaaaa": Contest(id="2026-aaaaaa", title="가", end_date="2026-11-10"),
        "2026-bbbbbb": Contest(id="2026-bbbbbb", title="나", categories=["웹소설"], end_date="2026-11-10",
                               needs_review=True, review_reasons=["분류 확인 필요"]),
        "2026-cccccc": Contest(id="2026-cccccc", title="다", end_date="2026-11-10"),
    }
    out, warnings = overrides.apply(contests, data)

    assert "2026-aaaaaa" not in out  # 숨김
    b = out["2026-bbbbbb"]
    assert b.categories == ["웹툰", "게임"] and b.subcategories == ["원화"]
    assert b.targets == ["high", "univ"] and b.end_date == "2026-12-01"
    assert not b.needs_review
    assert contests["2026-bbbbbb"].categories == ["웹소설"]  # 원본은 그대로
    added = [c for c in out.values() if c.title == "직접 등록 공모전"][0]
    assert added.official_url == "https://example.com" and added.prize_max_krw == 10_000_000
    joined = "\n".join(warnings)
    assert "알 수 없는 구분 '만화'" in joined
    assert "마감일 형식 오류 '내일'" in joined
    assert "'2026-zzzzzz'를 찾을 수 없음" in joined
    assert "마감일이 없거나" in joined


def test_keywords_tab(tmp_path):
    data = overrides.SheetData()
    rows = overrides._read_csv(write(tmp_path, "kw.csv",
        "종류,이름,키워드\n구분,웹툰,\"웹툰, 만화\"\n구분,게임,게임\n장르,원화,일러스트\n제외,,\"결과 발표\"\n이상한,값,x\n"))
    overrides._keywords(rows, data)
    assert data.keywords["categories"]["웹툰"] == ["웹툰", "만화"]
    assert data.keywords["exclude_title"] == ["결과 발표"]
    assert any("이상한" in w for w in data.warnings)


def test_empty_keywords_tab_keeps_defaults(tmp_path):
    data = overrides.SheetData()
    overrides._keywords(overrides._read_csv(write(tmp_path, "kw.csv", "종류,이름,키워드\n")), data)
    assert data.keywords is None
