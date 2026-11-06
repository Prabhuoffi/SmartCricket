(function (root) {
  "use strict";

  const PROVENANCE = "SYNTHETIC DEMONSTRATION DATA — not real player evidence or model evaluation";
  const INTERPRETATION = "Angle changes, target distances and activity completion do not establish better technique or prove that practice caused a change.";
  const JOINTS = ["left_elbow", "right_elbow", "left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee"];
  const degrees = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 180;
  const round = value => Math.round((value + Number.EPSILON) * 10) / 10;

  function measurement(value) {
    if (!value || !degrees(value.deg)) return { valid: false, reason: "Missing or invalid angle" };
    if (typeof value.visibility !== "number" || !Number.isFinite(value.visibility) || value.visibility < .5 || value.visibility > 1)
      return { valid: false, reason: "Low or unavailable visibility" };
    return { valid: true, deg: value.deg };
  }

  function comparison(scenario) {
    const shared = [], excluded = [], warnings = [];
    for (const joint of JOINTS) {
      const before = measurement(scenario.baseline?.angles?.[joint]);
      const after = measurement(scenario.retest?.angles?.[joint]);
      if (before.valid && after.valid) shared.push({ joint, baseline_deg: before.deg, retest_deg: after.deg, change_deg: round(after.deg - before.deg) });
      else excluded.push({ joint, reason: [!before.valid && `Baseline: ${before.reason}`, !after.valid && `Retest: ${after.reason}`].filter(Boolean).join("; ") });
    }
    if (!scenario.setup_confirmed) warnings.push("The fictional player has not confirmed matching capture setup.");
    const fields = { view: "Camera view", phase: "Movement phase", shot: "Stated shot", body_side: "Visible body side", mode: "Capture type" };
    for (const [field, label] of Object.entries(fields)) {
      const before = scenario.baseline?.[field], after = scenario.retest?.[field];
      if (!before || !after || before !== after) warnings.push(`${label} differs or is unavailable.`);
    }
    if ([scenario.baseline, scenario.retest].some(capture => capture?.quality !== "clear")) warnings.push("Capture quality is limited or unavailable.");
    if (shared.length < 4) warnings.push("Fewer than four joints have usable measurements in both captures.");
    const focus = shared.find(row => row.joint === scenario.goal?.focus_joint);
    const target = degrees(scenario.goal?.target_deg) && focus ? {
      joint: focus.joint, target_deg: scenario.goal.target_deg,
      baseline_distance_deg: round(Math.abs(focus.baseline_deg - scenario.goal.target_deg)),
      retest_distance_deg: round(Math.abs(focus.retest_deg - scenario.goal.target_deg)),
    } : null;
    return { shared, excluded, warnings, exploratory: warnings.length > 0, target };
  }

  function activity(sessions) {
    let planned = 0, completed = 0, restDays = 0;
    for (const session of sessions) {
      if (!Number.isInteger(session.planned) || !Number.isInteger(session.completed) || session.planned < 0 ||
          session.completed < 0 || session.completed > session.planned ||
          (session.check_in === "Rest" && (session.planned !== 0 || session.completed !== 0)))
        throw new Error("Invalid fictional activity totals.");
      planned += session.planned;
      completed += session.completed;
      if (session.check_in === "Rest") restDays++;
    }
    return { days: sessions.length, rest_days: restDays, planned_drills: planned, completed_drills: completed,
      adherence_pct: planned ? round(100 * completed / planned) : null };
  }

  function validateFixture(data) {
    if (data?.schema_version !== 1 || data.synthetic !== true || !data.provenance?.includes("SYNTHETIC") ||
        !Array.isArray(data.scenarios) || !data.scenarios.length) throw new Error("The fixture must identify itself as synthetic demonstration data.");
    const ids = new Set();
    for (const scenario of data.scenarios) {
      if (scenario.synthetic !== true || !scenario.provenance?.includes("SYNTHETIC") ||
          !/^[a-z0-9-]+$/.test(scenario.id) || ids.has(scenario.id) || !scenario.baseline || !scenario.retest ||
          !scenario.goal || !Array.isArray(scenario.sessions)) throw new Error("A fictional scenario is invalid or missing its provenance.");
      ids.add(scenario.id);
      activity(scenario.sessions);
    }
    return data;
  }

  function report(scenario) {
    if (scenario.synthetic !== true || !scenario.provenance?.includes("SYNTHETIC")) throw new Error("Only labeled synthetic scenarios can be exported here.");
    return { schema_version: 1, synthetic: true, provenance: PROVENANCE, interpretation: INTERPRETATION,
      purpose: "Feature demonstration only; not training, test, or accuracy evidence.",
      scenario, comparison: comparison(scenario), activity: activity(scenario.sessions) };
  }

  function csvCell(value) {
    let text = value == null ? "" : String(value);
    // Prevent spreadsheet formulas in text, retaining ordinary signed numeric values.
    if (typeof value === "string" && /^[=+\-@\t\r\n]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }

  function csv(scenario) {
    const exported = report(scenario), result = exported.comparison;
    const columns = ["synthetic", "provenance", "scenario_id", "record_type", "label", "baseline_deg", "retest_deg", "change_deg",
      "target_deg", "baseline_target_distance_deg", "retest_target_distance_deg", "date", "planned_drills", "completed_drills", "note"];
    const row = values => columns.map(key => csvCell(({ synthetic: true, provenance: PROVENANCE, scenario_id: scenario.id, ...values })[key])).join(",");
    const rows = [columns.map(csvCell).join(",")];
    rows.push(row({ record_type: "interpretation", label: scenario.title, note: INTERPRETATION }));
    rows.push(row({ record_type: "goal", label: scenario.goal.title, target_deg: scenario.goal.target_deg,
      baseline_target_distance_deg: result.target?.baseline_distance_deg, retest_target_distance_deg: result.target?.retest_distance_deg,
      date: scenario.goal.review_date, note: `${scenario.goal.status}. Personal target only; not an ideal batting angle.` }));
    for (const joint of result.shared) rows.push(row({ record_type: "measurement", label: joint.joint, ...joint }));
    for (const joint of result.excluded) rows.push(row({ record_type: "excluded_measurement", label: joint.joint, note: joint.reason }));
    for (const warning of result.warnings) rows.push(row({ record_type: "capture_warning", note: warning }));
    for (const session of scenario.sessions) rows.push(row({ record_type: "activity", label: session.check_in, date: session.date,
      planned_drills: session.planned, completed_drills: session.completed, note: session.note }));
    rows.push(row({ record_type: "activity_total", label: "Completed planned drills", planned_drills: exported.activity.planned_drills,
      completed_drills: exported.activity.completed_drills, note: "Rest days have no planned drills. Activity is not a skill score." }));
    return rows.join("\r\n") + "\r\n";
  }

  root.SCShowcase = { PROVENANCE, INTERPRETATION, measurement, comparison, activity, validateFixture, report, csv };
  if (typeof module !== "undefined" && module.exports) module.exports = root.SCShowcase;
  if (typeof document === "undefined") return;

  requireLogin();
  sidebar("showcase.html");
  const $ = id => document.getElementById(id);
  let fixture = null, selected = null;
  const deg = value => `${Number(value).toFixed(1)}°`;
  const signed = value => `${value > 0 ? "+" : ""}${deg(value)}`;
  const label = joint => prettyJoint(joint);

  function render() {
    selected = fixture.scenarios.find(scenario => scenario.id === $("showcase-select").value) || fixture.scenarios[0];
    const result = comparison(selected), totals = activity(selected.sessions);
    $("scenario-summary").innerHTML = `<h3>${esc(selected.title)}</h3><p class="muted">${esc(selected.description)}</p><p class="small"><b>${esc(selected.player)}</b> · ${esc(selected.handedness)}</p>`;
    $("showcase-kpis").innerHTML = [
      ["Shared joints", `${result.shared.length} / ${JOINTS.length}`, "Usable fictional measurements in both captures"],
      ["Practice adherence", totals.adherence_pct == null ? "—" : `${totals.adherence_pct}%`, `${totals.completed_drills} of ${totals.planned_drills} fictional planned drills`],
      ["Rest days", totals.rest_days, "No drills included in the activity denominator"],
      ["Retest target distance", result.target ? deg(result.target.retest_distance_deg) : "—", result.target ? `Baseline distance: ${deg(result.target.baseline_distance_deg)}` : "No usable focus joint or no personal target"],
    ].map(([name, value, note]) => `<article class="showcase-kpi"><span class="muted small">${esc(name)}</span><b>${esc(value)}</b><small>${esc(note)}</small></article>`).join("");
    $("showcase-goal").innerHTML = `<b>${esc(selected.goal.title)}</b><p class="muted small">${esc(label(selected.goal.focus_joint))} · ${selected.goal.target_deg == null ? "No numeric target" : `Personal target ${esc(deg(selected.goal.target_deg))}`} · Review ${esc(selected.goal.review_date)}</p><p class="small">${esc(selected.goal.status)}</p><p class="muted small">${esc(selected.goal.notes)}</p>`;
    $("showcase-captures").innerHTML = [["Baseline", selected.baseline], ["Retest", selected.retest]].map(([name, capture]) =>
      `<article class="showcase-capture"><h3>${name} · fictional capture</h3><dl>${Object.entries({ Date: capture.date, Type: capture.mode, Shot: capture.shot, View: capture.view, Phase: capture.phase, Quality: capture.quality, "Body side": capture.body_side,
        ...(capture.mode === "video" ? { "Selected frame": `${capture.selected_frame + 1} of ${capture.frame_count} (fictional snapshot)` } : {}) }).map(([key, value]) => `<dt>${esc(key)}</dt><dd>${esc(value)}</dd>`).join("")}</dl></article>`).join("");
    $("showcase-checks").innerHTML = result.warnings.length ? result.warnings.map(warning => `<p>${esc(warning)}</p>`).join("") :
      '<p class="showcase-clear">The stated demo setup checks match. These checks do not verify identical recording conditions or better technique.</p>';
    $("showcase-comparison-state").textContent = result.exploratory ? "Exploratory comparison" : "Setup checks clear";
    $("showcase-comparison-state").className = `chip ${result.exploratory ? "warn" : "info"}`;
    $("showcase-angle-rows").innerHTML = result.shared.map(row => {
      const width = Math.min(50, Math.abs(row.change_deg) / 30 * 50);
      const left = row.change_deg < 0 ? 50 - width : 50;
      return `<tr><th scope="row">${esc(label(row.joint))}</th><td>${esc(deg(row.baseline_deg))}</td><td>${esc(deg(row.retest_deg))}</td><td>${esc(signed(row.change_deg))}</td><td><div class="showcase-change" aria-hidden="true"><span class="${row.change_deg < 0 ? "negative" : "positive"}" style="left:${left}%;width:${width}%"></span></div></td></tr>`;
    }).join("") || '<tr><td colspan="5">No shared usable fictional measurements.</td></tr>';
    $("showcase-exclusions").hidden = !result.excluded.length;
    $("showcase-excluded-list").innerHTML = result.excluded.map(item => `<li>${esc(label(item.joint))}: ${esc(item.reason)}</li>`).join("");
    $("showcase-exclusions").open = result.excluded.length > 0;
    $("showcase-activity").innerHTML = selected.sessions.map(session => `<div class="showcase-day${session.check_in === "Rest" ? " rest" : ""}" title="${esc(session.date)}: ${session.completed}/${session.planned} fictional drills${session.check_in === "Rest" ? "; rest day" : ""}"><span>${session.check_in === "Rest" ? "Rest" : `<i style="height:${session.planned ? session.completed / session.planned * 100 : 0}%"></i>`}</span>${esc(session.date.slice(5))}</div>`).join("");
    $("showcase-session-rows").innerHTML = selected.sessions.map(session => `<tr><td>${esc(session.date)}</td><td>${esc(session.check_in)}</td><td>${session.planned}</td><td>${session.completed}</td><td>${esc(session.note)}</td></tr>`).join("");
  }

  function download(content, extension, type) {
    if (!selected) return;
    const url = URL.createObjectURL(new Blob([content], { type }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `smartcricket-synthetic-demo-${selected.id}.${extension}`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  $("showcase-select").addEventListener("change", render);
  $("showcase-csv").addEventListener("click", () => download("\uFEFF" + csv(selected), "csv", "text/csv;charset=utf-8"));
  $("showcase-json").addEventListener("click", () => download(JSON.stringify(report(selected), null, 2) + "\n", "json", "application/json"));
  $("showcase-print").addEventListener("click", () => window.print());

  (async function load() {
    try {
      const response = await fetch("data/showcase.json?v=1", { credentials: "same-origin" });
      if (!response.ok) throw new Error("The bundled demo scenarios could not be loaded.");
      fixture = validateFixture(await response.json());
      $("showcase-select").innerHTML = fixture.scenarios.map(scenario => `<option value="${esc(scenario.id)}">${esc(scenario.title)}</option>`).join("");
      $("scenario-count").textContent = `${fixture.scenarios.length} fictional scenarios`;
      render();
      $("showcase-status").hidden = true;
      $("showcase-content").hidden = false;
    } catch (error) {
      $("showcase-status").textContent = `${error.message} Reload this page with the local app server running.`;
    }
  })();
})(typeof window !== "undefined" ? window : globalThis);
