/* 관리자 페이지: 승인·숨김·확인 버튼 → GitHub 저장소의 data/decisions.json에 저장.
   서버가 없으므로 관리자가 만든 GitHub 토큰(이 저장소 Contents 읽기·쓰기 권한)을 이 기기의 브라우저에만 보관해서 쓴다.
   저장하면 GitHub Actions가 사이트를 다시 만든다(1~2분). */
(function () {
  "use strict";
  var cfg = JSON.parse(document.getElementById("admin-config").textContent);
  var TOKEN_KEY = "contesthub_token", QUEUE_KEY = "contesthub_queue";
  var LABELS = { approve: "승인", hide: "숨김", confirm: "공개", undo: "되돌리기" };
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

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (ch) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]; }); }

  // ---------------------------------------------------------------- 직원 관리 (decisions.json의 "_staff")
  var STAFF_KEY = "contesthub_staff_draft";
  var staffDraft = load(STAFF_KEY, null);
  var staffDirty = !!staffDraft;
  if (!staffDraft) staffDraft = JSON.parse(JSON.stringify(cfg.staff || {}));
  staffDraft["default"] = staffDraft["default"] || {};
  staffDraft.staff = staffDraft.staff || [];
  var siteBase = new URL("../", location.href).href;
  function staffLink(code) { return siteBase + "?ref=" + encodeURIComponent(code); }

  function renderStaff() {
    $("staff-rows").innerHTML = staffDraft.staff.map(function (s, i) {
      return '<tr data-i="' + i + '">' +
        '<td><input data-f="name" value="' + esc(s.name) + '" placeholder="김OO 선생님"></td>' +
        '<td><input data-f="code" value="' + esc(s.code) + '" placeholder="kim" style="width:7em"></td>' +
        '<td><input data-f="form" value="' + esc(s.form) + '" placeholder="https://naver.me/..."></td>' +
        '<td><input data-f="contest_form" value="' + esc(s.contest_form) + '" placeholder="(선택)"></td>' +
        '<td class="acts"><button class="btn small" type="button" data-staff="copy">링크 복사</button>' +
        '<button class="btn small" type="button" data-staff="qr">QR</button>' +
        '<button class="btn small" type="button" data-staff="del">삭제</button></td></tr>';
    }).join("") || '<tr><td colspan="5">아직 등록된 직원이 없습니다. 아래 "+ 직원 추가"를 누르세요.</td></tr>';
    document.querySelectorAll("[data-default]").forEach(function (inp) { inp.value = staffDraft["default"][inp.getAttribute("data-default")] || ""; });
  }
  function markStaff() { staffDirty = true; store(STAFF_KEY, staffDraft); renderQueue(); }
  $("staff-rows").addEventListener("input", function (e) {
    var tr = e.target.closest("tr[data-i]");
    if (!tr) return;
    var f = e.target.getAttribute("data-f"), v = e.target.value.trim();
    if (f === "code") { v = v.toLowerCase(); }
    staffDraft.staff[+tr.getAttribute("data-i")][f] = v;
    markStaff();
  });
  document.querySelectorAll("[data-default]").forEach(function (inp) {
    inp.addEventListener("input", function () { staffDraft["default"][inp.getAttribute("data-default")] = inp.value.trim(); markStaff(); });
  });
  $("staff-add").addEventListener("click", function () {
    staffDraft.staff.push({ name: "", code: "", form: "", contest_form: "" });
    markStaff(); renderStaff();
    var inputs = $("staff-rows").querySelectorAll('input[data-f="name"]');
    if (inputs.length) inputs[inputs.length - 1].focus();
  });
  $("staff-rows").addEventListener("click", function (e) {
    var b = e.target.closest("[data-staff]");
    if (!b) return;
    var i = +b.closest("tr").getAttribute("data-i"), s = staffDraft.staff[i], kind = b.getAttribute("data-staff");
    if (kind === "del") {
      if (confirm((s.name || "이 직원") + "을(를) 삭제할까요? 이 직원 링크로 들어온 학생은 대표 문의로 연결됩니다.")) {
        staffDraft.staff.splice(i, 1); markStaff(); renderStaff();
      }
      return;
    }
    if (!s.code) { toast("코드를 먼저 입력해 주세요"); return; }
    if (staffDirty) toast("반영하기로 저장한 뒤 1~2분 지나야 이 링크가 동작해요");
    if (kind === "copy") ContestHub.copy(staffLink(s.code), (s.name || s.code) + " 링크를 복사했어요");
    if (kind === "qr") showQr(s);
  });
  function validateStaff() {
    var seen = {}, url = /^https?:\/\/\S+$/i;
    for (var i = 0; i < staffDraft.staff.length; i++) {
      var s = staffDraft.staff[i], label = (i + 1) + "번째 직원(" + (s.name || "이름 없음") + "): ";
      if (!s.name && !s.code && !s.form) continue;  // 빈 줄은 저장할 때 버림
      if (!/^[a-z0-9_-]{2,20}$/.test(s.code || "")) return label + "코드는 영어 소문자·숫자 2~20자로 적어 주세요";
      if (seen[s.code]) return label + "코드 '" + s.code + "'가 다른 직원과 겹쳐요";
      seen[s.code] = true;
      if (!url.test(s.form || "")) return label + "포트폴리오 상담 폼 주소는 https://로 시작해야 해요";
      if (s.contest_form && !url.test(s.contest_form)) return label + "공모전 문의 폼 주소는 https://로 시작해야 해요";
    }
    var d = staffDraft["default"];
    if (d.form && !url.test(d.form)) return "대표 문의: 포트폴리오 상담 폼 주소는 https://로 시작해야 해요";
    if (d.contest_form && !url.test(d.contest_form)) return "대표 문의: 공모전 문의 폼 주소는 https://로 시작해야 해요";
    return "";
  }
  function cleanedStaff() {
    return {
      "default": staffDraft["default"],
      staff: staffDraft.staff.filter(function (s) { return s.name || s.code || s.form; })
    };
  }

  function showQr(s) {
    var url = staffLink(s.code), box = $("qr-code");
    $("qr-title").textContent = (s.name || s.code) + " 공유 링크";
    $("qr-url").textContent = url;
    box.innerHTML = "";
    if (!window.QRCode) { toast("QR 도구를 불러오지 못했어요. 인터넷 연결을 확인해 주세요"); return; }
    new QRCode(box, { text: url, width: 240, height: 240, correctLevel: QRCode.CorrectLevel.M });
    setTimeout(function () {
      var canvas = box.querySelector("canvas"), img = box.querySelector("img");
      $("qr-download").href = canvas ? canvas.toDataURL("image/png") : (img ? img.src : "#");
      $("qr-download").setAttribute("download", "QR_" + (s.name || s.code) + ".png");
    }, 150);
    $("qr-modal").hidden = false;
  }
  $("qr-close").addEventListener("click", function () { $("qr-modal").hidden = true; });
  $("qr-modal").addEventListener("click", function (e) { if (e.target === this) this.hidden = true; });

  // ---------------------------------------------------------------- 공모전 직접 등록 (decisions.json의 "_manual")
  var MANUAL_KEY = "contesthub_manual_draft";
  var manualDraft = load(MANUAL_KEY, null);
  var manualDirty = !!manualDraft;
  if (!manualDraft) manualDraft = JSON.parse(JSON.stringify(cfg.manual || []));
  var manualInfo = cfg.manualInfo || {};
  var editingKey = "";
  var picked = { cats: [], subs: [], targets: [] };

  function chipGroup(id, values, labels, group) {
    $(id).innerHTML = values.map(function (v) {
      return '<button class="chip" type="button" aria-pressed="false" data-group="' + group + '" data-val="' + esc(v) + '">' + esc(labels ? labels[v] : v) + "</button>";
    }).join("");
  }
  chipGroup("m-cats", cfg.categories || [], null, "cats");
  chipGroup("m-subs", cfg.subcategories || [], null, "subs");
  chipGroup("m-targets", Object.keys(cfg.targets || {}), cfg.targets || {}, "targets");
  function renderChips() {
    document.querySelectorAll("#manual-box [data-group]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(picked[b.getAttribute("data-group")].indexOf(b.getAttribute("data-val")) >= 0));
    });
  }
  document.getElementById("manual-box").addEventListener("click", function (e) {
    var b = e.target.closest("[data-group]");
    if (!b) return;
    var list = picked[b.getAttribute("data-group")], v = b.getAttribute("data-val"), i = list.indexOf(v);
    if (i >= 0) list.splice(i, 1); else list.push(v);
    renderChips();
  });

  function host(u) { try { return new URL(u).host; } catch (e) { return u || ""; } }
  function renderManual() {
    var today = new Date().toISOString().slice(0, 10);
    var rows = manualDraft.slice().sort(function (a, b) { return (b.end_date || "") < (a.end_date || "") ? -1 : 1; });
    $("manual-rows").innerHTML = rows.map(function (m) {
      var info = manualInfo[m.key] || {};
      var title = m.title || info.title;
      var label = title ? esc(title) : '<span class="note">제목은 반영 후 링크에서 자동으로 채워집니다</span>';
      var notes = [];
      if (!m.title && info.title) notes.push("제목 자동");
      if (info.error) notes.push('<span class="tag review">' + esc(info.error) + "</span>");
      if ((m.end_date || "") < today) notes.push("마감");
      return '<tr data-key="' + esc(m.key) + '"' + (m.key === editingKey ? ' class="queued"' : "") + "><td>" + label +
        '<div class="note">' + esc(host(m.url || m.official_url)) + (notes.length ? " · " + notes.join(" · ") : "") + "</div></td>" +
        "<td>" + esc((m.start_date || "") + " ~ " + (m.end_date || "")) + "</td>" +
        "<td>" + esc((m.categories || []).join(", ")) + "</td>" +
        '<td class="acts"><button class="btn small" type="button" data-manual="edit">수정</button>' +
        '<button class="btn small" type="button" data-manual="del">삭제</button></td></tr>';
    }).join("") || '<tr><td colspan="4">직접 등록한 공모전이 없습니다.</td></tr>';
  }
  function fillForm(m) {
    $("m-url").value = m.url || m.official_url || "";
    $("m-title").value = m.title || "";
    $("m-start").value = m.start_date || "";
    $("m-end").value = m.end_date || "";
    $("m-prize").value = m.prize_text || "";
    $("m-summary").value = m.summary || "";
    $("m-apply").value = m.apply_url || "";
    picked = { cats: (m.categories || []).slice(), subs: (m.subcategories || []).slice(), targets: (m.targets || []).slice() };
    renderChips();
  }
  function resetForm() {
    editingKey = ""; fillForm({});
    $("m-add").textContent = "목록에 추가"; $("m-cancel").hidden = true;
    renderManual();
  }
  function markManual() { manualDirty = true; store(MANUAL_KEY, manualDraft); renderManual(); renderQueue(); }

  $("m-add").addEventListener("click", function () {
    var url = $("m-url").value.trim(), end = $("m-end").value, start = $("m-start").value;
    if (!/^https?:\/\/\S+$/i.test(url)) { toast("공고 링크를 https://로 시작하는 주소로 넣어 주세요"); $("m-url").focus(); return; }
    if (!end) { toast("마감일을 넣어 주세요"); $("m-end").focus(); return; }
    if (start && start > end) { toast("접수 시작이 마감일보다 늦어요"); return; }
    if (!picked.cats.length) { toast("구분(웹툰·웹소설·게임·대학)을 하나 이상 골라 주세요"); return; }
    var old = editingKey ? manualDraft.filter(function (m) { return m.key === editingKey; })[0] : null;
    var entry = Object.assign({}, old || {}, {
      key: editingKey || "m" + Date.now().toString(36),
      url: url, title: $("m-title").value.trim(), start_date: start, end_date: end,
      categories: picked.cats.slice(), subcategories: picked.subs.slice(), targets: picked.targets.slice(),
      prize_text: $("m-prize").value.trim(), summary: $("m-summary").value.trim(), apply_url: $("m-apply").value.trim()
    });
    delete entry.official_url;  // 예전 파일 형식의 이름을 url로 통일
    if (old) manualDraft[manualDraft.indexOf(old)] = entry; else manualDraft.push(entry);
    toast(old ? "수정했어요. 아래 반영하기를 눌러 주세요" : "목록에 추가했어요. 아래 반영하기를 눌러 주세요");
    resetForm(); markManual();
  });
  $("m-cancel").addEventListener("click", resetForm);
  $("manual-rows").addEventListener("click", function (e) {
    var b = e.target.closest("[data-manual]");
    if (!b) return;
    var key = b.closest("tr").getAttribute("data-key");
    var m = manualDraft.filter(function (x) { return x.key === key; })[0];
    if (!m) return;
    if (b.getAttribute("data-manual") === "del") {
      if (confirm("'" + (m.title || (manualInfo[key] || {}).title || host(m.url)) + "'을(를) 삭제할까요? 사이트에서도 내려갑니다.")) {
        manualDraft.splice(manualDraft.indexOf(m), 1);
        if (editingKey === key) resetForm();
        markManual();
      }
      return;
    }
    editingKey = key; fillForm(m);
    $("m-add").textContent = "수정 완료"; $("m-cancel").hidden = false;
    renderManual();
    $("manual-box").scrollIntoView({ behavior: "smooth" });
  });

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
    $("savebar").hidden = ids.length === 0 && !staffDirty && !manualDirty;
    var parts = [];
    if (ids.length) parts.push(ids.length + "건 반영 대기");
    if (staffDirty) parts.push("직원 정보 변경");
    if (manualDirty) parts.push("직접 등록 변경");
    $("save-count").textContent = parts.join(" · ");
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-act]");
    if (!b) return;
    var id = b.getAttribute("data-id"), act = b.getAttribute("data-act");
    if (queue[id] === act) delete queue[id]; else queue[id] = act;  // 같은 버튼을 다시 누르면 취소
    store(QUEUE_KEY, queue);
    renderQueue();
  });
  $("save-cancel").addEventListener("click", function () {
    queue = {}; store(QUEUE_KEY, queue);
    if (manualDirty) {
      manualDirty = false; store(MANUAL_KEY, null);
      manualDraft = JSON.parse(JSON.stringify(cfg.manual || []));
      resetForm();
    }
    if (staffDirty) {
      staffDirty = false; store(STAFF_KEY, null);
      staffDraft = JSON.parse(JSON.stringify(cfg.staff || {}));
      staffDraft["default"] = staffDraft["default"] || {}; staffDraft.staff = staffDraft.staff || [];
      renderStaff();
    }
    renderQueue();
  });

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
      if (staffDirty) decisions._staff = cleanedStaff();
      // 예전 파일(config/manual_contests.json)의 등록분은 첫 저장 때 함께 옮겨 담는다
      if (manualDirty || cfg.manualOrigin === "file") decisions._manual = manualDraft;
      var n = Object.keys(queue).length;
      return api("PUT", {
        message: "관리자 결정 " + n + "건" + (staffDirty ? " · 직원 정보" : "") + (manualDirty ? " · 직접 등록" : ""),
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
    if (staffDirty) {
      var problem = validateStaff();
      if (problem) { toast(problem); $("staff-box").scrollIntoView({ behavior: "smooth" }); return; }
    }
    var btn = this; btn.disabled = true; btn.textContent = "저장 중…";
    save(false).then(function () {
      queue = {}; store(QUEUE_KEY, queue);
      if (staffDirty) { cfg.staff = cleanedStaff(); staffDirty = false; store(STAFF_KEY, null); }
      if (manualDirty || cfg.manualOrigin === "file") {
        cfg.manual = JSON.parse(JSON.stringify(manualDraft)); cfg.manualOrigin = "admin";
        manualDirty = false; store(MANUAL_KEY, null);
      }
      renderQueue();
      toast("저장했어요. 1~2분 뒤 사이트와 이 페이지에 반영됩니다");
    }, function (e) {
      toast("저장 실패: " + e.message);
    }).then(function () { btn.disabled = false; btn.textContent = "반영하기"; });
  });

  renderToken();
  renderStaff();
  renderManual();
  renderQueue();
})();
