"use strict";

requireLogin();
sidebar("profile.html");

const profileElement = id => document.getElementById(id);
const profileFields = { handedness: "profile-handedness", experience: "profile-experience", camera_view: "profile-camera", focus: "profile-focus", notes: "profile-notes" };
let savedProfile = null;
let savingProfile = false;
let profileChecklist = [];

function profileValues() {
  return Object.fromEntries(Object.entries(profileFields).map(([key, id]) => [key, profileElement(id).value.trim()]));
}

function renderProfileChecklist() {
  const view = profileElement("profile-camera").selectedOptions[0]?.textContent || "Selected";
  profileElement("profile-checklist-view").textContent = `Checklist for a ${view.toLowerCase()} capture. Save your preference to reuse it next time.`;
  profileElement("profile-checklist").innerHTML = profileChecklist.map(item => {
    const title = item.key === "view" ? `Repeat your ${view.toLowerCase()} camera view` : item.title;
    return `<li><div><b>${esc(title)}</b><p>${esc(item.detail)}</p></div></li>`;
  }).join("");
}

function renderProfile(data) {
  savedProfile = { ...data.profile };
  for (const [key, id] of Object.entries(profileFields)) profileElement(id).value = data.profile[key] ?? "";
  profileChecklist = data.checklist;
  profileElement("profile-interpretation").textContent = data.interpretation;
  profileElement("profile-state").textContent = data.saved ? "Saved preferences" : "Not saved yet";
  profileElement("profile-saved-at").textContent = data.saved ? `Saved ${fmtDate(data.profile.updated_at)}. Your model and historical measurements are unchanged.` : "Defaults shown. Save your choices when ready.";
  renderProfileChecklist();
  brandSelects();
}

function markProfileEdited() {
  if (!savedProfile || savingProfile) return;
  const current = profileValues();
  const dirty = Object.keys(profileFields).some(key => current[key] !== savedProfile[key]);
  profileElement("profile-state").textContent = dirty ? "Unsaved edits" : savedProfile.updated_at ? "Saved preferences" : "Not saved yet";
}

profileElement("profile-form").addEventListener("input", markProfileEdited);
profileElement("profile-form").addEventListener("change", () => { markProfileEdited(); renderProfileChecklist(); });
profileElement("profile-reset").addEventListener("click", () => {
  if (!savedProfile || savingProfile) return;
  for (const [key, id] of Object.entries(profileFields)) profileElement(id).value = savedProfile[key] ?? "";
  profileElement("profile-message").textContent = "Unsaved edits cleared. Your saved preferences are unchanged.";
  markProfileEdited(); renderProfileChecklist(); brandSelects();
});

profileElement("profile-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (savingProfile) return;
  savingProfile = true;
  const button = profileElement("profile-save");
  button.disabled = true;
  button.textContent = "Saving…";
  profileElement("profile-reset").disabled = true;
  // Freeze the submitted fields so a late reply cannot silently discard edits.
  for (const id of Object.values(profileFields)) profileElement(id).disabled = true;
  const body = profileValues();
  try {
    const data = await api("/api/profile", { method: "PUT", body });
    renderProfile(data);
    profileElement("profile-message").innerHTML = alertHtml("info", "Preferences saved. Your checklist is ready for the next capture.");
  } catch (error) {
    profileElement("profile-message").innerHTML = alertHtml("error", error.message);
  } finally {
    savingProfile = false;
    button.disabled = false;
    button.textContent = "Save preferences";
    profileElement("profile-reset").disabled = false;
    for (const id of Object.values(profileFields)) profileElement(id).disabled = false;
    markProfileEdited(); brandSelects();
  }
});

async function loadProfile() {
  try {
    const data = await api("/api/profile");
    renderProfile(data);
    profileElement("profile-loading").hidden = true;
    profileElement("profile-workspace").hidden = false;
  } catch (error) {
    profileElement("profile-loading").innerHTML = `${alertHtml("error", error.message)}<button type="button" class="ghost" id="profile-retry">Retry loading</button>`;
    profileElement("profile-retry").onclick = () => {
      profileElement("profile-loading").textContent = "Loading your capture preferences…";
      loadProfile();
    };
  }
}

loadProfile();
