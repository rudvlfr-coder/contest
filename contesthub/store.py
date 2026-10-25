"""data/contests.json 읽기·쓰기와 병합."""
from __future__ import annotations

import json
from pathlib import Path

from .models import Contest

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "contests.json"


def load(path: Path = DEFAULT_PATH) -> dict[str, Contest]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {r["id"]: Contest.from_dict(r) for r in rows}


def save(contests: dict[str, Contest], path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted((c.to_dict() for c in contests.values()),
                  key=lambda r: (r["end_date"] or "9999", r["id"]))
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _union(a: list, b: list) -> list:
    return a + [x for x in b if x not in a]


def merge(base: Contest, new: Contest) -> Contest:
    """같은 공모전 두 건을 합친다. 비어 있는 칸은 채우고, 목록은 합집합."""
    for f in Contest.__dataclass_fields__:
        old_v, new_v = getattr(base, f), getattr(new, f)
        if isinstance(old_v, list):
            setattr(base, f, _union(old_v, new_v))
        elif old_v in (None, "", "unknown") and new_v not in (None, ""):
            setattr(base, f, new_v)
    base.needs_review = base.needs_review or new.needs_review
    if new.updated_at and (not base.updated_at or new.updated_at > base.updated_at):
        base.updated_at = new.updated_at
    return base
