"""키워드 규칙 기반 분류 (작업지시서 F-03). LLM을 쓰지 않는다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from . import config

TITLE_WEIGHT = 3
BODY_WEIGHT = 1
ACCEPT_SCORE = 3  # 이 점수 이상이면 바로 공개, 1~2점은 '분류 확인 필요'


@dataclass
class Classification:
    categories: list[str] = field(default_factory=list)
    subcategories: list[str] = field(default_factory=list)
    scores: dict[str, int] = field(default_factory=dict)
    excluded: str | None = None  # 제외 사유

    @property
    def relevant(self) -> bool:
        return self.excluded is None and bool(self.categories)

    @property
    def confident(self) -> bool:
        return self.relevant and max(self.scores.get(c, 0) for c in self.categories) >= ACCEPT_SCORE


@lru_cache(maxsize=None)
def _pattern(word: str) -> re.Pattern:
    # 영문 키워드는 단어 경계로 ('ai'가 'main'에 걸리지 않게), 한글은 부분 일치
    if re.fullmatch(r"[a-z0-9 ]+", word):
        return re.compile(rf"(?<![a-z]){re.escape(word)}(?![a-z])")
    return re.compile(re.escape(word))


def _hits(text: str, words: list[str]) -> int:
    return sum(1 for w in words if _pattern(w.lower()).search(text))


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def competitor_hits(*texts: str | None) -> list[str]:
    """경쟁사 이름이 나오면 그 이름들을 돌려준다 (띄어쓰기·대소문자 무시)."""
    hay = _squash(" ".join(t for t in texts if t))
    return [name for name in config.keywords().get("competitors", []) if name.strip() and _squash(name) in hay]


# 대학 탭 = 진학과 연결되는 학교: 대학교와 전문학교(학점은행 교육기관, 예: 한국IT전문학교)
_UNIV_FULL = re.compile(r"[가-힣A-Za-z]{2,12}(?:대학교|전문학교)|\[대학\]")
# 학원·아카데미는 학교가 아니므로 대학 탭에 넣지 않고 '확인 필요'로 표시한다
_ACADEMY = re.compile(r"학원|아카데미|academy", re.I)
ACADEMY_REASON = "학원·아카데미 관련 — 확인 필요"


def has_university(*texts: str | None) -> bool:
    """'○○대학교'·'○○전문학교', '[대학]', 또는 키워드 목록의 줄임말(청강대, 한아전 …)이 있는지 (제목·주최)."""
    for text in (t for t in texts if t):
        if _UNIV_FULL.search(text):
            return True
        for name in config.keywords().get("universities", []):
            # '세종대왕'처럼 뒤에 다른 글자가 붙은 경우는 제외. '한국영상대공모전'처럼 붙여 쓴 경우는 허용
            if re.search(rf"{re.escape(name)}(?:학교|학)?(?:(?![가-힣])|(?=공모|실기|웹툰|게임|만화|애니|콘텐츠|전국))", text):
                return True
    return False


def is_academy(*texts: str | None) -> bool:
    return any(_ACADEMY.search(t) for t in texts if t)


def classify(title: str, body: str = "", organizer: str | None = None) -> Classification:
    kw = config.keywords()
    t, b = title.lower(), body.lower()
    result = Classification()

    for word in kw["exclude_title"]:
        if word.lower() in t:
            result.excluded = f"제외 키워드: {word}"
            return result

    for cat, words in kw["categories"].items():
        score = _hits(t, words) * TITLE_WEIGHT + min(_hits(b, words), 2) * BODY_WEIGHT
        if score:
            result.scores[cat] = score
    if result.scores:
        top = max(result.scores.values())
        # 제목에서 걸린 구분은 모두, 본문에서만 걸린 구분은 최고점일 때만
        result.categories = [c for c, s in result.scores.items() if s >= TITLE_WEIGHT or s == top]

    # 대학: 대학 이름이 제목에 있고, 웹툰·게임·애니 등 과목 단어가 제목·본문에 있을 때
    if has_university(title, organizer) and (_hits(t, kw.get("univ_subjects", [])) or _hits(b, kw.get("univ_subjects", []))):
        result.categories.append("대학")
        result.scores["대학"] = max(result.scores.get("대학", 0), ACCEPT_SCORE)

    for sub, words in kw["subcategories"].items():
        if _hits(t, words) or (sub != "채용" and _hits(b, words) >= 2):
            result.subcategories.append(sub)

    if not result.categories and "채용" in result.subcategories:
        result.excluded = "게임·웹툰·웹소설과 무관한 채용·대외활동"
    return result
