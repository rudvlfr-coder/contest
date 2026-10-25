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


def classify(title: str, body: str = "") -> Classification:
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

    for sub, words in kw["subcategories"].items():
        if _hits(t, words) or (sub not in ("채용", "대학") and _hits(b, words) >= 2):
            result.subcategories.append(sub)

    if not result.categories and "채용" in result.subcategories:
        result.excluded = "게임·웹툰·웹소설과 무관한 채용·대외활동"
    return result
