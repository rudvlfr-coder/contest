from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

CATEGORIES = ("웹툰", "웹소설", "게임")
SUBCATEGORIES = ("프로그래밍", "원화", "기획", "BGM", "그래픽", "AI", "대회", "대학", "채용", "기타")

# 참가 대상 태그 (코드 → 화면 표시)
TARGET_LABELS = {
    "elementary": "초등학생",
    "middle": "중학생",
    "high": "고등학생",
    "univ": "대학생",
    "grad": "대학원생",
    "general": "일반(누구나)",
}


@dataclass
class Contest:
    id: str
    title: str
    official_url: str | None = None
    apply_url: str | None = None
    organizer: str | None = None
    categories: list[str] = field(default_factory=list)
    subcategories: list[str] = field(default_factory=list)
    start_date: str | None = None  # YYYY-MM-DD (KST)
    end_date: str | None = None
    prize_text: str | None = None
    prize_max_krw: int | None = None
    target_text: str | None = None
    targets: list[str] = field(default_factory=list)
    student_eligible: str = "unknown"  # yes / no / unknown
    region: str = "domestic"  # domestic / overseas
    summary: str | None = None
    needs_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)  # [{"site": ..., "url": ...}]
    created_at: str | None = None
    updated_at: str | None = None

    def status(self, today: date) -> str:
        """진행예정 / 진행중 / 마감 / 날짜미정 (마감일 당일까지 진행중)."""
        if not self.end_date:
            return "날짜미정"
        if date.fromisoformat(self.end_date) < today:
            return "마감"
        if self.start_date and date.fromisoformat(self.start_date) > today:
            return "진행예정"
        return "진행중"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Contest:
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)
