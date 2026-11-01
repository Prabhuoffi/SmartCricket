// Shared helpers: session, API calls, protected images, layout, theme, toasts and small animations.

const TOKEN_KEY = "sc_token";
const NAME_KEY = "sc_name";
const THEME_KEY = "sc_theme";
const ROLE_KEY = "sc_role";

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};

// Apply the saved theme as early as possible to avoid a flash.
(function () {
  const t = store.get(THEME_KEY) || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = t;
})();

const getToken = () => store.get(TOKEN_KEY);
function saveSession(token, name, role = "player") { store.set(TOKEN_KEY, token); store.set(NAME_KEY, name); store.set(ROLE_KEY, role); }
// reason: "out" (the user chose to sign out) or "expired" (the server rejected the token)
function signOut(reason = "out") {
  store.del(TOKEN_KEY); store.del(NAME_KEY); store.del(ROLE_KEY);
  // an expired session brings the player back to the same page after signing in again
  location.replace(reason === "expired" ? `login.html?expired=1&next=${encodeURIComponent(herePage())}` : "login.html?signedout=1");
}

// Signing out (or in as someone else) in one tab updates every other open tab.
addEventListener("storage", e => {
  if (e.key !== TOKEN_KEY || location.pathname.endsWith("login.html")) return;
  if (!e.newValue) location.replace("login.html?signedout=1");
  else if (e.oldValue && e.newValue !== e.oldValue) location.replace(homePage());
});

// Small confirmation popover under the sign-out button.
function confirmSignOut(anchor) {
  if (document.querySelector(".so-pop")) return;
  const pop = document.createElement("div");
  pop.className = "so-pop"; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", "Sign out");
  const name = store.get(NAME_KEY) || "your account";
  pop.innerHTML = `<div class="so-head"><span class="so-ic">${icon("logout")}</span><div><b>Sign out?</b>
      <small>You're signed in as ${esc(name)}${isAdmin() ? " (admin)" : ""}. Your data stays saved.</small></div></div>
    <div class="so-actions"><button type="button" class="ghost" data-a="no">Cancel</button><button type="button" data-a="yes">${icon("logout")} Sign out</button></div>`;
  document.body.append(pop);
  const r = anchor.getBoundingClientRect();
  pop.style.top = `${r.bottom + 10}px`;
  pop.style.right = `${Math.max(12, innerWidth - r.right)}px`;
  const close = () => { pop.classList.add("out"); setTimeout(() => pop.remove(), 160); document.removeEventListener("mousedown", outside); document.removeEventListener("keydown", esc_); anchor.focus(); };
  const outside = e => { if (!pop.contains(e.target) && e.target !== anchor && !anchor.contains(e.target)) close(); };
  const esc_ = e => { if (e.key === "Escape") close(); };
  setTimeout(() => { document.addEventListener("mousedown", outside); document.addEventListener("keydown", esc_); });
  pop.querySelector('[data-a="no"]').onclick = close;
  const yes = pop.querySelector('[data-a="yes"]');
  yes.onclick = () => { yes.disabled = true; yes.innerHTML = '<span class="spinner"></span> Signing out'; setTimeout(() => signOut("out"), 250); };
  yes.focus();
}
const isAdmin = () => store.get(ROLE_KEY) === "admin";
// Not signed in: go to the login page and remember where the player was going (e.g. a scanned QR code).
const herePage = () => location.pathname.split("/").pop() + location.search;
function requireLogin() { if (!getToken()) location.replace(`login.html?next=${encodeURIComponent(herePage())}`); }
// Only our own app pages are accepted as a "next" address, never another site.
function safeNext(next) {
  return next && /^[a-z]+\.html(\?[\w=&%.-]*)?$/i.test(next) && next !== "login.html" ? next : null;
}

async function api(path, { method = "GET", body, raw = false } = {}) {
  const headers = { Authorization: `Bearer ${getToken()}` };
  const json = body && !(body instanceof FormData);
  if (json) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method, headers, body: json ? JSON.stringify(body) : body });
  if (res.status === 401) { signOut("expired"); throw new Error("Please sign in again"); }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { const j = await res.json(); if (typeof j.detail === "string") msg = j.detail; } catch {}
    throw new Error(msg);
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

// Protected files cannot be used in <img src>, so fetch them with the token and use a blob URL.
async function blobUrl(path) {
  const res = await api(path, { raw: true });
  return URL.createObjectURL(await res.blob());
}
async function loadImage(img, path) {
  try { img.src = await blobUrl(path); } catch { img.alt = "Image not available"; }
}
async function openBlob(path, download) {
  const url = await blobUrl(path);
  if (download) { const a = document.createElement("a"); a.href = url; a.download = download; a.click(); }
  else window.open(url, "_blank");
}

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmtDate = iso => new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
const fmtDay = iso => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const prettyJoint = n => n.replace("_", " ").replace(/^./, c => c.toUpperCase());
const resultPage = a => `${a.mode === "video" ? "clip" : "analysis"}.html?id=${a.id}`;
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------------------------------------------------------------- icons (inline, stroke style)
const ICON = {
  home: '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>',
  video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  logout: '<path d="M9 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h4M16 17l5-5-5-5M21 12H9"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  body: '<circle cx="12" cy="4.5" r="2"/><path d="M12 7v7M7 10l5-2 5 2M9 21l3-7 3 7"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  chat: '<path d="M4 5h16v11H8l-4 4z"/><path d="M8 10h8M8 13h5"/>',
  doc: '<path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.3c2.2.7 3.5 2.8 3.5 5.7"/>',
  shield: '<path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  play: '<path d="M7 5l12 7-12 7z"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  compare: '<path d="M8 4v16M16 4v16M4 8h4M16 16h4M4 16h4M16 8h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trophy: '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8.5 20h7M10 17h4"/>',
  dumbbell: '<path d="M6 8v8M3.5 10v4M18 8v8M20.5 10v4M6 12h12"/>',
  quiz: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5v.6M12 16.8v.2"/>',
  chevron: '<path d="M6 9l6 6 6-6"/>',
  volume: '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>',
  mute: '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 9l5 6M22 9l-5 6"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  cube: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
  ghost: '<path d="M6 20V10a6 6 0 0 1 12 0v10l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5z"/><path d="M10 10h.01M14 10h.01"/>',
  flame: '<path d="M12 3c1 4 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3.5 2-4.5 0 2 1 3 2 3 0-3-1-5 1-8.5z"/>',
};
const icon = (n, cls = "") => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${ICON[n]}</svg>`;

const BALL = `<svg class="ball" viewBox="0 0 64 64"><defs><radialGradient id="bg1" cx="38%" cy="32%" r="72%"><stop offset="0" stop-color="#f04a62"/><stop offset=".5" stop-color="#c8102e"/><stop offset="1" stop-color="#6a0614"/></radialGradient><radialGradient id="bg1s" cx="70%" cy="78%" r="60%"><stop offset="0" stop-color="#000" stop-opacity=".28"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient></defs><circle cx="32" cy="32" r="30" fill="url(#bg1)"/><g class="seam"><path d="M28.6 2.4Q22.6 32 28.6 61.6" fill="none" stroke="#f3e9d2" stroke-width="1.7"/><path d="M35.4 2.4Q29.4 32 35.4 61.6" fill="none" stroke="#f3e9d2" stroke-width="1.7"/><path d="M24.9 6Q18.9 32 24.9 58" fill="none" stroke="#f3e9d2" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="1.4 2.8"/><path d="M39.1 6Q33.1 32 39.1 58" fill="none" stroke="#f3e9d2" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="1.4 2.8"/></g><circle cx="32" cy="32" r="30" fill="url(#bg1s)"/><ellipse cx="21" cy="17" rx="9" ry="5" fill="#fff" opacity=".28" transform="rotate(-35 21 17)"/></svg>`;

// ---------------------------------------------------------------- layout
const PLAYER_TIPS = [
  "Film side-on at hip height for the clearest posture report.",
  "Keep the whole body in frame so all 33 points can be tracked.",
  "One stroke per clip: trim from back-lift to follow-through.",
  "Good light helps: avoid filming straight into the sun.",
  "Compare with a reference clip to see where your movement differs.",
  "Ask the AI coach about any number you don't understand.",
];

const ADMIN_TIPS = [
  "Import summary.json after training to fill Model results.",
  "Add one clean reference clip per shot for movement comparison.",
  "Players with a falling plan % may need a check-in.",
  "Admin accounts manage the app; players analyse and train.",
];

// Each role has its own pages. Opening the other role's page sends you to your own home.
// The server enforces the same split (README.md, Roles); keep both in step.
const PLAYER_LINKS = [
  ["dashboard.html", "home", "Dashboard"], ["training.html", "dumbbell", "Training"], ["progress.html", "trophy", "Progress"],
  ["image.html", "camera", "Photo analysis"], ["video.html", "video", "Video analysis"], ["history.html", "clock", "History"],
];
const ADMIN_LINKS = [
  ["admin.html", "chart", "Overview"], ["players.html", "users", "All players"], ["models.html", "target", "Model results"],
  ["references.html", "video", "Reference clips"], ["users.html", "shield", "Users"],
];
const ADMIN_PAGES = ADMIN_LINKS.map(l => l[0]);
const homePage = () => (isAdmin() ? "admin.html" : "dashboard.html");

function sidebar(active) {
  if (isAdmin() !== ADMIN_PAGES.includes(active)) { location.replace(homePage()); throw new Error("redirect"); }
  const links = isAdmin() ? ADMIN_LINKS : PLAYER_LINKS;
  const TIPS = isAdmin() ? ADMIN_TIPS : PLAYER_TIPS;
  const nav = document.createElement("aside");
  nav.className = "sidebar";
  nav.innerHTML = `
    <a class="brand" href="${homePage()}" aria-label="SmartCricket home">${BALL}
      <div><b>SmartCricket</b><small>${isAdmin() ? "Admin console" : "AI batting coach"}</small></div></a>
    <nav class="nav" aria-label="Main">${links.map(([href, ic, label]) =>
      `<a href="${href}" class="${href === active ? "active" : ""}"${href === active ? ' aria-current="page"' : ""}><span class="nav-ic">${icon(ic)}</span><span class="lbl">${label}</span></a>`).join("")}</nav>
    <div class="side-tip" aria-live="polite">
      <div class="tip-head"><span class="tip-ball">${BALL.replace('class="ball"', 'class="tb"').replace(/bg1/g, "bgt")}</span>${isAdmin() ? "Admin tip" : "Coach's tip"}</div>
      <p id="tip-text"></p>
      <div class="tip-dots" id="tip-dots"></div>
    </div>`;
  document.querySelector(".layout").prepend(nav);

  // rotating tips
  let t = Math.floor(Math.random() * TIPS.length);
  const tipText = nav.querySelector("#tip-text"), dots = nav.querySelector("#tip-dots");
  dots.innerHTML = TIPS.map(() => "<i></i>").join("");
  const showTip = () => {
    tipText.classList.remove("in");
    setTimeout(() => {
      tipText.textContent = TIPS[t];
      dots.querySelectorAll("i").forEach((d, i) => d.classList.toggle("on", i === t));
      tipText.classList.add("in");
      t = (t + 1) % TIPS.length;
    }, reduceMotion ? 0 : 250);
  };
  showTip();
  setInterval(showTip, 6500);

  const cur = links.find(l => l[0] === active) || links[0];
  topbar(cur[2], cur[1]);
  smoothLinks();
  setTimeout(brandSelects);   // after the page script has created its <select> elements
}

// Profile, theme and sign-out in the top-right corner of every app page.
function topbar(pageLabel, pageIcon) {
  const name = store.get(NAME_KEY) || "Player";
  const bar = document.createElement("header");
  bar.className = "topbar";
  bar.innerHTML = `
    <div class="crumb"><span class="crumb-ic">${icon(pageIcon)}</span>
      <div><small>SmartCricket <span>/</span> ${esc(pageLabel)}</small><b>${esc(pageLabel)}</b></div></div>
    <div class="tb-right">
    <a class="lvl-pill" id="lvl-pill" href="progress.html" title="Your level and XP" hidden></a>
    <button class="icon-btn" id="theme" data-tip="Light / dark" aria-label="Toggle dark mode"></button>
    <div class="me"><div class="avatar">${esc(name.trim()[0] || "P").toUpperCase()}<i class="online"></i></div>
      <div class="who"><b>${esc(name)}</b><span class="role">${isAdmin() ? "Admin" : "Player"}</span></div></div>
    <button class="icon-btn" id="signout" aria-label="Sign out" data-tip="Sign out">${icon("logout")}</button>
    </div>`;
  document.querySelector("main").prepend(bar);
  const tb = bar.querySelector("#theme");
  const paint = () => { tb.innerHTML = icon(document.documentElement.dataset.theme === "dark" ? "sun" : "moon"); };
  paint();
  tb.onclick = () => { toggleTheme(); paint(); };
  bar.querySelector("#signout").onclick = e => confirmSignOut(e.currentTarget);
  if (!isAdmin()) refreshLevel();   // levels and XP belong to players only
}

// Level badge + XP bar in the top bar. Pages call it again after earning XP.
async function refreshLevel(st) {
  const pill = document.getElementById("lvl-pill");
  if (!pill) return;
  try { st = st || await api("/api/train/status"); } catch { return; }
  pill.hidden = false;
  pill.innerHTML = `<span class="lv-num">L${st.level}</span><span class="lv-txt"><b>${esc(st.level_name)}</b>
    <span class="lv-bar"><i style="width:${Math.round(st.progress * 100)}%"></i></span></span>
    <span class="lv-xp">${st.xp.total}<small>XP</small></span>${st.streak ? `<span class="lv-streak">${icon("flame")}${st.streak}</span>` : ""}`;
  return st;
}

// Floating "+15 XP" next to an element.
function xpFloat(el, n) {
  if (!el || reduceMotion) return;
  const r = el.getBoundingClientRect(), f = document.createElement("span");
  f.className = "xp-float"; f.textContent = `+${n} XP`;
  f.style.left = `${r.left + r.width / 2}px`; f.style.top = `${r.top}px`;
  document.body.append(f);
  setTimeout(() => f.remove(), 1200);
}

// Full-screen level-up moment with confetti.
function celebrate(level, name) {
  const o = document.createElement("div");
  o.className = "levelup";
  o.innerHTML = `<div class="lu-card"><div class="lu-ball">${BALL}</div><span>Level up</span><b>L${level} · ${esc(name)}</b>
    <p>New level reached. Keep the streak going!</p><button type="button">Let's go</button></div>`;
  if (!reduceMotion) for (let i = 0; i < 70; i++) {
    const c = document.createElement("i");
    c.className = "lu-conf";
    c.style.cssText = `left:${Math.random() * 100}%;background:${["#c8102e", "#0f5c3a", "#f3e9d2", "#1f9d55", "#f59e0b"][i % 5]};animation-delay:${Math.random() * .6}s;animation-duration:${1.8 + Math.random() * 1.6}s;transform:rotate(${Math.random() * 360}deg)`;
    o.append(c);
  }
  document.body.append(o);
  const close = () => { o.classList.add("out"); setTimeout(() => o.remove(), 300); };
  o.querySelector("button").onclick = close;
  o.onclick = e => { if (e.target === o) close(); };
}

function toggleTheme() {
  const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = t;
  store.set(THEME_KEY, t);
  document.dispatchEvent(new CustomEvent("themechange"));
}

// Fade the page out before following internal links.
function smoothLinks() {
  document.addEventListener("click", e => {
    const a = e.target.closest("a[href$='.html'], a[href*='.html?']");
    if (!a || a.target || e.metaKey || e.ctrlKey || reduceMotion) return;
    e.preventDefault();
    go(a.getAttribute("href"));
  });
}
function go(href) {
  if (reduceMotion) { location.href = href; return; }
  document.body.classList.add("leaving");
  setTimeout(() => { location.href = href; }, 180);
}

// Stagger the entrance of elements with .reveal.
function revealAll(root = document) {
  root.querySelectorAll(".reveal").forEach((el, i) => { el.style.animationDelay = `${60 + i * 70}ms`; });
}

// ---------------------------------------------------------------- toasts
function toast(msg, kind = "info") {
  let box = document.querySelector(".toasts");
  if (!box) { box = document.createElement("div"); box.className = "toasts"; document.body.append(box); }
  if ([...box.children].some(t => !t.classList.contains("hide") && t.textContent === msg)) return;   // never stack the same message
  const colors = { info: "var(--brand)", ok: "var(--pitch)", error: "var(--red)", warn: "var(--gold)" };
  const t = document.createElement("div");
  t.className = "toast";
  t.setAttribute("role", "status");
  t.innerHTML = `<span class="dot" style="background:${colors[kind]}"></span><span>${esc(msg)}</span>`;
  box.append(t);
  setTimeout(() => { t.classList.add("hide"); setTimeout(() => t.remove(), 300); }, 3800);
}

function alertHtml(kind, msg) {
  return `<div class="alert ${kind}">${icon(kind === "info" ? "info" : "alert")}<div>${esc(msg)}</div></div>`;
}

// ---------------------------------------------------------------- number animation
function countUp(el, to, { decimals = 0, duration = 1100, suffix = "" } = {}) {
  if (to == null || isNaN(to)) { el.textContent = "–"; return; }
  if (reduceMotion) { el.textContent = Number(to).toFixed(decimals) + suffix; return; }
  const start = performance.now();
  const step = now => {
    const t = Math.min(1, (now - start) / duration);
    const e = 1 - Math.pow(1 - t, 4);
    el.textContent = (to * e).toFixed(decimals) + suffix;
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

// ---------------------------------------------------------------- branded dropdown
// Replaces the browser's native select popup (which cannot be styled) with an on-brand list.
// The real <select> stays in the page, hidden, so .value, onchange, form reset and required still work.
function brandSelect(sel) {
  if (sel.dataset.branded) return;
  sel.dataset.branded = "1";
  const wrap = document.createElement("div");
  wrap.className = "bsel";
  if (sel.style.width) wrap.style.width = sel.style.width;
  if (sel.style.minWidth) wrap.style.minWidth = sel.style.minWidth;
  sel.parentNode.insertBefore(wrap, sel);
  wrap.append(sel);
  sel.classList.add("bsel-native");
  sel.tabIndex = -1;
  sel.required = false;   // a hidden required field would silently block submit; pages validate the value themselves
  const btn = document.createElement("button");
  btn.type = "button"; btn.className = "bsel-btn";
  btn.setAttribute("aria-haspopup", "listbox"); btn.setAttribute("aria-expanded", "false");
  const list = document.createElement("div");
  list.className = "bsel-list"; list.setAttribute("role", "listbox"); list.hidden = true;
  wrap.append(btn, list);
  let active = -1;

  const opts = () => [...sel.querySelectorAll("option")];
  const paintBtn = () => {
    const o = sel.options[sel.selectedIndex];
    const placeholder = !o || o.value === "";
    btn.innerHTML = `<span class="${placeholder ? "bsel-ph" : ""}">${esc(o ? o.textContent : "")}</span>${icon("chevron").replace("<svg", '<svg class="bsel-car"')}`;
    btn.disabled = sel.disabled || !opts().length;
  };
  const build = () => {
    let html = "", i = 0;
    for (const node of sel.children) {
      if (node.tagName === "OPTGROUP") {
        html += `<div class="bsel-grp">${esc(node.label)}</div>`;
        for (const o of node.children) html += item(o, i++);
      } else html += item(node, i++);
    }
    list.innerHTML = html;
    list.querySelectorAll(".bsel-opt").forEach(el => {
      el.onmousedown = e => e.preventDefault();
      el.onclick = () => choose(+el.dataset.i);
    });
    paintBtn();
  };
  const item = (o, i) => o.value === "" && sel.options.length > 1 ? "" : `<div class="bsel-opt${o.value === "" ? " ph" : ""}${o.selected ? " on" : ""}" role="option" data-i="${i}"
      aria-selected="${o.selected}">${esc(o.textContent)}${icon("check").replace("<svg", '<svg class="bsel-tick"')}</div>`;
  const highlight = i => {
    const els = list.querySelectorAll(".bsel-opt");
    els.forEach(e => e.classList.remove("hl"));
    active = Math.max(0, Math.min(els.length - 1, i));
    if (els[active]) { els[active].classList.add("hl"); els[active].scrollIntoView({ block: "nearest" }); }
  };
  const open = () => {
    if (btn.disabled) return;
    build();
    list.hidden = false; wrap.classList.add("open"); btn.setAttribute("aria-expanded", "true");
    const r = btn.getBoundingClientRect();
    wrap.classList.toggle("up", innerHeight - r.bottom < 280 && r.top > innerHeight - r.bottom);
    highlight(Math.max(0, domIdx(sel.selectedIndex)));
  };
  // list rows can skip the placeholder, so map between option index and row position
  const rows = () => [...list.querySelectorAll(".bsel-opt")];
  const domIdx = optIdx => rows().findIndex(el => +el.dataset.i === optIdx);
  const close = () => { list.hidden = true; wrap.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); };
  const choose = i => {
    const o = opts()[i];
    if (o && !o.disabled) {
      const changed = sel.selectedIndex !== i;
      sel.selectedIndex = i;
      if (changed) sel.dispatchEvent(new Event("change", { bubbles: true }));
    }
    paintBtn(); close(); btn.focus();
  };

  btn.onclick = () => (list.hidden ? open() : close());
  btn.onkeydown = e => {
    const n = opts().length;
    if (["ArrowDown", "ArrowUp"].includes(e.key)) {
      e.preventDefault();
      if (list.hidden) return open();
      highlight(active + (e.key === "ArrowDown" ? 1 : -1));
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (list.hidden) open(); else if (rows()[active]) choose(+rows()[active].dataset.i);
    } else if (e.key === "Escape") close();
    else if (e.key === "Tab") close();
    else if (e.key.length === 1 && n) {   // type a letter to jump
      const k = e.key.toLowerCase(), all = opts();
      const start = (list.hidden ? sel.selectedIndex : +(rows()[active]?.dataset.i ?? -1)) + 1;
      for (let j = 0; j < n; j++) {
        const idx = (start + j) % n;
        if (all[idx].value === "" && n > 1) continue;
        if (all[idx].textContent.trim().toLowerCase().startsWith(k)) { list.hidden ? choose(idx) : highlight(domIdx(idx)); break; }
      }
    }
  };
  document.addEventListener("mousedown", e => { if (!wrap.contains(e.target)) close(); });
  sel.addEventListener("change", paintBtn);
  sel.form?.addEventListener("reset", () => setTimeout(paintBtn));
  new MutationObserver(() => (list.hidden ? paintBtn() : build())).observe(sel, { childList: true, subtree: true, attributes: true });
  // keep the button in step when code sets sel.value directly
  const desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
  Object.defineProperty(sel, "value", { get() { return desc.get.call(this); }, set(v) { desc.set.call(this, v); paintBtn(); } });
  Object.defineProperty(sel, "hidden", { get() { return wrap.hidden; }, set(v) { wrap.hidden = v; } });
  paintBtn();
}
function brandSelects(root = document) { root.querySelectorAll("select.select").forEach(brandSelect); }

// ---------------------------------------------------------------- the one AI Coach (same look on every page)
function coachHeader(topic) {
  return `<div class="coach-head"><div class="bot">${icon("chat")}</div>
    <div style="flex:1;min-width:0"><b>AI Coach</b><div class="faint small"><span class="live"></span>Knows your plan and your results</div></div>
    <span class="coach-topic">${esc(topic)}</span></div>`;
}
const coachHtml = text => esc(text)
  .replace(/^(Measured:)/gm, '<span class="tagm">$1</span>')
  .replace(/^(General tip:)/gm, '<span class="tagg">$1</span>');

// ---------------------------------------------------------------- input quality strip (photo and clip results)
function qualityHtml(q) {
  if (!q) return "";
  const ic = { good: "check", warn: "alert", bad: "alert" };
  const tips = q.checks.filter(c => c.tip);
  return `<div class="qstrip q-${q.grade.toLowerCase()}">
    <div class="q-score"><b>${q.score}</b><span>${esc(q.grade)}</span></div>
    <div class="q-body"><div class="q-title">Input quality</div>
      <div class="q-checks">${q.checks.map(c => `<span class="q-c ${c.level}">${icon(ic[c.level])}${esc(c.label)}</span>`).join("")}</div>
      ${tips.length ? `<ul class="q-tips">${tips.map(c => `<li>${esc(c.tip)}</li>`).join("")}</ul>` : ""}</div></div>`;
}

// ---------------------------------------------------------------- 3D skeleton viewer (drag to rotate, scroll to zoom)
// world: 33 x [x, y, z] in metres from MediaPipe, centred on the hips, y pointing down. No library needed.
function viewer3d(canvas, getWorld) {
  const EDGES = [[11, 12], [11, 13], [13, 15], [12, 14], [14, 16], [11, 23], [12, 24], [23, 24], [23, 25], [25, 27], [24, 26], [26, 28], [27, 31], [28, 32], [27, 29], [28, 30], [0, 11], [0, 12]];
  const ctx = canvas.getContext("2d");
  let yaw = 0.6, pitch = 0.18, zoom = 1, drag = null, auto = !reduceMotion, raf;
  const fit = () => { const r = canvas.getBoundingClientRect(), d = devicePixelRatio || 1; canvas.width = r.width * d; canvas.height = r.height * d; };
  function project([x, y, z], W, H) {
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const x1 = x * cy - z * sy, z1 = x * sy + z * cy;          // turn around the vertical axis
    const y2 = y * cp - z1 * sp, z2 = y * sp + z1 * cp;         // tilt
    const f = 3.2 / (3.2 + z2), s = Math.min(W, H) * 0.42 * zoom;
    return [W / 2 + x1 * s * f, H * 0.5 + y2 * s * f, z2];
  }
  function draw() {
    const W = canvas.width, H = canvas.height, P = getWorld(), dark = document.documentElement.dataset.theme === "dark";
    ctx.clearRect(0, 0, W, H);
    // floor grid at foot level
    ctx.strokeStyle = dark ? "rgba(243,233,210,.08)" : "rgba(11,26,18,.07)"; ctx.lineWidth = 1;
    for (let i = -5; i <= 5; i++) for (const [a, b] of [[[i * .2, .95, -1], [i * .2, .95, 1]], [[-1, .95, i * .2], [1, .95, i * .2]]]) {
      const A = project(a, W, H), B = project(b, W, H); ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke();
    }
    if (!P) { ctx.fillStyle = dark ? "#b8c4bb" : "#87958b"; ctx.font = `${14 * (devicePixelRatio || 1)}px sans-serif`; ctx.textAlign = "center"; ctx.fillText("No 3D pose for this frame", W / 2, H / 2); return; }
    const pts = P.map(p => project(p, W, H)), d = devicePixelRatio || 1;
    const segs = EDGES.map(([a, b]) => [a, b, (pts[a][2] + pts[b][2]) / 2]).sort((x, y) => y[2] - x[2]);   // far first
    for (const [a, b, z] of segs) {
      const near = Math.max(0, Math.min(1, .5 - z));
      ctx.strokeStyle = a % 2 === 1 && b % 2 === 1 ? `rgba(31,157,85,${.45 + near * .55})` : a % 2 === 0 && b % 2 === 0 && a > 10 ? `rgba(200,16,46,${.45 + near * .55})` : `rgba(140,150,140,${.5 + near * .4})`;
      ctx.lineWidth = (5 + near * 4) * d; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(pts[a][0], pts[a][1]); ctx.lineTo(pts[b][0], pts[b][1]); ctx.stroke();
    }
    for (const i of [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]) {
      ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(pts[i][0], pts[i][1], (i === 0 ? 9 : 5) * d, 0, 7); ctx.fill();
      ctx.strokeStyle = "#0b1a12"; ctx.lineWidth = 1.5 * d; ctx.stroke();
    }
  }
  function tick() { if (auto) { yaw += 0.006; draw(); } raf = requestAnimationFrame(tick); }
  canvas.addEventListener("pointerdown", e => { drag = [e.clientX, e.clientY, yaw, pitch]; auto = false; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener("pointermove", e => {
    if (!drag) return;
    yaw = drag[2] + (e.clientX - drag[0]) * 0.01;
    pitch = Math.max(-1.2, Math.min(1.2, drag[3] + (e.clientY - drag[1]) * 0.01));
    draw();
  });
  canvas.addEventListener("pointerup", () => (drag = null));
  canvas.addEventListener("wheel", e => { e.preventDefault(); zoom = Math.max(.5, Math.min(2.5, zoom * (e.deltaY > 0 ? .92 : 1.08))); draw(); }, { passive: false });
  addEventListener("resize", () => { fit(); draw(); });
  document.addEventListener("themechange", draw);
  fit(); draw(); tick();
  return { draw, view(y, p) { yaw = y; pitch = p; auto = false; draw(); }, spin(on) { auto = on; } };
}

// A card with the 3D viewer, view buttons and a 2D-versus-3D angle table.
function threeDCard(el, getWorld, get2d, get3d) {
  el.innerHTML = `<div class="card-head" style="margin-bottom:10px"><div><span class="eyebrow-s">3D pose</span><h2>Your body in 3D</h2></div>
      <div class="v3-btns"><button type="button" data-v="side">Side</button><button type="button" data-v="front">Front</button><button type="button" data-v="top">Top</button><button type="button" data-v="spin">Spin</button></div></div>
    <canvas class="v3" aria-label="3D skeleton, drag to rotate"></canvas>
    <p class="faint small" style="margin:8px 0 14px">Drag to rotate, scroll to zoom. Estimated by MediaPipe from one camera.</p>
    <table class="data v3-table"><thead><tr><th>Joint</th><th>2D (camera view)</th><th>3D (body)</th><th>Gap</th></tr></thead><tbody></tbody></table>
    <p class="faint small" style="margin:10px 0 0">2D angles depend on where the camera stands; 3D angles do not. A large gap means the camera view was distorting the 2D number.</p>`;
  const v = viewer3d(el.querySelector("canvas"), getWorld);
  const VIEWS = { side: [Math.PI / 2, .1], front: [0, .1], top: [0, 1.15] };
  el.querySelectorAll(".v3-btns button").forEach(b => (b.onclick = () => b.dataset.v === "spin" ? v.spin(true) : v.view(...VIEWS[b.dataset.v])));
  const paint = () => {
    const a2 = get2d() || {}, a3 = get3d() || {};
    el.querySelector("tbody").innerHTML = Object.keys(a3).length ? Object.keys(a3).map(j => {
      const x = a2[j], y = a3[j], gap = x != null && y != null ? Math.abs(x - y) : null;
      return `<tr><td>${prettyJoint(j)}</td><td>${x == null ? "–" : x.toFixed(1) + "°"}</td><td><b>${y == null ? "–" : y.toFixed(1) + "°"}</b></td>
        <td>${gap == null ? "–" : `<span class="chip ${gap < 10 ? "ok" : gap < 25 ? "low" : "big"}">${gap.toFixed(0)}°</span>`}</td></tr>`;
    }).join("") : `<tr><td colspan="4" class="muted">No 3D angles for this view.</td></tr>`;
  };
  paint();
  return { redraw() { v.draw(); paint(); } };
}
