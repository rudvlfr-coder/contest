"""1회용: '대학'을 장르에서 구분으로 옮기고, 제목에 대학 이름+과목이 있는 기존 공모전에 '대학'을 붙인다.
또 예전 규칙으로 '관련 없음' 처리된 출처 기록을 지워, 다음 수집 때 새 규칙으로 다시 판단하게 한다.

python tools/migrate_univ_category.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from contesthub import config, store  # noqa: E402
from contesthub.classify import _hits, has_university  # noqa: E402

contests = store.load()
moved = tagged = 0
subjects = config.keywords()["univ_subjects"]
for c in contests.values():
    if "대학" in c.subcategories:
        c.subcategories.remove("대학")
        if "대학" not in c.categories:
            c.categories.append("대학")
        c.review_reasons = [r for r in c.review_reasons if r != "구분 없음"]
        c.needs_review = bool(c.review_reasons)
        moved += 1
    elif "대학" not in c.categories and has_university(c.title) and _hits(c.title.lower(), subjects):
        c.categories.append("대학")
        tagged += 1
store.save(contests)

seen_path = ROOT / "data" / "seen.json"
seen = json.loads(seen_path.read_text(encoding="utf-8"))
before = len(seen)
seen = {k: v for k, v in seen.items() if v.get("relevant")}
seen_path.write_text(json.dumps(seen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"장르→구분 {moved}건, 제목으로 대학 추가 {tagged}건, 다시 판단할 출처 {before - len(seen)}건")
