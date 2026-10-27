"""참가 자격 문구 → 대상 태그, 학생 참가 가능 여부."""
from __future__ import annotations

import re

_GENERAL = re.compile(r"누구나|제한\s*없|무관|일반인|전\s*국민|일반\s*부|일반$|^일반|개인\s*또는\s*팀")
_NOT_STUDENT = re.compile(r"기성\s*작가|사업자|법인|경력\s*\d+\s*년|재직자|현직")

# 학교급 키워드. '중고등'처럼 붙어 쓰는 경우를 위해 개별 글자 패턴도 둔다.
_PATTERNS = [
    ("elementary", re.compile(r"초등|초\s*/|어린이")),
    ("middle", re.compile(r"중학|중등|중고|중\s*/|중\s*,|중\s*·|청소년")),
    ("high", re.compile(r"고등|고교|중고|고\s*/|고\s*,|/\s*고|재수생|청소년|고3|N수")),
    ("univ", re.compile(r"대학생|대학교|재학생|휴학생|대\s*학\s*\(원\)|/\s*대|청년|대학$")),
    ("grad", re.compile(r"대학원")),
]

_AGE_RANGE = re.compile(r"(\d{1,2})\s*세\s*[~\-]\s*(\d{1,2})\s*세")
_AGE_MIN = re.compile(r"(\d{1,2})\s*세\s*이상|만\s*(\d{1,2})\s*세\s*이상")

# 학교급별 대략적인 나이 구간
_AGE_BANDS = {"elementary": (8, 12), "middle": (13, 15), "high": (16, 18), "univ": (19, 99), "grad": (22, 99)}


def _tags_from_age(lo: int, hi: int) -> set[str]:
    return {tag for tag, (a, b) in _AGE_BANDS.items() if lo <= b and hi >= a}


def parse_targets(text: str | None) -> tuple[list[str], str]:
    """(대상 태그 목록, 학생 참가 여부 yes/no/unknown)."""
    if not text or not text.strip():
        return [], "unknown"
    t = text.strip()
    tags: set[str] = set()

    if _GENERAL.search(t):
        tags.add("general")
    for tag, pat in _PATTERNS:
        if pat.search(t):
            tags.add(tag)

    m = _AGE_RANGE.search(t)
    if m:
        tags |= _tags_from_age(int(m.group(1)), int(m.group(2)))
    m = _AGE_MIN.search(t)
    if m:
        lo = int(m.group(1) or m.group(2))
        tags |= _tags_from_age(lo, 99)
        if lo >= 19:
            tags.add("general")

    if "general" in tags or tags & {"elementary", "middle", "high", "univ", "grad"}:
        eligible = "yes"
    elif _NOT_STUDENT.search(t):
        eligible = "no"
    else:
        eligible = "unknown"

    order = ["elementary", "middle", "high", "univ", "grad", "general"]
    return [x for x in order if x in tags], eligible
