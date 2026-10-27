"""사용법:
  python -m contesthub crawl [--site wevity] [--limit 10]
  python -m contesthub import-notion <노션 _all.csv 경로>
  python -m contesthub stats
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from . import store
from .importers.notion_csv import import_csv


def cmd_import_notion(args: argparse.Namespace) -> int:
    imported, stats = import_csv(Path(args.csv))
    contests = store.load()
    for cid, c in imported.items():
        contests[cid] = store.merge(contests[cid], c) if cid in contests else c
    store.save(contests)
    print(f"CSV {stats['rows']}행 → 공모전 {stats['contests']}건 "
          f"(빈 행 {stats['skipped_empty']}개 제외, 복제 행 {stats['merged']}개 병합)")
    review = [c for c in imported.values() if c.needs_review]
    print(f"확인 필요 {len(review)}건")
    for c in review:
        print(f"  - [{c.id}] {c.title}: {', '.join(c.review_reasons)}")
    return 0


def cmd_stats(_: argparse.Namespace) -> int:
    contests = store.load()
    today = date.today()
    print(f"전체 {len(contests)}건")
    print("상태:", dict(Counter(c.status(today) for c in contests.values())))
    print("구분:", dict(Counter(x for c in contests.values() for x in c.categories)))
    print("장르:", dict(Counter(x for c in contests.values() for x in c.subcategories)))
    print("대상:", dict(Counter(x for c in contests.values() for x in c.targets)))
    return 0


def cmd_crawl(args: argparse.Namespace) -> int:
    from .crawl import run

    report = run(sites=args.site or None, limit=args.limit)
    failed = False
    for s in report:
        print(f"[{s['site']}] 목록 {s['listed']}건 · 이미 본 것 {s['already_seen']} · 무관 {s['irrelevant']} · "
              f"신규 {s['new']} (확인 필요 {s['needs_review']}) · 병합 {s['merged']} · 오류 {len(s['errors'])}")
        for e in s["errors"][:5]:
            print(f"    ! {e}")
        failed |= s["listed"] == 0 and bool(s["errors"])
    return 1 if failed else 0


def cmd_build(_: argparse.Namespace) -> int:
    from .site import build

    r = build()
    print(f"'{r['name']}' 사이트 생성: 공모전 {r['contests']}건 (승인 대기 {r['pending']}건) → {r['out']}")
    print(f"    관리자 페이지: /{r['admin']}/")
    for w in r["warnings"]:
        print(f"    ! {w}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="contesthub")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("crawl", help="사이트 수집")
    s.add_argument("--site", action="append", help="특정 사이트만 (여러 번 지정 가능)")
    s.add_argument("--limit", type=int, help="사이트당 새로 처리할 최대 건수 (시험용)")
    s.set_defaults(func=cmd_crawl)
    s = sub.add_parser("build", help="정적 사이트 생성 (site/dist)")
    s.set_defaults(func=cmd_build)
    s = sub.add_parser("import-notion", help="노션 CSV 가져오기")
    s.add_argument("csv")
    s.set_defaults(func=cmd_import_notion)
    s = sub.add_parser("stats", help="수집 현황")
    s.set_defaults(func=cmd_stats)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
