/* Shared single-select control. The native select remains the form's source of truth. */
(function (global) {
  "use strict";

  function normalize(value) {
    return String(value || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase().replace(/\s+/g, " ").trim();
  }

  function nextEnabled(options, current, direction, wrap) {
    if (!options.length) return -1;
    let index = current;
    for (let count = 0; count < options.length; count++) {
      index += direction;
      if (index < 0 || index >= options.length) {
        if (!wrap) return -1;
        index = (index + options.length) % options.length;
      }
      if (!options[index].disabled) return index;
    }
    return -1;  
  }

  function placement(rect, viewport, desiredHeight) {
    const margin = 12, gap = 6;
    const leftEdge = viewport.left || 0, topEdge = viewport.top || 0;
    const below = Math.max(0, topEdge + viewport.height - margin - rect.bottom - gap);
    const above = Math.max(0, rect.top - topEdge - margin - gap);
    const aboveTrigger = below < Math.min(desiredHeight, 220) && above > below;
    const height = Math.max(0, Math.min(360, desiredHeight, aboveTrigger ? above : below));
    const width = Math.min(rect.width, Math.max(0, viewport.width - margin * 2));
    const left = Math.min(Math.max(rect.left, leftEdge + margin), leftEdge + viewport.width - margin - width);
    return { left, top: aboveTrigger ? rect.top - gap - height : rect.bottom + gap, width, height, above: aboveTrigger };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { normalize, nextEnabled, placement };
  if (!global.document) return;

  const doc = global.document;
  const instances = new Set();
  const controls = new WeakMap();
  const nativePrototype = global.HTMLSelectElement.prototype;
  let sequence = 0, opened = null, positionFrame = 0, invalidFocus = null;

  const chevron = '<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 7.5 5 5 5-5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const check = '<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m4 10 4 4 8-8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const magnifier = '<svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" stroke-width="1.5"/><path d="m13 13 4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';

  function attribute(node, name, value) {
    if (value === null || value === undefined || value === false) {
      if (node.hasAttribute(name)) node.removeAttribute(name);
    } else if (node.getAttribute(name) !== String(value)) node.setAttribute(name, String(value));
  }

  function cleanText(node) {
    const clone = node.cloneNode(true);
    clone.querySelectorAll("select, button, input, textarea, .sc-select, .sc-select-error, [aria-hidden='true']").forEach(item => item.remove());
    return clone.textContent.replace(/\s+/g, " ").trim();
  }

  function accessibleName(select) {
    const labelledBy = (select.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean);
    const fromIds = labelledBy.map(id => doc.getElementById(id)).filter(Boolean).map(cleanText).filter(Boolean).join(" ");
    return fromIds || select.getAttribute("aria-label") || Array.from(select.labels || []).map(cleanText).filter(Boolean).join(" ") || select.title || select.name || "Choose an option";
  }

  function eligible(select) {
    return select instanceof global.HTMLSelectElement && !select.multiple && select.size <= 1 && !select.hasAttribute("data-native-select");
  }

  function readOptions(select) {
    return Array.from(select.options).map((option, index) => {
      const group = option.parentElement && option.parentElement.tagName === "OPTGROUP" ? option.parentElement : null;
      return {
        index, label: option.label || option.textContent || "", value: option.value,
        disabled: option.disabled || Boolean(group && group.disabled),
        hidden: option.hidden || Boolean(group && group.hidden), group,
        groupLabel: group ? group.label : ""
      };
    });
  }

  function selectedVisibleIndex(state) {
    return state.visible.findIndex(option => option.index === state.select.selectedIndex && !option.disabled);
  }

  function activeOption(state) {
    return state.visible[state.active] || null;
  }

  function setActive(state, index, scroll) {
    state.active = index;
    const option = activeOption(state);
    state.list.querySelectorAll(".sc-select-option").forEach(item => {
      const active = Boolean(option && Number(item.dataset.index) === option.index);
      item.classList.toggle("is-active", active);
      if (active && scroll) {
        const top = item.offsetTop, bottom = top + item.offsetHeight;
        if (top < state.list.scrollTop) state.list.scrollTop = top;
        else if (bottom > state.list.scrollTop + state.list.clientHeight) state.list.scrollTop = bottom - state.list.clientHeight;
      }
    });
    const activeId = state.open && option ? `${state.id}-option-${option.index}` : null;
    attribute(state.trigger, "aria-activedescendant", activeId);
    attribute(state.search, "aria-activedescendant", activeId);
  }

  function render(state, preserveActive) {
    const previous = preserveActive && activeOption(state);
    const query = normalize(state.search.value);
    state.visible = state.options.filter(option => !option.hidden && (!query || normalize(option.label).includes(query)));
    const fragment = doc.createDocumentFragment();
    let group = null, groupContainer = null;
    state.visible.forEach(option => {
      if (option.group !== group || !groupContainer) {
        group = option.group;
        if (group) {
          groupContainer = doc.createElement("div");
          groupContainer.className = "sc-select-group";
          groupContainer.setAttribute("role", "group");
          groupContainer.setAttribute("aria-label", option.groupLabel);
          const heading = doc.createElement("div");
          heading.className = "sc-select-group-label";
          heading.setAttribute("aria-hidden", "true");
          heading.textContent = option.groupLabel;
          groupContainer.append(heading);
          fragment.append(groupContainer);
        } else groupContainer = fragment;
      }
      const item = doc.createElement("div");
      item.className = "sc-select-option";
      item.id = `${state.id}-option-${option.index}`;
      item.dataset.index = String(option.index);
      item.setAttribute("role", "option");
      item.setAttribute("aria-selected", String(option.index === state.select.selectedIndex));
      if (option.disabled) item.setAttribute("aria-disabled", "true");
      const text = doc.createElement("span");
      text.className = "sc-select-option-text";
      text.textContent = option.label || "No selection";
      const mark = doc.createElement("span");
      mark.className = "sc-select-check";
      mark.innerHTML = check;
      item.append(text, mark);
      groupContainer.append(item);
    });
    state.list.replaceChildren(fragment);
    state.empty.hidden = state.visible.length > 0;
    state.empty.textContent = query ? "No matching options. Try another search." : "No options available.";
    let active = previous ? state.visible.findIndex(option => option.index === previous.index && !option.disabled) : -1;
    if (active < 0) active = selectedVisibleIndex(state);
    if (active < 0) active = nextEnabled(state.visible, -1, 1, false);
    setActive(state, active, Boolean(state.open && !query));
    if (state.open) schedulePosition();
  }

  function sync(state) {
    if (state.destroyed) return;
    if (!eligible(state.select)) { destroy(state); return; }
    const select = state.select;
    state.options = readOptions(select);
    const name = accessibleName(select);
    const disabled = select.disabled || select.matches(":disabled");
    state.wrapper.hidden = select.hidden;
    state.wrapper.classList.toggle("sc-select--disabled", disabled);
    state.wrapper.classList.toggle("sc-select--compact", select.hasAttribute("data-dropdown-compact"));
    state.trigger.disabled = disabled;
    attribute(state.trigger, "aria-label", name);
    attribute(state.trigger, "aria-required", select.required ? "true" : null);
    attribute(state.trigger, "aria-describedby", select.getAttribute("aria-describedby"));
    attribute(state.search, "aria-required", select.required ? "true" : null);
    attribute(state.search, "aria-label", `Search ${name.toLocaleLowerCase()}`);
    attribute(state.list, "aria-label", name);
    const current = state.options[select.selectedIndex];
    const label = current ? current.label || "No selection" : "Choose an option";
    state.text.textContent = label;
    state.trigger.title = label;
    state.trigger.classList.toggle("is-placeholder", !current || current.value === "");
    state.searchable = state.options.filter(option => !option.hidden && option.value !== "").length >= 8;
    state.searchWrap.hidden = !state.searchable;
    if (!state.searchable && state.search.value) state.search.value = "";
    if (state.open && !state.searchable && doc.activeElement === state.search) state.trigger.focus({ preventScroll: true });
    const invalid = Boolean(state.showError && !select.validity.valid);
    state.error.hidden = !invalid;
    state.error.textContent = invalid ? select.validationMessage : "";
    attribute(state.trigger, "aria-invalid", invalid ? "true" : null);
    attribute(state.search, "aria-invalid", invalid ? "true" : null);
    if (invalid) attribute(state.trigger, "aria-describedby", [select.getAttribute("aria-describedby"), state.error.id].filter(Boolean).join(" "));
    attribute(state.search, "aria-describedby", state.trigger.getAttribute("aria-describedby"));
    if (disabled || select.hidden) close(state, false);
    render(state, true);
  }

  function viewport() {
    const visual = global.visualViewport;
    return visual ? { left: visual.offsetLeft, top: visual.offsetTop, width: visual.width, height: visual.height } : { left: 0, top: 0, width: doc.documentElement.clientWidth, height: global.innerHeight };
  }

  function position(state) {
    if (!state || !state.open) return;
    const rect = state.trigger.getBoundingClientRect();
    const view = viewport();
    if (!state.trigger.getClientRects().length || rect.bottom <= view.top || rect.top >= view.top + view.height) {
      close(state, false);
      return;
    }
    const desired = Math.min(360, state.list.scrollHeight + (state.searchable ? state.searchWrap.offsetHeight : 0) + (state.empty.hidden ? 0 : state.empty.offsetHeight) + 14);
    const place = placement(rect, view, desired);
    if (place.height < 24) { close(state, false); return; }
    Object.assign(state.panel.style, { left: `${place.left}px`, top: `${place.top}px`, width: `${place.width}px`, maxHeight: `${place.height}px` });
    state.panel.classList.toggle("sc-select-panel--above", place.above);
    // Sizing can shrink the list after its initial render; reveal the entire active row.
    setActive(state, state.active, true);
  }

  function schedulePosition() {
    if (!opened || positionFrame) return;
    positionFrame = global.requestAnimationFrame(() => { positionFrame = 0; position(opened); });
  }

  function open(state, edge) {
    sync(state);
    if (state.destroyed || state.trigger.disabled || state.wrapper.hidden) return;
    if (opened && opened !== state) close(opened, false);
    if (!state.open) {
      state.search.value = "";
      state.open = true;
      opened = state;
      state.panel.hidden = false;
      state.wrapper.classList.add("is-open");
      attribute(state.trigger, "aria-expanded", "true");
      attribute(state.search, "aria-expanded", "true");
      render(state, false);
    }
    if (edge) setActive(state, nextEnabled(state.visible, edge > 0 ? -1 : state.visible.length, edge, false), true);
    position(state);
    if (!state.open) return;
    // Touch users can choose an option without the software keyboard covering the list.
    if (state.searchable && !global.matchMedia("(pointer: coarse)").matches) state.search.focus({ preventScroll: true });
    else state.trigger.focus({ preventScroll: true });
  }

  function close(state, focus) {
    if (!state || !state.open) return;
    state.open = false;
    state.panel.hidden = true;
    state.wrapper.classList.remove("is-open");
    attribute(state.trigger, "aria-expanded", "false");
    attribute(state.search, "aria-expanded", "false");
    attribute(state.trigger, "aria-activedescendant", null);
    attribute(state.search, "aria-activedescendant", null);
    if (opened === state) opened = null;
    if (focus && !state.trigger.disabled && state.trigger.isConnected) state.trigger.focus({ preventScroll: true });
  }

  function choose(state, option) {
    if (!option || option.disabled || state.trigger.disabled) return;
    const changed = state.select.selectedIndex !== option.index;
    state.select.selectedIndex = option.index;
    if (state.select.validity.valid) state.showError = false;
    close(state, true);
    sync(state);
    if (changed) {
      state.select.dispatchEvent(new Event("input", { bubbles: true }));
      state.select.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function move(state, direction, edge) {
    const current = edge ? (direction > 0 ? -1 : state.visible.length) : state.active;
    const index = nextEnabled(state.visible, current, direction, !edge);
    if (index >= 0) setActive(state, index, true);
  }

  function tabFromSearch(state, event) {
    const candidates = Array.from(doc.querySelectorAll("a[href], button, input, textarea, select, [tabindex], summary, iframe, [contenteditable='true']"))
      .filter(node => !state.panel.contains(node) && node.tabIndex >= 0 && !node.matches(":disabled") && !node.closest("[hidden], [inert]") && node.getClientRects().length)
      .map((node, index) => ({ node, index }))
      .sort((a, b) => (a.node.tabIndex > 0 ? a.node.tabIndex : Infinity) - (b.node.tabIndex > 0 ? b.node.tabIndex : Infinity) || a.index - b.index)
      .map(item => item.node);
    const index = candidates.indexOf(state.trigger);
    const target = candidates[index + (event.shiftKey ? -1 : 1)];
    close(state, true);
    if (index >= 0 && target) {
      event.preventDefault();
      target.focus({ preventScroll: false });
    }
  }

  function keydown(state, event) {
    const inSearch = event.target === state.search;
    if (state.trigger.disabled || event.isComposing || event.ctrlKey || event.metaKey) return;
    if (event.key === "Tab") {
      if (state.open && inSearch) tabFromSearch(state, event);
      else close(state, false);
      return;
    }
    if (event.key === "Escape") {
      if (state.open) { event.preventDefault(); event.stopPropagation(); close(state, true); }
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      if (!state.open) open(state, state.select.selectedIndex < 0 ? direction : 0);
      else move(state, direction, false);
      return;
    }
    if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const direction = event.key === "Home" ? 1 : -1;
      if (!state.open) open(state, direction);
      else move(state, direction, true);
      return;
    }
    if (event.key === "Enter" || (!inSearch && event.key === " ")) {
      event.preventDefault();
      if (!state.open) open(state);
      else choose(state, activeOption(state));
      return;
    }
    if (!inSearch && event.key.length === 1 && !event.altKey) {
      event.preventDefault();
      if (state.searchable) {
        if (!state.open) open(state);
        state.search.value += event.key;
        state.search.focus({ preventScroll: true });
        render(state, false);
        return;
      }
      global.clearTimeout(state.typeTimer);
      state.typeBuffer += normalize(event.key);
      state.typeTimer = global.setTimeout(() => { state.typeBuffer = ""; }, 650);
      const repeated = state.typeBuffer.split("").every(character => character === state.typeBuffer[0]);
      const prefix = repeated ? state.typeBuffer[0] : state.typeBuffer;
      const options = state.options.filter(option => !option.hidden && !option.disabled);
      const from = options.findIndex(option => option.index === (activeOption(state)?.index ?? state.select.selectedIndex));
      const ordered = [...options.slice(from + 1), ...options.slice(0, from + 1)];
      const option = ordered.find(item => normalize(item.label).startsWith(prefix));
      if (option) {
        if (state.open) setActive(state, state.visible.findIndex(item => item.index === option.index), true);
        else choose(state, option);
      }
    }
  }

  function proxyProperty(state, name) {
    const descriptor = Object.getOwnPropertyDescriptor(nativePrototype, name);
    const own = Object.getOwnPropertyDescriptor(state.select, name);
    if (!descriptor || !descriptor.get || !descriptor.set || (own && !own.configurable)) return;
    state.originalProperties.set(name, own);
    Object.defineProperty(state.select, name, {
      configurable: true, enumerable: descriptor.enumerable,
      get() { return descriptor.get.call(this); },
      set(value) { descriptor.set.call(this, value); sync(state); }
    });
  }

  function destroy(state) {
    if (state.destroyed) return;
    close(state, false);
    state.destroyed = true;
    state.observer.disconnect();
    state.events.abort();
    global.clearTimeout(state.typeTimer);
    state.panel.remove();
    if (state.select.parentNode === state.wrapper && state.wrapper.parentNode) state.wrapper.before(state.select);
    state.wrapper.remove();
    state.select.classList.remove("sc-select-native");
    attribute(state.select, "tabindex", state.originalTabIndex);
    attribute(state.select, "aria-hidden", state.originalAriaHidden);
    state.originalProperties.forEach((descriptor, name) => {
      if (descriptor) Object.defineProperty(state.select, name, descriptor);
      else delete state.select[name];
    });
    controls.delete(state.select);
    instances.delete(state);
  }

  function enhance(select) {
    if (!eligible(select)) return null;
    const existing = controls.get(select);
    if (existing) { sync(existing); return existing.wrapper; }
    if (!select.parentNode) return null;
    const id = `sc-select-${++sequence}`;
    const wrapper = doc.createElement("span");
    wrapper.className = "sc-select";
    if (select.style.width) wrapper.style.width = select.style.width;
    const trigger = doc.createElement("button");
    trigger.type = "button";
    trigger.tabIndex = select.tabIndex;
    trigger.id = `${id}-trigger`;
    trigger.className = "sc-select-trigger";
    trigger.setAttribute("role", "combobox");
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-autocomplete", "none");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-controls", `${id}-list`);
    const text = doc.createElement("span");
    text.className = "sc-select-value";
    const arrow = doc.createElement("span");
    arrow.className = "sc-select-arrow";
    arrow.innerHTML = chevron;
    trigger.append(text, arrow);
    const error = doc.createElement("span");
    error.className = "sc-select-error";
    error.id = `${id}-error`;
    error.setAttribute("role", "alert");
    error.hidden = true;
    const panel = doc.createElement("div");
    panel.className = "sc-select-panel";
    panel.hidden = true;
    panel.dataset.selectId = select.id || id;
    const searchWrap = doc.createElement("div");
    searchWrap.className = "sc-select-search-wrap";
    searchWrap.innerHTML = magnifier;
    const search = doc.createElement("input");
    search.className = "sc-select-search";
    search.type = "search";
    search.placeholder = "Search options…";
    search.autocomplete = "off";
    search.spellcheck = false;
    search.setAttribute("role", "combobox");
    search.setAttribute("aria-autocomplete", "list");
    search.setAttribute("aria-controls", `${id}-list`);
    search.setAttribute("aria-expanded", "false");
    searchWrap.append(search);
    const list = doc.createElement("div");
    list.id = `${id}-list`;
    list.className = "sc-select-list";
    list.setAttribute("role", "listbox");
    const empty = doc.createElement("div");
    empty.className = "sc-select-empty";
    empty.setAttribute("role", "status");
    empty.hidden = true;
    panel.append(searchWrap, list, empty);
    const state = {
      id, select, wrapper, trigger, text, error, panel, searchWrap, search, list, empty,
      open: false, destroyed: false, searchable: false, options: [], visible: [], active: -1,
      showError: false, typeBuffer: "", typeTimer: 0,
      originalProperties: new Map(), originalTabIndex: select.getAttribute("tabindex"), originalAriaHidden: select.getAttribute("aria-hidden"),
      events: new AbortController()
    };
    controls.set(select, state);
    instances.add(state);
    select.before(wrapper);
    wrapper.append(select, trigger, error);
    (doc.body || doc.documentElement).append(panel);
    select.classList.add("sc-select-native");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    proxyProperty(state, "value");
    proxyProperty(state, "selectedIndex");
    const ownFocus = Object.getOwnPropertyDescriptor(select, "focus");
    if (!ownFocus || ownFocus.configurable) {
      state.originalProperties.set("focus", ownFocus);
      Object.defineProperty(select, "focus", { configurable: true, value(options) { trigger.focus(options); } });
    }
    const on = (node, type, handler, options) => node.addEventListener(type, handler, { ...options, signal: state.events.signal });
    on(trigger, "click", event => { event.preventDefault(); if (state.open) close(state, true); else open(state); });
    on(trigger, "keydown", event => keydown(state, event));
    on(search, "keydown", event => keydown(state, event));
    on(search, "input", () => render(state, false));
    on(list, "pointerdown", event => { if (event.target.closest(".sc-select-option")) event.preventDefault(); });
    on(list, "click", event => {
      const item = event.target.closest(".sc-select-option");
      if (!item) return;
      event.preventDefault();
      choose(state, state.options[Number(item.dataset.index)]);
    });
    on(list, "pointermove", event => {
      if (event.pointerType === "touch") return;
      const item = event.target.closest(".sc-select-option");
      if (!item || item.getAttribute("aria-disabled") === "true") return;
      const index = state.visible.findIndex(option => option.index === Number(item.dataset.index));
      if (index !== state.active) setActive(state, index, false);
    });
    on(select, "change", () => { if (select.validity.valid) state.showError = false; sync(state); });
    on(select, "input", () => sync(state));
    on(select, "focus", () => trigger.focus({ preventScroll: true }));
    on(select, "invalid", event => {
      event.preventDefault();
      state.showError = true;
      sync(state);
      // A form emits invalid for every failing field; reveal the first select once.
      if (!invalidFocus) {
        invalidFocus = state;
        global.queueMicrotask(() => {
          const first = invalidFocus;
          invalidFocus = null;
          if (!first || first.destroyed || first.trigger.disabled || first.wrapper.hidden) return;
          const firstField = first.select.form && Array.from(first.select.form.elements).find(field => field.willValidate && !field.validity.valid);
          if (firstField && firstField !== first.select && !controls.has(firstField)) return;
          first.trigger.scrollIntoView({ behavior: "instant", block: "center", inline: "nearest" });
          first.trigger.focus({ preventScroll: true });
          open(first);
        });
      }
    });
    Array.from(select.labels || []).forEach(label => on(label, "click", event => {
      if (wrapper.contains(event.target) || event.target.closest("a, button, input, textarea, select")) return;
      event.preventDefault();
      trigger.focus({ preventScroll: true });
    }));
    state.observer = new MutationObserver(() => sync(state));
    state.observer.observe(select, { childList: true, subtree: true, characterData: true, attributes: true });
    sync(state);
    return wrapper;
  }

  function enhanceAll(root) {
    root = root || doc;
    if (root.matches && root.matches("select")) enhance(root);
    if (root.querySelectorAll) root.querySelectorAll("select").forEach(enhance);
  }

  function refresh(select) {
    const state = controls.get(select);
    if (state) sync(state);
    else enhance(select);
  }

  global.SCSelect = { enhance, enhanceAll, refresh };
  doc.addEventListener("pointerdown", event => {
    if (opened && !opened.wrapper.contains(event.target) && !opened.panel.contains(event.target)) close(opened, false);
  }, true);
  doc.addEventListener("focusin", event => {
    if (opened && !opened.wrapper.contains(event.target) && !opened.panel.contains(event.target)) close(opened, false);
  });
  doc.addEventListener("reset", event => global.setTimeout(() => {
    instances.forEach(state => {
      if (state.select.form === event.target) { state.showError = false; close(state, false); sync(state); }
    });
  }, 0), true);
  global.addEventListener("resize", schedulePosition);
  global.addEventListener("scroll", event => { if (!opened || !opened.panel.contains(event.target)) schedulePosition(); }, true);
  if (global.visualViewport) {
    global.visualViewport.addEventListener("resize", schedulePosition);
    global.visualViewport.addEventListener("scroll", schedulePosition);
  }
  const observer = new MutationObserver(records => {
    records.forEach(record => {
      if (record.type === "attributes") {
        if (record.target.tagName === "FIELDSET") enhanceAll(record.target);
        if (record.target.tagName === "SELECT" && !controls.has(record.target)) enhance(record.target);
        if (opened && record.target.contains(opened.trigger)) schedulePosition();
      } else record.addedNodes.forEach(node => { if (node.nodeType === 1) enhanceAll(node); });
    });
    instances.forEach(state => {
      if (!state.select.isConnected || !state.wrapper.contains(state.select)) {
        const select = state.select;
        destroy(state);
        if (select.isConnected) enhance(select);
      }
    });
  });
  function start() {
    enhanceAll(doc);
    observer.observe(doc.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled", "hidden", "multiple", "size", "data-native-select"] });
  }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})(typeof window !== "undefined" ? window : globalThis);
