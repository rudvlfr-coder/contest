import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

_keyword_override: dict | None = None


@lru_cache
def settings() -> dict:
    s = json.loads((CONFIG_DIR / "settings.json").read_text(encoding="utf-8"))
    # GitHub Actions에서는 환경변수로 주소·연락처를 넘긴다 (settings.json 값이 비어 있을 때만)
    s["site_url"] = s.get("site_url") or os.environ.get("SITE_URL", "")
    s["contact_email"] = s.get("contact_email") or os.environ.get("CONTACT_EMAIL", "")
    s["user_agent"] = s["user_agent"].format(site_url=s["site_url"] or "-", contact=s["contact_email"] or "pending")
    for key, env in (("edit_csv", "SHEET_EDIT_CSV"), ("add_csv", "SHEET_ADD_CSV"),
                     ("keywords_csv", "SHEET_KEYWORDS_CSV"), ("sites_csv", "SHEET_SITES_CSV")):
        s.setdefault("sheet", {})
        s["sheet"][key] = s["sheet"].get(key) or os.environ.get(env, "")
    return s


@lru_cache
def _file_keywords() -> dict:
    return json.loads((CONFIG_DIR / "keywords.json").read_text(encoding="utf-8"))


def keywords() -> dict:
    """구글 시트 '키워드' 탭이 있으면 그 값, 없으면 config/keywords.json."""
    return _keyword_override or _file_keywords()


def override_keywords(kw: dict | None) -> None:
    global _keyword_override
    _keyword_override = kw
