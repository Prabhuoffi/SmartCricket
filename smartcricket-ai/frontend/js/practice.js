(function (root) {
  "use strict";

  const JOINTS = ["left_elbow", "right_elbow", "left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee"];
  const degrees = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 180;
  const captureName = capture => capture.session_label || capture.original_name || `Capture ${capture.id}`;
  const frameCount = capture => capture?.mode === "video" ? Math.min(64, Math.max(0,
    Math.floor(capture.summary?.angles_seq?.length || Number(capture.summary?.frames) || 0))) : 0;
  const defaultFrame = capture => Math.max(0, Math.min(frameCount(capture) - 1, Number(capture?.summary?.key_frame) || 0));

  function retestCandidates(history, baseline) {
    if (!baseline) return [];
    const baselineTime = Date.parse(baseline.created_at);
    return history.filter(capture => capture.id !== baseline.id && capture.mode === baseline.mode &&
      Number.isFinite(baselineTime) && Date.parse(capture.created_at) >= baselineTime);
  }

  function measuredJoints(capture, frame, minVisibility = .5) {
    if (!capture || (capture.mode === "image" && capture.summary?.detected === false)) return {};
    const values = capture.mode === "video" ? capture.summary?.angles_seq?.[frame] || {} : capture.angles || {};
    return Object.fromEntries(JOINTS.flatMap(joint => {
      const value = values[joint];
      const degree = typeof value === "object" && value !== null ? value.deg : value;
      const visibility = typeof value === "object" && value !== null ? value.visibility : null;
      const visible = visibility == null || (typeof visibility === "number" && Number.isFinite(visibility) &&
        visibility >= minVisibility && visibility <= 1);
      return degrees(degree) && visible ? [[joint, degree]] : [];
    }));
  }

  function selectedFrame(capture, displayed) {
    if (capture?.mode !== "video") return null;
    const frame = Number(displayed) - 1;
    if (!Number.isInteger(frame) || frame < 0 || frame >= frameCount(capture))
      throw new Error(`Choose a frame between 1 and ${frameCount(capture)}.`);
    return frame;
  }

  function queryFor(baseline, retest, baselineFrame, retestFrame, sameSetup, goalId) {
    const query = new URLSearchParams({ baseline_id: baseline.id, retest_id: retest.id, same_setup: Boolean(sameSetup) });
    if (baseline.mode === "video") query.set("baseline_frame", baselineFrame);
    if (retest.mode === "video") query.set("retest_frame", retestFrame);
    if (goalId) query.set("goal_id", goalId);
    return query.toString();
  }

  root.SCPractice = { retestCandidates, measuredJoints, selectedFrame, queryFor, captureName, frameCount, defaultFrame };
  if (typeof module !== "undefined" && module.exports) module.exports = root.SCPractice;
  if (typeof document === "undefined") return;

  requireLogin();
  sidebar("practice.html");
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const state = { history: [], goals: [], joints: [], baseline: null, retest: null, selectedGoal: null,
    comparison: null, comparisonQuery: null, generation: 0, comparisonRequest: 0, comparing: false, mutating: false, loading: false,
    minVisibility: .5 };
  const cache = new Map();
  const urls = new Set();
  const labels = () => Object.fromEntries(state.joints.map(joint => [joint.key, joint.label]));
  const number = value => `${Number(value).toFixed(1)}°`;
  const sign = value => `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(1)}°`;
  const setMessage = (id, message, kind = "error") => { $(id).innerHTML = message ? alertHtml(kind, message) : ""; };
  const selectedGoal = () => state.goals.find(goal => goal.id === state.selectedGoal) || null;
  const option = (capture, selected) => `<option value="${capture.id}"${capture.id === selected ? " selected" : ""}>${esc(captureName(capture))} · ${esc(fmtDate(capture.created_at))} · ${capture.mode === "video" ? "Clip" : "Photo"} · #${capture.id}</option>`;

  function forgetComparison() {
    state.comparisonRequest++;
    state.comparing = false;
    state.comparison = null;
    state.comparisonQuery = null;
    $("comparison-result").hidden = true;
    setMessage("comparison-error", "");
    setMessage("comparison-save-status", "");
    $("compare-button").textContent = "Compare measurements";
    controls();
  }

  function controls() {
    const hasPair = Boolean(state.baseline && state.retest);
    $("capture-previews").hidden = !state.baseline;
    $("setup-confirmation").hidden = !hasPair;
    $("compare-button").disabled = !hasPair || state.loading || state.mutating || state.comparing;
    $("baseline-select").disabled = state.mutating;
    $("retest-select").disabled = !state.baseline || state.loading || state.mutating ||
      ![...$("retest-select").options].some(option => option.value && !option.disabled);
    $("same-setup").disabled = !hasPair || state.loading || state.mutating;
    $("baseline-frame").disabled = state.mutating;
    $("retest-frame").disabled = state.mutating;
    const hasJoints = $("goal-joint").options.length > 1;
    $("goal-joint").disabled = !hasJoints || state.loading || state.mutating;
    $("create-goal").disabled = !state.baseline || !hasJoints || state.loading || state.mutating;
    document.querySelectorAll("#goal-form input, #goal-form textarea").forEach(field => {
      field.disabled = !state.baseline || state.loading || state.mutating;
    });
    $("download-comparison").disabled = !state.comparison || state.mutating;
    $("save-goal-comparison").hidden = !selectedGoal();
    $("save-goal-comparison").disabled = !state.comparison || state.mutating || selectedGoal()?.status !== "active";
    document.querySelectorAll("#goal-list button").forEach(button => {
      button.disabled = state.mutating || button.dataset.unavailable === "true";
    });
    $("comparison-hint").textContent = state.loading ? "Loading selected captures…" : hasPair
      ? "Only joints measured in both captures will be compared." : "Select two captures to compare.";
  }

  function showGoalContext() {
    const goal = selectedGoal();
    const box = $("goal-context");
    box.hidden = !goal;
    if (!goal) return;
    const focus = labels()[goal.focus_joint] || goal.focus_joint.replaceAll("_", " ");
    box.innerHTML = `<div><div><span class="eyebrow-s">Selected practice goal</span><h2>${esc(goal.title)}</h2></div>
      <button type="button" class="ghost" id="clear-goal">Compare without a goal</button></div>
      <p>${esc(focus)}${goal.target_deg != null ? ` · Personal target ${number(goal.target_deg)}` : ""}${goal.due_date ? ` · Review ${esc(goal.due_date)}` : ""}</p>
      ${!goal.baseline ? alertHtml("warn", "The baseline capture was deleted. Create a new goal from an available capture to continue.") : ""}
      ${goal.status !== "active" ? `<p>This goal is ${esc(goal.status)}. Reopen it from Saved practice goals to save another retest.</p>` : ""}
      <div class="practice-actions">${goal.baseline && goal.status === "active" ? `<a class="btn ghost" href="training.html?goal=${goal.id}">${icon("dumbbell")} Practise this goal</a>
        <a class="btn" href="${goal.baseline.mode === "video" ? "video" : "image"}.html?goal=${goal.id}">${icon("upload")} Capture a retest</a>`
        : goal.baseline ? '<button type="button" class="ghost" id="reopen-selected-goal">Reopen this goal</button>'
        : '<button type="button" class="ghost" id="new-goal-baseline">Choose another baseline</button>'}</div>
      <div id="goal-target-detail" class="practice-goal-target" hidden></div>`;
    $("clear-goal").onclick = () => {
      state.selectedGoal = null;
      showGoalContext(); renderGoals(); forgetComparison(); updateAddress();
    };
    $("reopen-selected-goal")?.addEventListener("click", () => {
      if (state.mutating) return;
      $("goal-filter").value = "all"; renderGoals();
      document.querySelector(`#goal-list [data-goal-id="${goal.id}"] [data-action="reopen"]`)?.click();
    });
    $("new-goal-baseline")?.addEventListener("click", () => { $("clear-goal").click(); $("choose-goal-baseline").click(); });
    paintTarget();
  }

  function paintTarget() {
    const goal = selectedGoal(), box = $("goal-target-detail");
    if (!box) return;
    const row = state.comparison?.rows.find(item => item.joint === goal?.focus_joint);
    box.hidden = !row || goal.target_deg == null;
    if (box.hidden) return;
    const before = Math.abs(row.baseline_deg - goal.target_deg), after = Math.abs(row.retest_deg - goal.target_deg);
    box.textContent = `Distance from your chosen ${number(goal.target_deg)} target: baseline ${number(before)}, retest ${number(after)}. This describes the measurement relative to your target, not a technique rating.`;
  }

  function renderGoals() {
    const filter = $("goal-filter").value;
    const goals = state.goals.filter(goal => filter === "all" || goal.status === filter);
    $("goal-count").textContent = `${state.goals.filter(goal => goal.status === "active").length} active`;
    if (!goals.length) {
      $("goal-list").innerHTML = `<div class="practice-empty">${icon("target")}<h3>${state.goals.length ? "No goals in this view" : "Start with one personal focus"}</h3><p>${state.goals.length ? "Choose another filter to see your saved goals." : "Choose a baseline below, name your goal, and return with a new capture after practice."}</p></div>`;
      return;
    }
    $("goal-list").innerHTML = goals.map(goal => {
      const focus = labels()[goal.focus_joint] || goal.focus_joint.replaceAll("_", " ");
      const active = goal.status === "active", missing = !goal.baseline;
      return `<article class="practice-goal${state.selectedGoal === goal.id ? " selected" : ""}" data-goal-id="${goal.id}">
        <div class="practice-goal-title"><h3>${esc(goal.title)}</h3><span class="chip ${active ? "info" : goal.status === "completed" ? "ok" : "off"}">${esc(goal.status)}</span></div>
        <p><b>${esc(focus)}</b>${goal.target_deg != null ? ` · Target ${number(goal.target_deg)}` : ""}</p>
        <p>${missing ? "Baseline capture deleted" : `Baseline: ${esc(captureName(goal.baseline))}`}${goal.baseline?.mode === "video" ? ` · frame ${(goal.baseline_frame ?? 0) + 1}` : ""}<br>
          ${goal.retest ? `Retest: ${esc(captureName(goal.retest))}` : "Retest not yet saved"}${goal.due_date ? `<br>Review date: ${esc(goal.due_date)}` : ""}</p>
        ${goal.notes ? `<p class="practice-goal-notes">${esc(goal.notes)}</p>` : ""}
        <div class="practice-actions"><button class="ghost" type="button" data-action="view">${goal.retest ? "View comparison" : "Open goal"}</button>
          ${active && !missing ? `<a class="btn ghost" href="training.html?goal=${goal.id}">Practise</a><a class="btn ghost" href="${goal.baseline.mode === "video" ? "video" : "image"}.html?goal=${goal.id}">Capture retest</a>` : ""}</div>
        <div class="practice-actions practice-goal-secondary">${active
          ? `<button class="ghost" type="button" data-action="complete"${!goal.retest || missing ? ' disabled data-unavailable="true" title="Save a valid retest before marking this goal complete"' : ""}>Mark complete</button><button class="ghost" type="button" data-action="archive">Archive</button>`
          : `<button class="ghost" type="button" data-action="reopen">Reopen</button>`}
          <button class="danger" type="button" data-action="delete">Delete goal</button></div>
        <div class="practice-goal-feedback" role="status" aria-live="polite"></div></article>`;
    }).join("");
    $("goal-list").querySelectorAll("button[data-action]").forEach(button => button.onclick = () => goalAction(button));
    controls();
  }

  async function goalAction(button) {
    if (state.mutating) return;
    const card = button.closest("[data-goal-id]"), goal = state.goals.find(item => item.id === Number(card.dataset.goalId));
    if (button.dataset.action === "view") {
      await openGoal(goal);
      $("compare-heading").scrollIntoView({ behavior: reduceMotion ? "instant" : "smooth", block: "start" });
      return;
    }
    if (button.dataset.action === "delete" && !confirm("Delete this practice goal? Your captures and reports will remain in History.")) return;
    state.mutating = true; controls();
    try {
      if (button.dataset.action === "delete") {
        await api(`/api/practice/goals/${goal.id}`, { method: "DELETE" });
        state.goals = state.goals.filter(item => item.id !== goal.id);
        if (state.selectedGoal === goal.id) { state.selectedGoal = null; forgetComparison(); }
      } else {
        const status = { complete: "completed", archive: "archived", reopen: "active" }[button.dataset.action];
        replaceGoal(await api(`/api/practice/goals/${goal.id}`, { method: "PATCH", body: { status } }));
      }
      renderGoals(); showGoalContext(); updateAddress();
      toast(button.dataset.action === "delete" ? "Practice goal deleted" : "Practice goal updated", "ok");
    } catch (error) {
      card.querySelector(".practice-goal-feedback").innerHTML = alertHtml("error", error.message);
    } finally { state.mutating = false; controls(); }
  }

  function replaceGoal(goal) {
    const index = state.goals.findIndex(item => item.id === goal.id);
    if (index < 0) state.goals.unshift(goal); else state.goals[index] = goal;
  }

  async function detail(id) {
    if (!cache.has(id)) cache.set(id, api(`/api/analyses/${id}`).catch(error => { cache.delete(id); throw error; }));
    return cache.get(id);
  }

  function updateAddress() {
    const query = new URLSearchParams();
    if (state.selectedGoal) query.set("goal", state.selectedGoal);
    if (state.baseline) query.set("baseline", state.baseline.id);
    if (state.retest) query.set("retest", state.retest.id);
    history.replaceState(null, "", `practice.html${query.size ? "?" + query : ""}`);
  }

  function populateRetests(baseline, requestedRetest = null) {
    const eligible = retestCandidates(state.history, baseline);
    $("retest-select").innerHTML = `<option value="">${baseline ? eligible.length ? "Choose a newer capture" : "No newer matching captures" : "Choose a baseline first"}</option>` + eligible.map(capture => option(capture, Number(requestedRetest))).join("");
    $("retest-help").textContent = !baseline ? "Choose a baseline to find newer captures of the same type." : eligible.length
      ? `${eligible.length} newer ${baseline.mode === "video" ? "clip" : "photo"}${eligible.length === 1 ? "" : "s"} available. Match the same shot and capture setup.`
      : `No newer ${baseline.mode === "video" ? "clips" : "photos"} yet. Practise, then use ${selectedGoal() ? "Capture a retest above" : "New photo or New clip"} to add one.`;
    return eligible;
  }

  async function chooseCaptures({ baselineId, retestId, baselineFrame, retestFrame, sameSetup = false } = {}) {
    const generation = ++state.generation;
    state.loading = true;
    state.baseline = null; state.retest = null;
    $("same-setup").checked = false;
    forgetComparison();
    renderCapture("baseline", null); renderCapture("retest", null);
    $("baseline-select").value = baselineId || "";
    const brief = state.history.find(item => item.id === Number(baselineId));
    const eligible = populateRetests(brief, retestId);
    try {
      if (!brief) {
        if (baselineId) throw new Error("This baseline capture is no longer available. Choose a capture from History to create a new goal.");
        return;
      }
      if (retestId && !eligible.some(item => item.id === Number(retestId)))
        throw new Error("This retest is unavailable, older than the baseline, or a different capture type. Choose a newer matching capture.");
      const [baseline, retest] = await Promise.all([detail(brief.id), retestId ? detail(Number(retestId)) : Promise.resolve(null)]);
      if (generation !== state.generation) return;
      state.baseline = baseline; state.retest = retest;
      renderCapture("baseline", baseline, baselineFrame, generation);
      renderCapture("retest", retest, retestFrame, generation);
      $("same-setup").checked = Boolean(sameSetup && retest);
      populateGoalJoints(); updateAddress();
    } catch (error) {
      if (generation === state.generation) setMessage("practice-message", error.message);
    } finally {
      if (generation === state.generation) { state.loading = false; populateGoalJoints(); controls(); }
    }
  }

  function renderCapture(side, capture, requestedFrame, generation = state.generation) {
    const image = $(`${side}-preview`), note = $(`${side}-preview-note`), frame = $(`${side}-frame`);
    if (image.dataset.blobUrl) { URL.revokeObjectURL(image.dataset.blobUrl); urls.delete(image.dataset.blobUrl); delete image.dataset.blobUrl; }
    image.hidden = true; image.removeAttribute("src");
    note.hidden = false;
    $(`${side}-meta`).innerHTML = "";
    $(`${side}-frame-wrap`).hidden = capture?.mode !== "video";
    if (!capture) { note.textContent = side === "baseline" ? "Select a saved capture to begin." : "Your newer capture will appear here."; return; }
    const count = frameCount(capture);
    const index = Number.isInteger(requestedFrame) && requestedFrame >= 0 && requestedFrame < count ? requestedFrame : defaultFrame(capture);
    if (capture.mode === "video") {
      frame.max = count; frame.value = index + 1;
      $(`${side}-frame-help`).textContent = `Frame 1–${count}. Choose the same movement phase in both clips; frames are not automatically aligned.`;
    }
    const quality = capture.summary?.quality;
    $(`${side}-meta`).innerHTML = `<b>${esc(captureName(capture))}</b><span>${esc(fmtDate(capture.created_at))}</span>
      <span>${capture.mode === "video" ? "Video frame" : "Photo posture"}</span><span>${quality?.grade ? `Capture quality: ${esc(quality.grade)}` : "Capture quality not recorded"}</span>
      <a href="${resultPage(capture)}">Open original report →</a>`;
    note.textContent = "Loading capture preview…";
    image.alt = `${side === "baseline" ? "Baseline" : "Retest"} capture; tracked skeleton shown when available`;
    const paths = [`/api/practice/captures/${capture.id}/preview${capture.mode === "video" ? `?frame=${index}` : ""}`];
    loadPreview(image, note, paths, generation);
  }

  async function loadPreview(image, note, paths, generation) {
    for (const path of paths) {
      try {
        const url = await blobUrl(path);
        if (generation !== state.generation || !image.isConnected) { URL.revokeObjectURL(url); return; }
        urls.add(url);
        image.dataset.blobUrl = url;
        image.onload = () => { if (generation === state.generation) { image.hidden = false; note.hidden = true; } urls.delete(url); URL.revokeObjectURL(url); };
        image.onerror = () => { if (generation === state.generation) { image.hidden = true; note.hidden = false; note.textContent = "Preview unavailable. The saved measurements can still be compared."; } urls.delete(url); URL.revokeObjectURL(url); };
        image.src = url;
        return;
      } catch (_) { if (generation !== state.generation) return; }
    }
    note.textContent = "Preview unavailable. The saved measurements can still be compared.";
  }

  function frames() {
    return { baseline: selectedFrame(state.baseline, $("baseline-frame").value), retest: selectedFrame(state.retest, $("retest-frame").value) };
  }

  function populateGoalJoints() {
    let current = $("goal-joint").value;
    let available = {};
    try { available = measuredJoints(state.baseline, frames().baseline, state.minVisibility); } catch (_) {}
    $("goal-joint").innerHTML = '<option value="">Choose a measurable joint</option>' + state.joints.filter(joint => Object.hasOwn(available, joint.key))
      .map(joint => `<option value="${joint.key}">${esc(joint.label)} · ${number(available[joint.key])}</option>`).join("");
    if (Object.hasOwn(available, current)) $("goal-joint").value = current;
    const canCreate = Boolean(state.baseline && Object.keys(available).length);
    $("goal-form").hidden = !canCreate;
    $("goal-form-empty").hidden = canCreate;
    $("goal-baseline-note").hidden = !canCreate;
    $("goal-form-empty-title").textContent = state.baseline ? "Choose a capture with clear joint measurements" : "Choose a baseline to get started";
    $("goal-form-empty-text").textContent = state.baseline
      ? "Try a different frame or a clearer capture, then choose a joint for your goal."
      : "Your goal will use a joint measured in that photo or clip.";
    $("goal-baseline-note").textContent = !state.baseline ? "Select a baseline capture above to create a goal." : !Object.keys(available).length
      ? "No joints were clearly measured in this capture or frame. Choose a different frame or capture a clearer photo before creating a goal."
      : `Using ${captureName(state.baseline)}${state.baseline.mode === "video" ? `, frame ${$("baseline-frame").value}` : ""} as your baseline. Choose a joint measured in this capture.`;
    controls();
  }

  async function openGoal(goal, retestOverride) {
    state.selectedGoal = goal.id;
    setMessage("practice-message", "");
    if ($( "goal-filter").value !== "all" && $("goal-filter").value !== goal.status) $("goal-filter").value = "all";
    renderGoals(); showGoalContext();
    const generation = state.generation + 1;
    await chooseCaptures({ baselineId: goal.baseline?.id, retestId: retestOverride ?? goal.retest?.id,
      baselineFrame: goal.baseline_frame, retestFrame: retestOverride ? undefined : goal.retest_frame,
      sameSetup: !retestOverride && goal.same_setup });
    if (state.selectedGoal !== goal.id || state.generation !== generation) return;
    if (!goal.baseline) setMessage("practice-message", "This goal's baseline was deleted. Create a new goal from an available capture.", "warn");
    if (retestOverride && state.retest) setMessage("practice-message", "Your retest is ready. Match the capture setup, compare the measurements, then save the retest to this goal.", "info");
    else if (state.baseline && state.retest) await compare();
  }

  async function compare() {
    if (!state.baseline || !state.retest || state.loading || state.mutating || state.comparing) return;
    const request = ++state.comparisonRequest;
    const generation = state.generation;
    state.comparing = true;
    $("compare-button").disabled = true;
    $("compare-button").textContent = "Comparing measurements…";
    setMessage("comparison-error", "");
    try {
      const frame = frames();
      const query = queryFor(state.baseline, state.retest, frame.baseline, frame.retest, $("same-setup").checked);
      const result = await api(`/api/practice/compare?${query}`);
      if (request !== state.comparisonRequest || generation !== state.generation) return;
      state.comparison = result;
      state.comparisonQuery = query;
      paintComparison();
    } catch (error) {
      if (request === state.comparisonRequest && generation === state.generation) setMessage("comparison-error", error.message);
    } finally {
      if (request === state.comparisonRequest && generation === state.generation) { state.comparing = false; $("compare-button").textContent = "Compare measurements"; controls(); }
    }
  }

  function paintComparison() {
    const result = state.comparison, goal = selectedGoal();
    $("comparison-result").hidden = false;
    $("comparison-status").className = `chip ${result.comparable ? "ok" : "low"}`;
    $("comparison-status").textContent = result.comparable ? "Setup checks passed" : "Exploratory comparison";
    $("comparison-note").textContent = result.note;
    $("comparison-checks").innerHTML = result.checks.map(check => `<div class="practice-check ${esc(check.level)}">${icon(check.level === "good" ? "check" : "info")}<div><b>${esc(check.label)}</b>${check.detail ? `<p>${esc(check.detail)}</p>` : ""}</div></div>`).join("");
    $("comparison-table").querySelector("tbody").innerHTML = result.rows.map(row => `<tr${goal?.focus_joint === row.joint ? ' class="practice-focus"' : ""}><th scope="row">${esc(row.label)}</th><td>${number(row.baseline_deg)}</td><td>${number(row.retest_deg)}</td><td class="practice-delta">${sign(row.change_deg)}</td></tr>`).join("");
    $("omitted-joints").hidden = !result.omitted.length;
    $("omitted-list").innerHTML = result.omitted.map(joint => `<li><b>${esc(joint.label)}</b>: ${esc(joint.reason)}</li>`).join("");
    $("save-goal-comparison").textContent = goal?.retest?.id === state.retest.id ? "Update saved comparison" : "Save retest to this goal";
    paintTarget(); controls();
  }

  $("baseline-select").onchange = () => {
    state.selectedGoal = null; showGoalContext(); renderGoals(); setMessage("practice-message", "");
    setMessage("goal-form-status", "");
    chooseCaptures({ baselineId: Number($("baseline-select").value) || null });
  };
  $("retest-select").onchange = () => {
    setMessage("practice-message", "");
    let baselineFrame; try { baselineFrame = frames().baseline; } catch (_) {}
    chooseCaptures({ baselineId: Number($("baseline-select").value), retestId: Number($("retest-select").value) || null, baselineFrame });
  };
  ["baseline", "retest"].forEach(side => {
    $(`${side}-frame`).oninput = () => { forgetComparison(); $("same-setup").checked = false; populateGoalJoints(); };
    $(`${side}-frame`).onchange = () => {
      try {
        const frame = frames();
        const generation = ++state.generation;
        renderCapture("baseline", state.baseline, frame.baseline, generation);
        renderCapture("retest", state.retest, frame.retest, generation);
        populateGoalJoints(); controls();
      } catch (error) { setMessage("comparison-error", error.message); }
    };
  });
  $("same-setup").onchange = forgetComparison;
  $("compare-button").onclick = compare;
  $("goal-filter").onchange = renderGoals;
  $("choose-goal-baseline").onclick = () => {
    $("compare-heading").scrollIntoView({ behavior: reduceMotion ? "instant" : "smooth", block: "start" });
    $("baseline-select").focus({ preventScroll: true });
  };

  $("goal-form").onsubmit = async event => {
    event.preventDefault();
    if (state.mutating || !state.baseline) return;
    setMessage("goal-form-status", "");
    const title = $("goal-title").value.trim(), joint = $("goal-joint").value;
    if (!title || !joint) return setMessage("goal-form-status", "Enter a goal title and choose a joint measured in your baseline.");
    const target = $("goal-target").value.trim() ? Number($("goal-target").value) : null;
    if (target != null && !degrees(target)) return setMessage("goal-form-status", "Choose a personal angle target between 0 and 180 degrees.");
    let frame;
    try { frame = frames().baseline; } catch (error) { return setMessage("goal-form-status", error.message); }
    state.mutating = true; controls();
    $("create-goal").textContent = "Saving goal…";
    try {
      const goal = await api("/api/practice/goals", { method: "POST", body: { title, baseline_id: state.baseline.id,
        baseline_frame: frame, focus_joint: joint, target_deg: target, notes: $("goal-notes").value.trim(), due_date: $("goal-due").value || null } });
      replaceGoal(goal); state.selectedGoal = goal.id; $("goal-filter").value = "active";
      renderGoals(); showGoalContext(); updateAddress();
      if (state.comparison) paintComparison();
      setMessage("goal-form-status", "Goal saved. Open Training to practise, then capture a retest using the same setup.", "info");
      $("goal-title").value = ""; $("goal-notes").value = ""; $("goal-target").value = ""; $("goal-due").value = "";
      toast("Practice goal saved", "ok");
    } catch (error) { setMessage("goal-form-status", error.message); }
    finally { state.mutating = false; $("create-goal").textContent = "Create goal from baseline"; controls(); }
  };

  $("save-goal-comparison").onclick = async () => {
    const goal = selectedGoal();
    if (!goal || !state.comparison || state.mutating || goal.status !== "active") return;
    const frame = frames();
    state.mutating = true; controls();
    try {
      const updated = await api(`/api/practice/goals/${goal.id}`, { method: "PATCH", body: { baseline_frame: frame.baseline,
        retest_id: state.retest.id, retest_frame: frame.retest, same_setup: $("same-setup").checked } });
      replaceGoal(updated); renderGoals(); showGoalContext(); paintComparison();
      setMessage("comparison-save-status", "Retest saved to this goal. Review the measured change, and mark the goal complete when you decide your practice objective is fulfilled.", "info");
    } catch (error) { setMessage("comparison-save-status", error.message); }
    finally { state.mutating = false; controls(); }
  };

  $("download-comparison").onclick = async () => {
    if (!state.comparisonQuery || state.mutating) return;
    const button = $("download-comparison");
    button.disabled = true;
    try {
      const query = state.comparisonQuery + (state.selectedGoal ? `&goal_id=${state.selectedGoal}` : "");
      await openBlob(`/api/practice/compare/pdf?${query}`, `SmartCricket_comparison_${state.baseline.id}_${state.retest.id}.pdf`);
      toast("Comparison PDF downloaded", "ok");
    } catch (error) { setMessage("comparison-save-status", error.message); }
    finally { controls(); }
  };

  async function load() {
    $("practice-loading").innerHTML = "Loading your captures and practice goals…";
    $("practice-loading").hidden = false;
    try {
      const [captures, goals] = await Promise.all([api("/api/history"), api("/api/practice/goals")]);
      state.history = captures; state.goals = goals.goals; state.joints = goals.joints;
      if (typeof goals.min_visibility === "number" && goals.min_visibility >= 0 && goals.min_visibility <= 1)
        state.minVisibility = goals.min_visibility;
      $("baseline-select").innerHTML = '<option value="">Choose a baseline</option>' + captures.map(capture => option(capture)).join("");
      $("practice-loading").hidden = true; $("practice-workspace").hidden = false;
      renderGoals(); populateGoalJoints(); revealAll();
      const requestedGoal = Number(params.get("goal")), requestedBaseline = Number(params.get("baseline")), requestedRetest = Number(params.get("retest"));
      if (params.has("goal")) {
        const goal = state.goals.find(item => item.id === requestedGoal);
        if (goal) await openGoal(goal, requestedRetest || undefined);
        else setMessage("practice-message", "This practice goal is unavailable. Choose one of your saved goals or create a new one.");
      } else if (params.has("baseline")) await chooseCaptures({ baselineId: requestedBaseline, retestId: requestedRetest || null });
      else if (!captures.length) setMessage("practice-message", "Start by analysing a batting photo or clip. Return here to choose it as a baseline and save your first goal.", "info");
    } catch (error) {
      $("practice-loading").innerHTML = `${alertHtml("error", error.message)}<button type="button" class="ghost" id="retry-practice">Retry loading practice goals</button>`;
      $("retry-practice").onclick = load;
    }
  }
  addEventListener("pagehide", () => { state.generation++; urls.forEach(url => URL.revokeObjectURL(url)); urls.clear(); });
  revealAll();
  load();
})(globalThis);
