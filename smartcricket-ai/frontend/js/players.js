(function (root) {
  "use strict";
  const SORT_KEYS = new Set(["name", "analyses", "last_active", "level", "streak", "plan_pct", "avg_visible"]);
  const finite = value => typeof value === "number" && Number.isFinite(value);
  const count = value => finite(value) && value >= 0 ? value : 0;
  const percentage = value => finite(value) && value >= 0 && value <= 100 ? value : null;

  function visiblePlayers(players, query, sortKey = "analyses", direction = -1) {
    const key = SORT_KEYS.has(sortKey) ? sortKey : "analyses";
    const order = direction === 1 ? 1 : -1;
    const term = String(query || "").trim().toLowerCase();
    return players.filter(p => `${p.name} ${p.email}`.toLowerCase().includes(term)).sort((a, b) => {
      const x = a[key], y = b[key];
      if (x == null && y == null) return String(a.name).localeCompare(String(b.name));
      if (x == null) return 1;
      if (y == null) return -1;
      return (x > y ? 1 : x < y ? -1 : 0) * order || String(a.name).localeCompare(String(b.name));
    });
  }

  function captureBreakdown(player) {
    const photos = count(player.photos), videos = count(player.videos), total = photos + videos;
    return { photos, videos, total, photo_share: total ? photos / total * 100 : 0, video_share: total ? videos / total * 100 : 0 };
  }

  function activityStats(players, now = Date.now()) {
    const active = players.filter(p => p.last_active && now - Date.parse(p.last_active) < 7 * 864e5).length;
    return { total: players.length, active, on_plan: players.filter(p => percentage(p.plan_pct) !== null && p.plan_pct >= 80).length,
      inactive: players.length - active };
  }

  root.SCPlayers = { visiblePlayers, captureBreakdown, activityStats };
  if (typeof module !== "undefined" && module.exports) module.exports = root.SCPlayers;
  if (typeof document === "undefined") return;

  requireLogin();
  sidebar("players.html");
  const $ = id => document.getElementById(id);
  const COLORS = ["#0f5c3a", "#c8102e", "#1f9d55", "#8f0b20", "#0a3d27", "#b58a3a"];
  const sheet = $("player-sheet");
  let players = [], sortKey = "analyses", sortDir = -1, loading = false, selectedId = null, lastTrigger = null;
  $("sico").innerHTML = icon("search");

  function ago(iso) {
    if (!iso || !Number.isFinite(Date.parse(iso))) return "Not yet";
    const minutes = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60000));
    return minutes < 1 ? "Just now" : minutes < 60 ? `${minutes} min ago` : minutes < 1440 ? `${Math.round(minutes / 60)} h ago` : `${Math.round(minutes / 1440)} d ago`;
  }
  const dateLabel = iso => iso && Number.isFinite(Date.parse(iso)) ? new Date(iso).toLocaleDateString(undefined, {day:"numeric",month:"short",year:"numeric"}) : "Not available";
  const avatar = player => `<span class="player-avatar" style="background:${COLORS[Math.abs(player.id) % COLORS.length]}">${esc(String(player.name || "?").trim()[0] || "?").toUpperCase()}</span>`;
  const number = value => count(value).toLocaleString();
  const progress = value => `<div class="bar-mini" aria-hidden="true"><i style="width:${value}%"></i></div>`;

  function render() {
    const list = visiblePlayers(players, $("search").value, sortKey, sortDir);
    $("roster-title").textContent = $("search").value.trim() ? `Players (${list.length} of ${players.length})` : `Players (${players.length})`;
    $("rows").innerHTML = list.map(player => {
      const streak = PlayerStreaks.presentation(player), plan = percentage(player.plan_pct);
      const visibility = finite(player.avg_visible) ? player.avg_visible.toFixed(1) : null;
      return `<tr data-player-id="${player.id}"${selectedId === player.id ? ' class="selected"' : ""}>
        <td><button type="button" class="player-open" aria-label="View ${esc(player.name)}" aria-haspopup="dialog" aria-controls="player-sheet">${avatar(player)}<span class="player-identity"><b title="${esc(player.name)}">${esc(player.name)}</b><small title="${esc(player.email)}">${esc(player.email)}</small></span><span class="player-open-arrow" aria-hidden="true">${icon("arrow")}</span></button></td>
        <td><b class="players-primary">${number(player.analyses)}</b><small class="players-secondary">${number(player.photos)} photos · ${number(player.videos)} videos</small></td>
        <td class="players-no-wrap">${esc(ago(player.last_active))}</td>
        <td><span class="chip info">L${player.level} ${esc(player.level_name)}</span><small class="players-secondary">${number(player.xp)} XP</small></td>
        <td class="players-no-wrap"><b class="players-primary${streak.active ? " players-streak-active" : ""}">${esc(streak.current)}</b><small class="players-secondary">${esc(streak.best)}</small></td>
        <td>${plan === null ? '<span class="muted">No plan</span>' : `<b class="players-primary">${plan}%</b>${progress(plan)}`}</td>
        <td>${visibility === null ? '<span class="muted">—</span>' : `<b class="players-primary">${visibility}</b><small class="players-secondary">of 33 points</small>`}</td>
        <td class="players-top-shot">${esc(player.top_shot || "—")}</td>
      </tr>`;
    }).join("") || `<tr><td colspan="8" class="players-empty muted">${players.length ? "No players match your search." : "No players yet."}</td></tr>`;
  }

  function openPlayer(id, trigger) {
    const player = players.find(value => value.id === id);
    if (!player) return;
    selectedId = id;
    lastTrigger = trigger;
    const streak = PlayerStreaks.presentation(player), breakdown = captureBreakdown(player), plan = percentage(player.plan_pct);
    const metric = (label, value) => `<div class="player-sheet-metric"><span>${label}</span><b>${esc(value)}</b></div>`;
    $("sheet-body").innerHTML = `<div class="player-sheet-identity">${avatar(player)}<div><h2 id="sheet-title">${esc(player.name)}</h2><p id="sheet-email">${esc(player.email)}</p></div></div>
      <div class="player-sheet-metrics">${metric("Analyses", number(player.analyses))}${metric("Current streak", streak.current)}${metric("Best streak", streak.best ? streak.best.replace("Best: ", "") : "Not available")}${metric("Plan completion · 7d", plan === null ? "No plan" : `${plan}%`)}</div>
      <section class="player-sheet-section"><h3>Analysis breakdown</h3><div class="player-capture-counts"><div><p><span>Photos</span><b>${number(breakdown.photos)}</b></p>${progress(breakdown.photo_share)}</div><div><p><span>Videos</span><b>${number(breakdown.videos)}</b></p>${progress(breakdown.video_share)}</div></div></section>
      <section class="player-sheet-section"><h3>Practice & progress</h3><dl><dt>Level</dt><dd><span class="chip info">L${player.level} ${esc(player.level_name)}</span></dd><dt>Total XP</dt><dd>${number(player.xp)}</dd><dt>7-day plan</dt><dd>${plan === null ? "No plan yet" : `${plan}% completed`}</dd></dl><details class="player-sheet-help"><summary>How streaks work</summary><p>Consecutive days with a capture, check-in, completed drill or saved live session count toward a streak. Practising yesterday keeps it active through today.</p></details></section>
      <section class="player-sheet-section"><h3>Capture summary</h3><dl><dt>Average visibility</dt><dd>${finite(player.avg_visible) ? `${player.avg_visible.toFixed(1)} / 33 points` : "Not available"}</dd><dt>Most common shot</dt><dd>${esc(player.top_shot || "Not available")}</dd></dl></section>
      <section class="player-sheet-section"><h3>Account</h3><dl><dt>Joined</dt><dd>${esc(dateLabel(player.joined))}</dd><dt>Last active</dt><dd>${esc(ago(player.last_active))}</dd></dl></section>`;
    document.querySelectorAll("#rows tr[data-player-id]").forEach(row => row.classList.toggle("selected", Number(row.dataset.playerId) === id));
    document.body.classList.add("players-sheet-open");
    sheet.showModal();
    $("sheet-body").scrollTop = 0;
  }

  $("rows").addEventListener("click", event => {
    const row = event.target.closest("tr[data-player-id]");
    if (row) openPlayer(Number(row.dataset.playerId), row.querySelector(".player-open"));
  });
  $("sheet-close").addEventListener("click", () => sheet.close());
  sheet.addEventListener("click", event => {
    const rect = sheet.getBoundingClientRect();
    if (event.target === sheet && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) sheet.close();
  });
  sheet.addEventListener("close", () => {
    document.body.classList.remove("players-sheet-open");
    selectedId = null;
    document.querySelector("#rows tr.selected")?.classList.remove("selected");
    if (lastTrigger?.isConnected) lastTrigger.focus({preventScroll:true});
  });
  $("search").addEventListener("input", render);
  document.querySelectorAll("[data-sort]").forEach(button => button.addEventListener("click", () => {
    const key = button.dataset.sort;
    sortDir = sortKey === key ? -sortDir : key === "name" ? 1 : -1;
    sortKey = key;
    document.querySelectorAll("[data-sort]").forEach(other => {
      other.querySelector(".sort-arrow").textContent = other === button ? sortDir === 1 ? "↑" : "↓" : "";
      other.closest("th").setAttribute("aria-sort", other === button ? sortDir === 1 ? "ascending" : "descending" : "none");
    });
    render();
  }));

  async function load() {
    if (loading) return;
    loading = true;
    $("players-status").hidden = false;
    $("players-status").textContent = "Loading players…";
    try {
      const result = await api("/api/admin/overview");
      players = result.players;
      const stats = activityStats(players);
      $("chips").innerHTML = [["users",stats.total,"players"],["flame",stats.active,"active this week"],["check",stats.on_plan,"on track"],["clock",stats.inactive,"inactive"]]
        .map(([name,value,label]) => `<span class="pl-chip">${icon(name)}<b>${value}</b> ${label}</span>`).join("");
      $("search").disabled = false;
      render();
      $("players-status").hidden = true;
      $("players-roster").hidden = false;
      revealAll();
    } catch (error) {
      $("players-status").innerHTML = `${alertHtml("error", error.message)}<button type="button" class="ghost" id="players-retry">Try again</button>`;
      $("players-retry").addEventListener("click", load);
    } finally { loading = false; }
  }
  load();
})(globalThis);
