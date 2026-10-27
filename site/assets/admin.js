/* 관리자 페이지: 승인·숨김·확인 버튼 → GitHub 저장소의 data/decisions.json에 저장.
   서버가 없으므로 관리자가 만든 GitHub 토큰(이 저장소 Contents 읽기·쓰기 권한)을 이 기기의 브라우저에만 보관해서 쓴다.
   저장하면 GitHub Actions가 사이트를 다시 만든다(1~2분). */
(function () {
  "use strict";
  var cfg = JSON.parse(document.getElementById("admin-config").textContent);
  var TOKEN_KEY = "contesthub_token", QUEUE_KEY = "contesthub_queue";
  var LABELS = { approve: "승인", hide: "숨김", confirm: "확인", undo: "되돌리기" };
  var $ = function (id) { return document.getElementById(id); };
  var toast = function (m) { showToast(m); };

  function showToast(msg) {
    var el = document.getElementById("toast");
    if (!el) { el = document.createElement("div"); el.id = "toast"; el.className = "toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.textContent = msg; el.classList.add("show");
    clearTimeout(showToast._t); showToast._t = setTimeout(function () { el.classList.remove("show"); }, 3500);
  }
  function load(key, fallback) { try { var v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch (e) { return fallback; } }
  function store(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* 저장 불가한 브라우저 */ } }
  function token() { return load(TOKEN_KEY, ""); }

  // ---------------------------------------------------------------- 토큰
  function renderToken() {
    var on = !!token();
    $("token-on").hidden = !on;
    $("token-off").hidden = on;
  }
  $("token-save").addEventListener("click", function () {
    var v = $("token-input").value.trim();
    if (!v) return;
    store(TOKEN_KEY, v);
    $("token-input").value = "";
    renderToken();
    // 연결 확인
    api("GET", "").then(function () { toast("GitHub에 연결했어요"); }, function (e) { toast("연결 확인 실패: " + e.message); });
  });
  $("token-clear").addEventListener("click", function () { store(TOKEN_KEY, ""); renderToken(); toast("이 기기의 연결을 해제했어요"); });

  // ---------------------------------------------------------------- 대기열
  var queue = load(QUEUE_KEY, {});
  function renderQueue() {
    var ids = Object.keys(queue);
    document.querySelectorAll("[data-row]").forEach(function (tr) {
      var act = queue[tr.getAttribute("data-row")];
      tr.classList.toggle("queued", !!act);
      var tag = tr.querySelector(".queued-tag");
      if (act && !tag) { tag = document.createElement("span"); tag.className = "tag review queued-tag"; tr.querySelector(".acts").prepend(tag); }
      if (tag) { if (act) tag.textContent = LABELS[act] + " 예정"; else tag.remove(); }
    });
    $("savebar").hidden = ids.length === 0;
    $("save-count").textContent = ids.length + "건 반영 대기";
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-act]");
    if (!b) return;
    var id = b.getAttribute("data-id"), act = b.getAttribute("data-act");
    if (queue[id] === act) delete queue[id]; else queue[id] = act;  // 같은 버튼을 다시 누르면 취소
    store(QUEUE_KEY, queue);
    renderQueue();
  });
  $("save-cancel").addEventListener("click", function () { queue = {}; store(QUEUE_KEY, queue); renderQueue(); });

  // ---------------------------------------------------------------- GitHub 저장
  function api(method, body) {
    var url = "https://api.github.com/repos/" + cfg.repo + "/contents/" + cfg.path + (method === "GET" ? "?ref=" + cfg.branch : "");
    return fetch(url, {
      method: method,
      headers: { "Authorization": "Bearer " + token(), "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store"
    }).then(function (r) {
      if (r.status === 404 && method === "GET") return null;  // 파일이 아직 없음
      if (r.status === 401 || r.status === 403) throw new Error("토큰이 맞지 않거나 권한(Contents 읽기·쓰기)이 없어요");
      if (!r.ok) return r.text().then(function (t) { var e = new Error("GitHub 오류 " + r.status); e.status = r.status; e.detail = t; throw e; });
      return r.json();
    });
  }
  function decode(b64) { return new TextDecoder().decode(Uint8Array.from(atob(b64.replace(/\n/g, "")), function (c) { return c.charCodeAt(0); })); }
  function encode(text) { var bytes = new TextEncoder().encode(text), s = ""; bytes.forEach(function (b) { s += String.fromCharCode(b); }); return btoa(s); }

  function save(retry) {
    return api("GET", "").then(function (file) {
      var decisions = file ? JSON.parse(decode(file.content) || "{}") : {};
      var now = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 16);  // 한국 시간
      Object.keys(queue).forEach(function (id) {
        if (queue[id] === "undo") delete decisions[id];
        else decisions[id] = { action: queue[id], at: now };
      });
      var n = Object.keys(queue).length;
      return api("PUT", {
        message: "관리자 결정 " + n + "건",
        content: encode(JSON.stringify(decisions, null, 1) + "\n"),
        sha: file ? file.sha : undefined,
        branch: cfg.branch
      });
    }).catch(function (e) {
      if (e.status === 409 && !retry) return save(true);  // 동시에 저장된 경우 한 번 더
      throw e;
    });
  }
  $("save-go").addEventListener("click", function () {
    if (!token()) { toast("먼저 위에서 GitHub 토큰을 연결해 주세요"); $("token-box").scrollIntoView({ behavior: "smooth" }); return; }
    if (!cfg.repo) { toast("저장소 설정(github_repo)이 비어 있어요"); return; }
    var btn = this; btn.disabled = true; btn.textContent = "저장 중…";
    save(false).then(function () {
      queue = {}; store(QUEUE_KEY, queue); renderQueue();
      toast("저장했어요. 1~2분 뒤 사이트와 이 페이지에 반영됩니다");
    }, function (e) {
      toast("저장 실패: " + e.message);
    }).then(function () { btn.disabled = false; btn.textContent = "반영하기"; });
  });

  renderToken();
  renderQueue();
})();
