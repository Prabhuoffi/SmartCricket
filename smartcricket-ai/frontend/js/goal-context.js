// Carry an explicitly selected practice goal through training and retest uploads.
(function (root) {
  async function load(mode) {
    const raw = new URLSearchParams(location.search).get("goal");
    if (raw === null) return { goal: null, blocked: false };
    const banner = document.createElement("section");
    banner.className = "report-next";
    banner.style.margin = "0 0 20px";
    banner.setAttribute("aria-live", "polite");
    banner.setAttribute("aria-busy", "true");
    banner.innerHTML = '<p class="muted small">Loading your practice goal…</p>';
    (document.querySelector(".practice-path") || document.querySelector(".page-head"))?.after(banner);
    try {
      if (!/^[1-9]\d*$/.test(raw)) throw new Error("This practice goal link is invalid.");
      const payload = await api("/api/practice/goals");
      const goal = payload.goals.find(item => String(item.id) === raw);
      if (!goal) throw new Error("This practice goal could not be found. It may have been removed.");
      if (!goal.baseline) throw new Error("The baseline for this goal has been deleted. Create a new goal from an available report.");
      if (mode && goal.baseline.mode !== mode) {
        const capturePage = goal.baseline.mode === "video" ? "video.html" : "image.html";
        banner.innerHTML = `<div><b>Use the same capture type as your baseline</b><p class="muted small">This goal uses a ${goal.baseline.mode === "video" ? "video clip" : "photo"}. Take a matching retest to compare the measurements.</p></div>
          <a class="btn" href="${capturePage}?goal=${goal.id}">Capture a matching retest ${icon("arrow")}</a>`;
        return { goal, blocked: true };
      }
      const capturePage = goal.baseline.mode === "video" ? "video.html" : "image.html";
      const focus = prettyJoint(goal.focus_joint);
      banner.innerHTML = `<div><span class="eyebrow-s">${mode ? "Retest capture" : "Your practice goal"}</span><b style="display:block;margin-top:6px">${esc(goal.title)}</b>
        <p class="muted small">${esc(focus)}${goal.target_deg != null ? ` · chosen target ${goal.target_deg}°` : " · observe changes"}
          · Baseline: ${fmtDay(goal.baseline.created_at)}.</p>
        <p class="muted small">${mode ? "Match the baseline's camera position, body side, shot, and stroke phase. Your new capture will open beside the baseline; save the comparison to link this retest to your goal."
          : "Keep this goal in mind while following today's plan. Recovery guidance takes priority. When ready, capture a retest from the same view."}</p></div>
        <div class="guided-actions" style="margin:0">${mode ? "" : `<a class="btn" href="${capturePage}?goal=${goal.id}">${icon("camera")} Capture a retest</a>`}
          <a class="guided-secondary" href="practice.html?goal=${goal.id}">View goal ${icon("arrow")}</a></div>`;
      return { goal, blocked: false };
    } catch (error) {
      banner.innerHTML = `<div>${alertHtml("error", error.message)}</div><div class="guided-actions" style="margin:0">
        <button type="button" class="ghost" data-retry>Retry goal</button><a class="guided-secondary" href="practice.html">Open practice goals</a>
        ${mode ? `<a class="guided-secondary" href="${mode === "video" ? "video.html" : "image.html"}">Capture without a goal</a>` : ""}</div>`;
      banner.querySelector("[data-retry]").onclick = () => location.reload();
      return { goal: null, blocked: true };
    } finally { banner.setAttribute("aria-busy", "false"); }
  }

  function resultUrl(analysis, goal) {
    return goal ? `practice.html?goal=${goal.id}&retest=${analysis.id}` : resultPage(analysis);
  }

  root.PracticeGoalFlow = { load, resultUrl };
})(globalThis);
