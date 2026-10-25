from datetime import date, datetime

import pytest

from contesthub.eligibility import parse_targets
from contesthub.textutil import clean_title, clean_url, parse_date, parse_datetime, parse_prize


@pytest.mark.parametrize("text, expected", [
    ("1억", 100_000_000),
    ("1,200만원", 12_000_000),
    ("일천만원", 10_000_000),
    ("60000000", 60_000_000),
    ("18억", 1_800_000_000),
    ("1억5천", 150_000_000),
    ("3억5천만원", 350_000_000),
    ("8백만원", 8_000_000),
    ("약 3천만원", 30_000_000),
    ("100만원+a", 1_000_000),
    ("선인세 100만원", 1_000_000),
    ("1,000만 원", 10_000_000),
    ("45만원", 450_000),
    ("MG+RS", None),
    ("입학특전", None),
    ("갤럭시 버즈 2pro", None),
    ("", None),
])
def test_parse_prize(text, expected):
    assert parse_prize(text) == expected


def test_parse_dates():
    assert parse_date("2026년 4월 6일") == date(2026, 4, 6)
    assert parse_date("2026.11.30") == date(2026, 11, 30)
    assert parse_date("날짜 미정") is None
    assert parse_datetime("2026년 2월 21일 오전 4:54") == datetime(2026, 2, 21, 4, 54)
    assert parse_datetime("2026년 2월 21일 오후 1:33") == datetime(2026, 2, 21, 13, 33)
    assert parse_datetime("2026년 7월 10일 오전 12:09") == datetime(2026, 7, 10, 0, 9)


def test_clean_url():
    assert clean_url("lemonsound.co/lemonation/contest-461gndqr?") == "https://lemonsound.co/lemonation/contest-461gndqr"
    assert clean_url("https://a.com/p?id=3&utm_source=x&utm_medium=y") == "https://a.com/p?id=3"
    assert clean_url("https://a.com/x.do;jsessionid=ABC.worker1?enc=Z") == "https://a.com/x.do?enc=Z"
    assert clean_url("") is None


def test_clean_title():
    assert clean_title("봉은사 사천왕 캐릭터 공모전 (1)") == ("봉은사 사천왕 캐릭터 공모전", True)
    assert clean_title('"2026[대학]재능대 "') == ("2026[대학]재능대", False)


@pytest.mark.parametrize("text, tags, eligible", [
    ("고등학생", ["high"], "yes"),
    ("중고등생", ["middle", "high"], "yes"),
    ("중/고/대", ["middle", "high", "univ"], "yes"),
    ("19세 이상", ["univ", "grad", "general"], "yes"),
    ("누구나", ["general"], "yes"),
    ("신인/기성 무관", ["general"], "yes"),
    ("10세 ~ 16세 남아", ["elementary", "middle", "high"], "yes"),
    ("인스타툰", [], "unknown"),
    ("대전,세종,충남,충북만 해당", [], "unknown"),
    (None, [], "unknown"),
])
def test_parse_targets(text, tags, eligible):
    assert parse_targets(text) == (tags, eligible)
