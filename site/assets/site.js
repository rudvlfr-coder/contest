/* 공모전 목록·필터·공유. 데이터는 페이지에 들어 있는 <script id="data">에서 읽는다. */
(function () {
  "use strict";

  var TARGET_LABELS = { elementary: "초등학생", middle: "중학생", high: "고등학생", univ: "대학생", grad: "대학원생", general: "일반(누구나)" };
  var CAT_CODES = { webtoon: "웹툰", webnovel: "웹소설", game: "게임", univ: "대학" };
  var GENRE_CODES = { prog: "프로그래밍", art: "원화", plan: "기획", bgm: "BGM", gfx: "그래픽", ai: "AI", comp: "대회", job: "채용", etc: "기타" };
  var WEEK = ["일", "월", "화", "수", "목", "금", "토"];

  function invert(o) { var r = {}; Object.keys(o).forEach(function (k) { r[o[k]] = k; }); return r; }
  var CAT_TO_CODE = invert(CAT_CODES), GENRE_TO_CODE = invert(GENRE_CODES);

  // ---------------------------------------------------------------- 날짜·문구
  function today() { var d = new Date(); return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
  function parseDay(s) { if (!s) return null; var p = s.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function daysLeft(c) { var e = parseDay(c.end_date); return e ? Math.round((e - today()) / 86400000) : null; }
  function status(c) {
    var left = daysLeft(c);
    if (left === null) return "날짜미정";
    if (left < 0) return "마감";
    var s = parseDay(c.start_date);
    return s && s > today() ? "진행예정" : "진행중";
  }
  function ddayText(c) {
    var left = daysLeft(c);
    if (left === null) return "미정";
    if (left < 0) return "마감";
    return left === 0 ? "D-Day" : "D-" + left;
  }
  function shortDate(s) { var d = parseDay(s); return d ? (d.getMonth() + 1) + "/" + d.getDate() + "(" + WEEK[d.getDay()] + ")" : ""; }
  function won(n) {
    if (!n) return "";
    var eok = Math.floor(n / 1e8), man = Math.round((n % 1e8) / 1e4);
    var s = (eok ? eok + "억" : "") + (man ? (eok ? " " : "") + man.toLocaleString("ko-KR") + "만" : "");
    return (s || n.toLocaleString("ko-KR")) + " 원";
  }
  function prizeText(c) {
    if (c.prize_max_krw) return "최대 " + won(c.prize_max_krw);
    return c.prize_text ? c.prize_text.slice(0, 40) : "";
  }
  function targetText(c) {
    var t = (c.targets || []).map(function (x) { return TARGET_LABELS[x]; });
    return t.length ? t.join(", ") : "자격 확인 필요";
  }
  // ---------------------------------------------------------------- 담당 직원 (직원별 공유 링크 ?ref=코드)
  // 처음 받은 링크의 직원을 30일 동안 유지한다. 그 사이 다른 직원 링크로 들어와도 바꾸지 않는다.
  var REF_KEY = "contesthub_ref", REF_DAYS = 30;
  var STAFF = (function () {
    var el = document.getElementById("staff");
    try { return el ? JSON.parse(el.textContent) : {}; } catch (e) { return {}; }
  })();
  var STAFF_MAP = STAFF.staff || {};
  function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : ""; }
  function readRef() {
    var urlRef = (new URLSearchParams(location.search).get("ref") || "").toLowerCase();
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(REF_KEY) || "null"); } catch (e) { saved = null; }
    if (saved && STAFF_MAP[saved.code] && Date.now() - saved.at < REF_DAYS * 86400000) return saved.code;
    if (STAFF_MAP[urlRef]) {
      try { localStorage.setItem(REF_KEY, JSON.stringify({ code: urlRef, at: Date.now() })); } catch (e) { /* 저장 불가 브라우저 */ }
      return urlRef;
    }
    return "";
  }
  var REF = readRef();
  function withRef(url) {
    if (!REF) return url;
    var u = new URL(url, document.baseURI);
    u.searchParams.set("ref", REF);
    return u.href;
  }
  function renderContact() {
    var s = REF ? STAFF_MAP[REF] : null, d = STAFF["default"] || {};
    var portfolio = safeUrl(s && s.form) || safeUrl(d.form);
    var contest = safeUrl(s && (s.contest_form || s.form)) || safeUrl(d.contest_form || d.form);
    var name = s ? s.name : (d.name || "");
    document.querySelectorAll("[data-contact]").forEach(function (box) {
      var show = !!(portfolio || contest);
      box.hidden = !show;
      document.body.classList.toggle("has-contact", show);
      var who = box.querySelector("[data-contact-name]");
      if (who) { who.textContent = name ? "담당 " + name : ""; who.hidden = !name; }
      var a = box.querySelector('[data-contact-link="portfolio"]');
      if (a) a.href = portfolio || contest;
      var b = box.querySelector('[data-contact-link="contest"]');
      if (b) b.href = contest || portfolio;
    });
  }

  function detailUrl(c) { return withRef(new URL("c/" + c.id + "/", document.baseURI).href); }

  function shareText(c, url) {
    var lines = ["[" + (c.categories || []).join("·") + "] " + c.title];
    var due = c.end_date ? "마감: " + shortDate(c.end_date) + " " + ddayText(c) : "마감: 미정";
    lines.push(due + " · 대상: " + targetText(c));
    var p = prizeText(c);
    if (p) lines.push("상금: " + p);
    lines.push(url || detailUrl(c));
    return lines.join("\n");
  }

  // ---------------------------------------------------------------- 공용
  function toast(msg) {
    var el = document.getElementById("toast");
    if (!el) { el = document.createElement("div"); el.id = "toast"; el.className = "toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.textContent = msg; el.classList.add("show");
    clearTimeout(toast._t); toast._t = setTimeout(function () { el.classList.remove("show"); }, 1800);
  }
  function copy(text, msg) {
    function fallback() {
      var ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); toast(msg); } catch (e) { window.prompt("복사해서 쓰세요", text); }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(function () { toast(msg); }, fallback);
    else fallback();
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (ch) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]; }); }

  window.ContestHub = { shareText: shareText, copy: copy, ddayText: ddayText, status: status, daysLeft: daysLeft, ref: REF };
  renderContact();

  // ---------------------------------------------------------------- 상세 페이지
  var detailData = document.getElementById("contest");
  if (detailData) {
    var c = JSON.parse(detailData.textContent);
    var dd = document.querySelector("[data-dday]");
    if (dd) {
      dd.textContent = ddayText(c);
      var left = daysLeft(c);
      dd.classList.toggle("urgent", left !== null && left >= 0 && left <= 7);
      dd.classList.toggle("closed", left !== null && left < 0);
    }
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-copy]");
      if (!b) return;
      var kind = b.getAttribute("data-copy");
      if (kind === "share") copy(shareText(c, withRef(location.href.split("#")[0])), "공유 문구를 복사했어요");
      if (kind === "link") copy(withRef(location.href.split("#")[0]), "링크를 복사했어요");
      if (kind === "id") copy(c.id, "공모전 ID를 복사했어요");
    });
    return;
  }

  // ---------------------------------------------------------------- 목록 페이지
  var dataEl = document.getElementById("data");
  if (!dataEl) return;
  var ALL = JSON.parse(dataEl.textContent);
  var $ = function (id) { return document.getElementById(id); };
  var state = {};

  function readState() {
    var q = new URLSearchParams(location.search);
    state = {
      cat: CAT_CODES[q.get("cat")] || "",
      genre: GENRE_CODES[q.get("genre")] || "",
      target: TARGET_LABELS[q.get("target")] ? q.get("target") : "",
      region: ["domestic", "overseas"].indexOf(q.get("region")) >= 0 ? q.get("region") : "",
      due: ["7", "30"].indexOf(q.get("due")) >= 0 ? q.get("due") : "",
      prize: q.get("prize") === "1",
      past: q.get("past") === "1",
      sort: ["due", "new", "prize"].indexOf(q.get("sort")) >= 0 ? q.get("sort") : "due",
      q: q.get("q") || ""
    };
  }
  function writeState() {
    var q = new URLSearchParams();
    if (state.cat) q.set("cat", CAT_TO_CODE[state.cat]);
    if (state.genre) q.set("genre", GENRE_TO_CODE[state.genre]);
    if (state.target) q.set("target", state.target);
    if (state.region) q.set("region", state.region);
    if (state.due) q.set("due", state.due);
    if (state.prize) q.set("prize", "1");
    if (state.past) q.set("past", "1");
    if (state.sort !== "due") q.set("sort", state.sort);
    if (state.q) q.set("q", state.q);
    if (REF) q.set("ref", REF);  // 주소창을 그대로 복사해 공유해도 담당 직원이 따라가도록
    var s = q.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : ""));
  }

  function matches(c) {
    var st = status(c);
    if (state.past ? st !== "마감" : st === "마감") return false;
    if (c.student_eligible === "no") return false;
    if (state.cat && (c.categories || []).indexOf(state.cat) < 0) return false;
    if (state.genre && (c.subcategories || []).indexOf(state.genre) < 0) return false;
    if (state.target) {
      var t = c.targets || [];
      // '일반(누구나)'는 학생도 참가할 수 있으므로 학교급 필터에도 포함
      if (t.indexOf(state.target) < 0 && !(state.target !== "general" && t.indexOf("general") >= 0)) return false;
    }
    if (state.region && (c.region || "domestic") !== state.region) return false;
    if (state.due) { var left = daysLeft(c); if (left === null || left > +state.due) return false; }
    if (state.prize && !c.prize_max_krw) return false;
    if (state.q) {
      var hay = (c.title + " " + (c.organizer || "")).toLowerCase();
      if (hay.indexOf(state.q.toLowerCase()) < 0) return false;
    }
    return true;
  }
  function sorted(list) {
    var key = {
      due: function (a, b) { return (a.end_date || "9999") < (b.end_date || "9999") ? -1 : (a.end_date || "9999") > (b.end_date || "9999") ? 1 : 0; },
      new: function (a, b) { return (b.created_at || "") < (a.created_at || "") ? -1 : (b.created_at || "") > (a.created_at || "") ? 1 : 0; },
      prize: function (a, b) { return (b.prize_max_krw || 0) - (a.prize_max_krw || 0); }
    }[state.sort];
    var out = list.slice().sort(key);
    if (state.past && state.sort === "due") out.reverse();
    return out;
  }

  function card(c) {
    var left = daysLeft(c);
    var cls = left === null ? "" : left < 0 ? " closed" : left <= 7 ? " urgent" : "";
    var tags = (c.categories || []).map(function (x) { return '<span class="tag cat-' + esc(x) + '">' + esc(x) + "</span>"; })
      .concat((c.subcategories || []).map(function (x) { return '<span class="tag">' + esc(x) + "</span>"; }));
    if (c.region === "overseas") tags.push('<span class="tag">해외</span>');
    if (c.needs_review) tags.push('<span class="tag review">확인 필요</span>');
    var meta = [];
    if (c.organizer) meta.push(esc(c.organizer));
    if (c.end_date) meta.push("마감 " + shortDate(c.end_date));
    meta.push("대상 " + esc(targetText(c)));
    var p = prizeText(c);
    if (p) meta.push("상금 " + esc(p));
    return '<li class="card' + (c.id === selectedId && WIDE.matches ? " selected" : "") + '" data-id="' + esc(c.id) + '">' +
      '<div class="card-head"><h2><a href="c/' + esc(c.id) + '/" data-open="' + esc(c.id) + '">' + esc(c.title) + "</a></h2>" +
      '<span class="dday' + cls + '">' + ddayText(c) + "</span></div>" +
      '<div class="tags">' + tags.join("") + "</div>" +
      '<div class="meta"><span>' + meta.join("</span><span>") + "</span></div>" +
      '<div class="card-foot"><button class="btn small" type="button" data-share="' + esc(c.id) + '">공유 문구 복사</button></div></li>';
  }

  // ---------------------------------------------------------------- PC: 오른쪽 상세 영역 (5:5 분할)
  var WIDE = window.matchMedia("(min-width: 1024px)");
  var selectedId = "";
  var SOURCE_NAMES = { notion: "기존 노션 목록", wevity: "위비티", contestkorea: "콘테스트코리아", mgood: "엠굿", itchio: "itch.io", sheet: "직접등록" };
  function fullDate(s) { var d = parseDay(s); return d ? d.getFullYear() + "." + (d.getMonth() + 1) + "." + d.getDate() + "(" + WEEK[d.getDay()] + ")" : "미정"; }
  function safeHref(u) { return /^https?:\/\//i.test(u || "") ? esc(u) : ""; }

  function renderPane() {
    var pane = $("detail-pane");
    var c = ALL.filter(function (x) { return x.id === selectedId; })[0];
    if (!c) { pane.innerHTML = '<p class="empty">왼쪽 목록에서 공모전을 선택하세요.</p>'; return; }
    var left = daysLeft(c);
    var cls = left === null ? "" : left < 0 ? " closed" : left <= 7 ? " urgent" : "";
    var tags = (c.categories || []).map(function (x) { return '<span class="tag cat-' + esc(x) + '">' + esc(x) + "</span>"; })
      .concat((c.subcategories || []).map(function (x) { return '<span class="tag">' + esc(x) + "</span>"; }));
    if (c.region === "overseas") tags.push('<span class="tag">해외</span>');
    if (c.needs_review) tags.push('<span class="tag review">확인 필요</span>');

    var links = [];
    if (safeHref(c.official_url)) links.push('<a class="btn primary" href="' + safeHref(c.official_url) + '" target="_blank" rel="noopener">공식 공고 보기</a>');
    if (safeHref(c.apply_url) && c.apply_url !== c.official_url) links.push('<a class="btn" href="' + safeHref(c.apply_url) + '" target="_blank" rel="noopener">접수 페이지</a>');
    links.push('<button class="btn" type="button" data-pane="share">공유 문구 복사</button>');
    links.push('<button class="btn" type="button" data-pane="link">링크 복사</button>');
    if (c.end_date) links.push('<a class="btn" href="c/' + esc(c.id) + '/event.ics" download>캘린더에 마감일 추가</a>');

    var rows = [["접수 기간", (c.start_date ? fullDate(c.start_date) + " ~ " : "~ ") + fullDate(c.end_date)]];
    if (c.organizer) rows.push(["주최", esc(c.organizer)]);
    rows.push(["참가 대상", esc(targetText(c)) + (c.target_text ? '<div class="note">' + esc(c.target_text.slice(0, 200)) + "</div>" : "")]);
    var p = prizeText(c);
    if (p || c.prize_text) rows.push(["시상", esc(p) + (c.prize_text && c.prize_max_krw ? '<div class="note">' + esc(c.prize_text.slice(0, 200)) + "</div>" : "")]);
    if (c.summary) rows.push(["소개", esc(c.summary)]);
    var sources = (c.sources || []).map(function (s) {
      return "<li>" + esc(SOURCE_NAMES[s.site] || s.site) + (safeHref(s.url) ? ' — <a href="' + safeHref(s.url) + '" target="_blank" rel="noopener">원문</a>' : "") + "</li>";
    }).join("");

    pane.innerHTML =
      '<div class="tags">' + tags.join("") + "</div>" +
      '<div class="card-head"><h1>' + esc(c.title) + '</h1><span class="dday' + cls + '">' + ddayText(c) + "</span></div>" +
      '<div class="cta">' + links.join("") + "</div>" +
      '<section class="box"><dl class="facts">' + rows.map(function (r) { return "<dt>" + r[0] + "</dt><dd>" + r[1] + "</dd>"; }).join("") + "</dl></section>" +
      '<section class="box"><p class="note" style="margin:0 0 6px">출처</p><ul class="sources">' + sources + "</ul>" +
      '<p class="note" style="margin:10px 0 0">공모전 ID <code>' + esc(c.id) + '</code> · <a href="c/' + esc(c.id) + '/" target="_blank">새 창으로 보기</a></p></section>';
    pane.scrollTop = 0;
  }
  function select(id) {
    selectedId = id;
    document.querySelectorAll("#list .card").forEach(function (li) { li.classList.toggle("selected", li.getAttribute("data-id") === id); });
    renderPane();
  }
  function syncHeaderHeight() {
    var top = document.querySelector(".top");
    if (top) document.documentElement.style.setProperty("--top-h", top.offsetHeight + "px");
  }

  var current = [];
  function render() {
    current = sorted(ALL.filter(matches));
    if (WIDE.matches && !current.some(function (c) { return c.id === selectedId; })) selectedId = current.length ? current[0].id : "";
    $("list").innerHTML = current.length ? current.map(card).join("") : '<li class="empty">조건에 맞는 공모전이 없어요.</li>';
    if (WIDE.matches) renderPane();
    syncHeaderHeight();
    $("count").textContent = (state.past ? "지난 공모전 " : "") + current.length + "건";
    document.querySelectorAll("[data-cat]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-cat") === state.cat)); });
    $("f-genre").value = state.genre; $("f-target").value = state.target; $("f-region").value = state.region;
    $("f-due").value = state.due; $("f-sort").value = state.sort; $("f-prize").checked = state.prize;
    $("past").setAttribute("aria-pressed", String(state.past));
    $("past").textContent = state.past ? "진행 중 보기" : "지난 공모전";
    if ($("q").value !== state.q) $("q").value = state.q;
    var n = ["genre", "target", "region", "due"].filter(function (k) { return state[k]; }).length + (state.prize ? 1 : 0);
    $("toggle").textContent = n ? "필터 " + n : "필터";
    writeState();
  }

  readState();
  if (["genre", "target", "region", "due"].some(function (k) { return state[k]; }) || state.prize) $("panel").classList.add("open");

  // PC에서는 카드를 누르면 페이지를 옮기지 않고 오른쪽에 상세를 보여준다 (모바일은 상세 페이지로 이동)
  $("list").addEventListener("click", function (e) {
    if (!WIDE.matches || e.target.closest("button")) return;
    var li = e.target.closest(".card[data-id]");
    if (!li) return;
    if (e.target.closest("a")) {
      if (e.ctrlKey || e.metaKey || e.shiftKey) return;  // 새 탭으로 열기는 그대로 허용
      e.preventDefault();
    }
    select(li.getAttribute("data-id"));
  });
  $("detail-pane").addEventListener("click", function (e) {
    var b = e.target.closest("[data-pane]");
    if (!b) return;
    var c = ALL.filter(function (x) { return x.id === selectedId; })[0];
    if (!c) return;
    if (b.getAttribute("data-pane") === "share") copy(shareText(c), "공유 문구를 복사했어요");
    else copy(detailUrl(c), "링크를 복사했어요");
  });
  WIDE.addEventListener ? WIDE.addEventListener("change", render) : WIDE.addListener(render);
  window.addEventListener("resize", syncHeaderHeight);

  document.addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    if (b.hasAttribute("data-cat")) { state.cat = b.getAttribute("data-cat"); render(); }
    else if (b.id === "toggle") { $("panel").classList.toggle("open"); b.setAttribute("aria-expanded", String($("panel").classList.contains("open"))); syncHeaderHeight(); }
    else if (b.id === "past") { state.past = !state.past; render(); }
    else if (b.id === "copy-link") copy(location.href, "현재 필터 링크를 복사했어요");
    else if (b.id === "copy-list") {
      var top = current.slice(0, 10).map(function (c) { return shareText(c); });
      var head = document.title + (current.length > 10 ? " (상위 10건 / 전체 " + current.length + "건)" : "");
      copy([head].concat(top).concat(["전체 목록: " + location.href]).join("\n\n"), "목록 공유 문구를 복사했어요");
    }
    else if (b.hasAttribute("data-share")) {
      var id = b.getAttribute("data-share");
      var c = ALL.filter(function (x) { return x.id === id; })[0];
      if (c) copy(shareText(c), "공유 문구를 복사했어요");
    }
    else if (b.id === "reset") { state = { cat: "", genre: "", target: "", region: "", due: "", prize: false, past: false, sort: "due", q: "" }; render(); }
  });
  ["f-genre", "f-target", "f-region", "f-due", "f-sort"].forEach(function (id) {
    $(id).addEventListener("change", function () { state[id.slice(2)] = this.value; render(); });
  });
  $("f-prize").addEventListener("change", function () { state.prize = this.checked; render(); });
  var timer;
  $("q").addEventListener("input", function () { var v = this.value.trim(); clearTimeout(timer); timer = setTimeout(function () { state.q = v; render(); }, 150); });

  render();
})();
