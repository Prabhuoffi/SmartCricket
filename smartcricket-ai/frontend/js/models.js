(function (root) {
  "use strict";
  const ORDER = ["video", "pose", "fusion", "pose3d", "fusion3d"];
  const LABELS = { video: "Video only", pose: "Pose only", fusion: "Video + pose", pose3d: "3D pose only", fusion3d: "Video + 3D pose" };
  const DESCRIPTIONS = { video: "Video appearance and movement", pose: "Estimated 2D body movement", fusion: "Video and 2D pose combined", pose3d: "Estimated 3D body movement", fusion3d: "Video and 3D pose combined" };
  const metric = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1 ? value : null;
  const percent = value => metric(value) === null ? "–" : (value * 100).toFixed(2) + "%";
  const decimal = value => metric(value) === null ? "–" : value.toFixed(4);
  const chartPercent = value => metric(value) === null ? null : value * 100;
  function bestF1(rows) {
    const values = rows.map(row => metric(row.macro_f1)).filter(value => value !== null);
    return values.length ? Math.max(...values) : null;
  }
  root.SCModels = { metric, percent, decimal, chartPercent, bestF1 };
  if (typeof module !== "undefined" && module.exports) module.exports = root.SCModels;
  if (typeof document === "undefined") return;

  requireLogin(); sidebar("models.html");
  const $ = id => document.getElementById(id);
  let evaluations = [], charts = [], loading = false, importing = false;
  $("sum-icon").innerHTML = icon("upload");
  revealAll();

  function clearCharts() { charts.forEach(chart => chart.destroy()); charts = []; }
  function renderCharts() {
    clearCharts();
    $("charts-unavailable").hidden = true; $("model-charts").hidden = false;
    if (typeof Chart === "undefined") { $("charts-unavailable").hidden = false; $("model-charts").hidden = true; return; }
    const dark = document.documentElement.dataset.theme === "dark";
    const tick = dark ? "#b8c4bb" : "#4a5a50", grid = dark ? "rgba(243,239,228,.1)" : "rgba(11,26,18,.07)";
    const options = maximum => ({ indexAxis: "y", maintainAspectRatio: false,
      animation: { duration: reduceMotion ? 0 : 500 },
      plugins: { legend: { position: "bottom", labels: { color: tick, usePointStyle: true, boxWidth: 9, padding: 18 } } },
      scales: { x: { beginAtZero: true, ...(maximum ? { max: maximum } : {}), ticks: { color: tick }, grid: { color: grid } },
        y: { ticks: { color: tick, font: { size: 11 } }, grid: { display: false } } } });
    const labels = evaluations.map(row => LABELS[row.model]);
    try {
      const accuracyOptions = options(100);
      accuracyOptions.scales.x.ticks.callback = value => value + "%";
      accuracyOptions.plugins.tooltip = { callbacks: { label: context => ` ${context.dataset.label}: ${context.parsed.x.toFixed(2)}%` } };
      charts.push(new Chart($("acc"), { type: "bar", data: { labels, datasets: [
        { label: "Top-1 accuracy", data: evaluations.map(row => chartPercent(row.accuracy)), backgroundColor: dark ? "#34b77a" : "#0f5c3a", borderRadius: 4, maxBarThickness: 15 },
        { label: "Macro-F1", data: evaluations.map(row => chartPercent(row.macro_f1)), backgroundColor: dark ? "#fb7185" : "#c8102e", borderRadius: 4, maxBarThickness: 15 },
      ] }, options: accuracyOptions }));
      charts.push(new Chart($("ece"), { type: "bar", data: { labels, datasets: [
        { label: "Before scaling", data: evaluations.map(row => metric(row.ece_before)), backgroundColor: "#c98b19", borderRadius: 4, maxBarThickness: 15 },
        { label: "After scaling", data: evaluations.map(row => metric(row.ece_after)), backgroundColor: "#1f9d55", borderRadius: 4, maxBarThickness: 15 },
      ] }, options: options() }));
    } catch (_) { clearCharts(); $("charts-unavailable").hidden = false; $("model-charts").hidden = true; }
  }

  function render(data) {
    const installed = new Set((data.installed || []).map(model => model.kind));
    evaluations = ORDER.map(kind => (data.evaluations || []).find(row => row.model === kind)).filter(Boolean);
    $("models-summary").hidden = false;
    $("models-summary").textContent = `${ORDER.filter(kind => installed.has(kind)).length} of ${ORDER.length} models installed · ${evaluations.length} ${evaluations.length === 1 ? "model evaluated" : "models evaluated"}`;
    $("installed").innerHTML = ["fusion", "video", "pose", "fusion3d", "pose3d"].map(kind => {
      const available = installed.has(kind);
      return `<div class="card kpi ${available ? "tone-green" : "tone-gold"}"><div class="ico">${icon(available ? "check" : "clock")}</div>
        <b>${LABELS[kind]}</b><p class="muted small">${DESCRIPTIONS[kind]}</p><span class="chip ${available ? "ok" : "low"}">${available ? "Installed" : "Not installed"}</span></div>`;
    }).join("");
    $("empty").hidden = Boolean(evaluations.length); $("content").hidden = !evaluations.length;
    if (!evaluations.length) {
      clearCharts();
      const count = ORDER.filter(kind => installed.has(kind)).length;
      const steps = [[count > 0, "Train the classifiers", "Run the training notebook in Google Colab with a GPU."],
        [count === ORDER.length, `Install the checkpoints (${count} of ${ORDER.length})`, "Copy the trained model files into the models folder, then restart the backend."],
        [false, "Import evaluation results", 'Choose summary.json in the <a href="#import">Training results</a> section below.']];
      const next = steps.findIndex(step => !step[0]);
      $("step-count").textContent = `${steps.filter(step => step[0]).length} of 3 done`;
      $("setup").innerHTML = steps.map(([done, title, text], index) => `<div class="su${done ? " done" : index === next ? " now" : ""}"><span class="su-n">${done ? icon("check") : index + 1}</span><div><b>${title}</b><p>${text}</p></div></div>`).join("");
      $("cls-title").textContent = `${(data.classes || []).length} shot classes`;
      $("classes").innerHTML = (data.classes || []).map(shot => `<span class="chip info">${esc(shot)}</span>`).join("");
      return;
    }
    const best = bestF1(evaluations);
    $("evaluation-count").textContent = `${evaluations.length} ${evaluations.length === 1 ? "model" : "models"}`;
    $("rows").innerHTML = evaluations.map(row => `<tr><th scope="row">${LABELS[row.model]}${best !== null && metric(row.macro_f1) === best ? '<br><span class="chip ok">Highest macro-F1</span>' : ""}</th>
      <td>${percent(row.accuracy)}</td><td>${percent(row.macro_f1)}</td><td>${percent(row.precision)}</td><td>${percent(row.recall)}</td><td>${decimal(row.ece_before)}</td><td>${decimal(row.ece_after)}</td></tr>`).join("");
    renderCharts();
  }

  async function load() {
    if (loading) return false;
    loading = true; $("models-status").hidden = false; $("models-status").textContent = "Loading model results…";
    try { render(await api("/api/models")); $("models-status").hidden = true; return true; }
    catch (error) {
      $("models-status").innerHTML = `${alertHtml("error", error.message)}<button type="button" class="ghost" id="retry-models">Retry model results</button>`;
      $("retry-models").onclick = load;
      return false;
    } finally { loading = false; }
  }

  $("sum-file").onchange = async () => {
    const file = $("sum-file").files[0];
    if (!file || importing) return;
    $("sum-msg").innerHTML = "";
    importing = true; $("sum-file").disabled = true; $("sum-drop").setAttribute("aria-busy", "true");
    $("sum-label").textContent = "Importing results…";
    try {
      if (!file.name.toLowerCase().endsWith(".json")) throw new Error("Choose the summary.json results file.");
      if (!file.size || file.size > 2 * 1024 * 1024) throw new Error("Choose a non-empty JSON file up to 2 MB.");
      try { JSON.parse(await file.text()); } catch (_) { throw new Error("This file is not valid JSON. Choose the summary.json generated by training."); }
      const form = new FormData(); form.append("file", file);
      const result = await api("/api/admin/evaluations", { method: "POST", body: form });
      const count = Object.keys(result.imported).length;
      const refreshed = await load();
      $("sum-msg").innerHTML = alertHtml("info", `Imported results for ${count} ${count === 1 ? "model" : "models"}.${refreshed ? " The metrics above are updated." : " Use Retry above to refresh the view."}`);
    } catch (error) { $("sum-msg").innerHTML = alertHtml("error", error.message); }
    finally {
      importing = false; $("sum-file").disabled = false; $("sum-file").value = "";
      $("sum-drop").setAttribute("aria-busy", "false"); $("sum-label").textContent = "Choose results file";
    }
  };
  document.addEventListener("themechange", () => { if (evaluations.length) renderCharts(); });
  addEventListener("pagehide", clearCharts);
  load();
})(globalThis);
