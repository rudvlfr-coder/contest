# ChatGPT 디자인 요청문

## 사용 방법
1. ChatGPT 새 대화를 엽니다.
2. 아래 **"===== 여기부터 복사 ====="** 부터 **"===== 여기까지 복사 ====="** 까지를 붙여넣습니다.
3. 바로 이어서 `site/assets/site.css` 파일을 **첨부**합니다 (첨부가 안 되면 메모장으로 열어 내용 전체를 붙여넣기).
4. `[원하는 분위기]` 칸은 보내기 전에 원하는 내용으로 바꿉니다.
5. ChatGPT가 준 CSS 전체를 `site/assets/site.css`에 덮어쓰고, GitHub에는 **이 파일 하나만** 올립니다 (Add file → Upload files → `site/assets` 폴더 안에 맞춰 올리거나, GitHub에서 파일을 열어 연필(편집) → 전체 교체).
6. 결과가 이상하면 원래 파일로 되돌리면 됩니다. 올리기 전에 Claude에게 "이 CSS 검토해줘"라고 보여 주셔도 됩니다.

---

===== 여기부터 복사 =====

너는 웹 UI 디자이너이자 CSS 개발자야. 이미 운영 중인 정적 웹사이트의 **CSS 파일 하나(site.css)만** 새로 디자인해 줘.
HTML과 JavaScript는 자동으로 생성되기 때문에 **절대 바꿀 수 없어.** 아래 규칙을 반드시 지켜 줘.

## 사이트 소개
- 웹툰·웹소설·게임·대학(실기대회) 분야 **학생 공모전 모음 사이트**. 사용자는 고등학생·대학생, 운영은 미술·게임 입시 학원.
- 학생들은 주로 **휴대폰(카카오톡 링크)** 으로 접속하고, 직원·멘토는 PC로 봄.
- 페이지 3종: ① 목록(첫 화면) ② 공모전 상세 ③ 관리자(운영진 전용, 표 위주)
- 사이트 이름은 날짜가 바뀌는 "10.27 공모전" 형식.

## 원하는 분위기
[원하는 분위기] ← 예: "깔끔하고 신뢰감 있는 교육 서비스 느낌, 포인트 컬러는 보라, 카드에 여백 넉넉히, 둥근 모서리"

## 반드시 지킬 규칙
1. **결과는 site.css 전체 한 파일**로 줘. 일부만 주지 말고 처음부터 끝까지 완성본으로.
2. **클래스명·id·data 속성·선택자 이름을 바꾸거나 새로 만들지 마.** 아래 "HTML 구조"에 있는 이름만 써. (HTML을 고칠 수 없으므로 새 클래스는 적용되지 않음)
3. **기능에 쓰이는 규칙은 동작이 그대로 유지돼야 해** (모양은 바꿔도 됨):
   - `[hidden] { display: none !important; }` — 반드시 유지
   - `.panel` 은 기본 숨김, `.panel.open` 일 때만 보임 (필터 영역)
   - `.detail-pane` 은 **1023px 이하에서는 숨김**, **1024px 이상에서만** 목록 옆 오른쪽에 보임
   - 1024px 이상: `.split` 은 2열(목록 | 상세) **5:5** 그리드, `.detail-pane` 은 `position: sticky`이며 위쪽 여백은 `var(--top-h)` (자바스크립트가 상단 헤더 높이를 이 변수에 넣어 줌), 자체 세로 스크롤
   - 1024px 이상에서 `body.index .wrap` 은 넓게(약 1280~1320px), 그 외 페이지의 `.wrap` 은 약 760px
   - 640px 이하(휴대폰)에서 `.top` 은 상단 고정을 풀기 (`position: static`) — 필터를 펼치면 화면을 가리지 않게
   - `.contactbar` 는 화면 **하단 고정**, `body.has-contact` 일 때 본문 아래쪽 여백을 줘서 마지막 카드가 가려지지 않게
   - `.savebar`(관리자) 도 하단 고정
   - `.toast` 는 기본 투명(숨김), `.toast.show` 일 때 나타남
   - `.qr-modal` 은 화면 전체를 덮는 반투명 배경 + 가운데 상자
   - `.detail > * { min-width: 0; }` 처럼 **넓은 표가 페이지 가로폭을 밀어내지 않게** 유지 (표는 `div[style*="overflow-x:auto"]` 안에서만 가로 스크롤)
4. **라이트 모드와 다크 모드 둘 다** 지원해 줘. 색은 `:root` 의 CSS 변수로 정의하고, 다크 모드는
   `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { … } }` 와 `:root[data-theme="dark"] { … }` 두 곳에 같은 값으로 넣어 줘. `body` 에는 배경색을 꼭 지정.
5. **분야별 색 4가지**를 구분되게: 웹툰(`.tag.cat-웹툰`), 웹소설(`.tag.cat-웹소설`), 게임(`.tag.cat-게임`), 대학(`.tag.cat-대학`). 클래스명에 **한글**이 들어가 있으니 그대로 써.
6. **상태 색**: 마감 7일 이내 `.dday.urgent`(눈에 띄게), 마감 `.dday.closed`(흐리게), 기본 `.dday`, 확인 필요 `.tag.review`(주의 색), 선택된 카드 `.card.selected`, 눌린 버튼 `.chip[aria-pressed="true"]`, `.btn[aria-pressed="true"]`, 주 버튼 `.btn.primary`.
7. 글꼴은 시스템 글꼴 또는 **Pretendard / Noto Sans KR** (웹폰트를 쓸 경우 CSS 맨 위 `@import` 한 줄로만). 이미지·아이콘 파일은 쓰지 마 (없음).
8. 휴대폰 가로 375px에서 **가로 스크롤이 생기지 않게**, 글자는 15px 이상, 버튼은 손가락으로 누르기 쉽게(높이 약 36px 이상).
9. 한국어 줄바꿈: `word-break: keep-all; overflow-wrap: anywhere;` 유지.
10. 색 대비는 읽기 쉽게(본문 글자와 배경 대비 충분히). 애니메이션은 짧고 은은하게만.

## HTML 구조 (바꿀 수 없음 — 이 이름들만 사용)

### 공통
```
<body class="index">            ← 목록 페이지만 class="index", 나머지는 빈 class
  <header class="top"><div class="wrap">
    <div class="title-row"><p class="site-name"><a>10.27 공모전</a></p><span class="updated">10.27 18:28 기준</span></div>
    (목록 페이지에만 아래 검색·필터 영역)
  </div></header>
  <main class="wrap"> … </main>
  <footer><div class="wrap">안내 문구 · 마지막 수집 시각</div></footer>
  <div class="contactbar" data-contact hidden>          ← 담당 직원 문의 버튼 (하단 고정)
    <span class="who" data-contact-name>담당 김경필 멘토</span>
    <a class="btn">무료 포트폴리오 상담</a>
    <a class="btn primary">공모전 준비 문의</a>
  </div>
  <div class="toast show">복사했어요</div>              ← 잠깐 떴다 사라지는 알림 (자바스크립트가 생성)
</body>
```

### 목록 페이지 — 검색·필터 (header 안)
```
<div class="search"><input id="q" type="search"><button class="btn" id="toggle">필터</button></div>
<div class="chips">
  <button class="chip" data-cat="" aria-pressed="true">전체</button>
  <button class="chip" data-cat="웹툰" aria-pressed="false">웹툰</button> … 웹소설 / 게임 / 대학
</div>
<div class="panel open" id="panel">                     ← 펼쳐졌을 때 .open
  <label>장르<select id="f-genre">…</select></label>  (label+select 5개: 장르, 참가 대상, 마감, 국내/해외, 정렬)
  <label class="check"><input type="checkbox" id="f-prize"> 상금 있는 것만</label>
  <button class="btn small" id="reset">필터 초기화</button>
</div>
```

### 목록 페이지 — 본문
```
<main class="wrap">
  <div class="split">
    <section class="list-col">
      <div class="bar">
        <span class="count" id="count">109건</span>
        <div class="actions">
          <button class="btn small">필터 링크 복사</button>
          <button class="btn small">목록 공유 문구</button>
          <button class="btn small" id="past" aria-pressed="false">지난 공모전</button>
        </div>
      </div>
      <ul class="list" id="list">
        <li class="card selected" data-id="…">           ← PC에서 선택된 카드만 .selected
          <div class="card-head">
            <h2><a>2026 노벨피아 우주최강 웹소설 공모전</a></h2>
            <span class="dday urgent">D-2</span>         ← .urgent / .closed / 없음
          </div>
          <div class="tags">
            <span class="tag cat-웹소설">웹소설</span><span class="tag">원화</span>
            <span class="tag">해외</span><span class="tag review">확인 필요</span>
          </div>
          <div class="meta"><span>주최</span><span>마감 10/29(목)</span><span>대상 고등학생</span><span>상금 최대 3억 원</span></div>
          <div class="card-foot"><button class="btn small">공유 문구 복사</button></div>
        </li>
        <li class="empty">조건에 맞는 공모전이 없어요.</li>   ← 결과 없을 때
      </ul>
    </section>
    <aside class="detail-pane" id="detail-pane">          ← PC(1024px 이상)에서만 보이는 오른쪽 상세
      (아래 "상세 내용"과 같은 구조, 제목은 h1)
      <p class="empty">왼쪽 목록에서 공모전을 선택하세요.</p>   ← 선택 전
    </aside>
  </div>
</main>
```

### 상세 내용 (상세 페이지의 main, 그리고 PC 오른쪽 .detail-pane 안)
```
<main class="wrap detail">                              ← 상세 페이지
  <div class="tags">…</div>
  <div class="card-head"><h1>공모전 제목</h1><span class="dday">D-36</span></div>
  <div class="cta">
    <a class="btn primary">공식 공고 보기</a><a class="btn">접수 페이지</a>
    <button class="btn">공유 문구 복사</button><button class="btn">링크 복사</button><a class="btn">캘린더에 마감일 추가</a>
  </div>
  <section class="box">
    <dl class="facts">
      <dt>접수 기간</dt><dd>2026.10.1(목) ~ 2026.10.29(목)</dd>
      <dt>참가 대상</dt><dd>고등학생, 대학생<div class="note">원문 설명(작은 글씨)</div></dd> …
    </dl>
  </section>
  <section class="box">
    <p class="note">출처</p><ul class="sources"><li>위비티 — <a>원문</a></li></ul>
    <p class="note">공모전 ID <code>2026-744997</code> <button class="btn small">ID 복사</button></p>
  </section>
  <p><a class="btn">← 전체 목록</a></p>
</main>
```

### 관리자 페이지 (표 위주, 운영진용 — 실용성 우선)
```
<main class="wrap detail admin">
  <h1>관리자</h1><p class="note">…</p>
  <section class="box" id="token-box">
    <div id="token-off"><b>…</b><p class="note">…</p>
      <div class="search"><input id="token-input" type="password"><button class="btn primary">연결</button></div></div>
    <div id="token-on" hidden>✅ 연결됨 <button class="btn small">연결 해제</button></div>
  </section>
  <section class="box"><h2>승인 대기 3건</h2><p class="note">…</p>
    <div style="overflow-x:auto"><table class="review">
      <thead><tr><th>제목</th><th>…</th><th>처리</th></tr></thead>
      <tbody><tr data-row="…" class="queued">           ← 버튼을 눌러 반영 대기 중인 줄은 .queued
        <td>제목<div class="note">주최 · 마감 · <code>ID</code></div></td>
        <td><span class="tag review">경쟁사 이름</span></td>
        <td class="acts"><span class="tag review queued-tag">승인 예정</span>
          <button class="btn small primary">승인</button><button class="btn small">숨김</button></td>
      </tr></tbody></table></div>
  </section>
  <section class="box" id="staff-box"><h2>직원 관리</h2>
    <div style="overflow-x:auto"><table class="review staff-table"><tbody><tr>
      <td><input></td>… <td class="acts"><button class="btn small">링크 복사</button>…</td></tr></tbody></table></div>
  </section>
</main>
<div class="qr-modal" id="qr-modal"><div class="box"><p id="qr-title"></p><div id="qr-code">(QR 이미지)</div>
  <p class="note" id="qr-url"></p><p><a class="btn small">QR 이미지 저장</a> <button class="btn small">닫기</button></p></div></div>
<div class="savebar" id="savebar"><span id="save-count">3건 반영 대기</span>
  <button class="btn">취소</button><button class="btn primary">반영하기</button></div>
```

## 결과물 형식
- **site.css 전체 코드** 한 덩어리 (코드 블록 하나)
- 그 아래에 바꾼 디자인 포인트를 **5줄 이내**로 요약

첨부한 현재 site.css 를 출발점으로 삼되, 위 규칙만 지키면 색·여백·글꼴·모서리·그림자·카드 모양은 자유롭게 바꿔도 돼.

===== 여기까지 복사 =====
