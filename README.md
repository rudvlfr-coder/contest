# ContestHub

웹툰·웹소설·게임 분야 학생 공모전을 자동으로 모아 정적 사이트(`{M.DD} 공모전`)로 보여주는 프로젝트입니다.
요구사항은 [작업지시서_공모전수집기.md](작업지시서_공모전수집기.md)를 참고하세요.

## 배포·운영
처음 배포하는 방법과 평소 운영 방법은 [docs/배포안내.md](docs/배포안내.md)를 보세요.
- 자동 실행: `.github/workflows/crawl.yml` (매일 08:00·18:00 KST 수집 → 사이트 생성 → GitHub Pages 배포)
- 운영 수정: 구글 시트 ([docs/구글시트_양식.xlsx](docs/구글시트_양식.xlsx)). 양식 다시 만들기: `python tools/make_sheet_template.py` (openpyxl 필요)

## 설치
```
python -m pip install -r requirements.txt
```

## 명령
| 명령 | 설명 |
|---|---|
| `python -m contesthub crawl` | 켜져 있는 모든 사이트 수집 (`config/settings.json`) |
| `python -m contesthub crawl --site wevity --limit 5` | 한 사이트만, 새 공모전 5건까지 (시험용) |
| `python -m contesthub import-notion data/notion/notion_export_all.csv` | 노션 CSV를 `data/contests.json`으로 가져오기 (여러 번 실행해도 중복되지 않음) |
| `python -m contesthub build` | 정적 사이트를 `site/dist/`에 생성 (사이트 이름은 마지막 수집 성공 날짜로 `M.DD 공모전`) |
| `python -m http.server 8000 --directory site/dist` | 만든 사이트를 내 컴퓨터에서 미리 보기 |
| `python -m contesthub stats` | 상태·구분·장르·대상별 건수 |
| `python -m pytest -q tests` | 테스트 |

## 구조
```
config/
├─ settings.json    # User-Agent, 요청 간격, 사이트별 on/off·페이지 수
└─ keywords.json    # 구분·장르 분류 키워드, 제외 키워드
contesthub/
├─ models.py        # Contest 데이터 형식, 구분·장르 목록
├─ textutil.py      # 날짜·상금·URL·제목 정규화, 고정 ID
├─ eligibility.py   # 참가대상 문구 → 대상 태그
├─ classify.py      # 키워드 규칙 분류
├─ dedupe.py        # 여러 사이트에 올라온 같은 공모전 찾기
├─ http.py          # 요청 간격·재시도를 지키는 HTTP 클라이언트
├─ crawl.py         # 수집 실행 (수집기 → 분류 → 중복 제거 → 저장)
├─ collectors/      # wevity.py, contestkorea.py, mgood.py, itchio.py
└─ importers/notion_csv.py
data/
├─ contests.json    # 전체 공모전 데이터
├─ seen.json        # 이미 확인한 출처 주소 (다시 요청하지 않음)
├─ crawl_log.json   # 수집 실행 기록 (최근 200회)
└─ notion/          # 노션 원본 CSV
tests/fixtures/     # 사이트별 실제 페이지 사본 (파서 회귀 테스트)
docs/사이트조사.md   # 수집 대상 사이트 조사
```

## 새 사이트 추가
1. `contesthub/collectors/`에 `Collector`를 상속한 클래스 작성 (`list_items`, `parse_detail` 또는 `from_list_item`)
2. `collectors/__init__.py`의 `COLLECTORS`에 등록
3. `config/settings.json`의 `sites`에 켜기
4. 실제 페이지를 `tests/fixtures/`에 저장하고 파서 테스트 추가
