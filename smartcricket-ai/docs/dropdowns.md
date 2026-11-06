# Shared dropdowns

The app uses one select component for capture pickers, goal filters, focus joints, shot types, reference clips, and playback speed.

`frontend/js/dropdown.js` provides `SCSelect`. App pages load it before `js/api.js`; `css/style.css` imports its shared stylesheet. Existing `brandSelect` and `brandSelects` calls remain compatibility helpers.

## Adding a dropdown

Use a normal single-select control with a visible label. The component discovers it automatically, including controls added later.

```html
<label for="session">Practice session</label>
<select id="session" name="session" aria-label="Practice session" required>
  <option value="">Choose a session</option>
  <option value="morning">Morning nets</option>
  <option value="evening">Evening nets</option>
</select>
```

The native select remains the source of its value, options, disabled state, and form validation. Existing `change` handlers continue to work. Setting `.value`, `.selectedIndex`, `.disabled`, or replacing options updates the visible control.

```js
const session = document.getElementById("session");
session.value = "evening";
session.disabled = false;
SCSelect.refresh(session); // Optional explicit refresh after a custom update.
```

Use `data-dropdown-compact` for inline controls such as filters or playback speed. Use `<optgroup>` to group choices and `disabled` on an option or group to make it unavailable. `required` retains normal browser form semantics; errors focus the visible dropdown.

## Interaction

- Long lists provide search, including a clear no-results state.
- Arrow keys move between available choices; Enter selects; Escape dismisses the menu. Disabled options are skipped.
- Menus open above or below the control as space permits, remain inside the viewport, and scroll internally.
- The menu is placed outside cards so overflow rules do not clip it. Only one dropdown is open at a time.
- Labels, selected states, keyboard focus, themes, and mobile sizing use the same implementation on every page.

Native multi-select/listbox controls and selects explicitly marked `data-native-select` retain their original behavior. The current app's nine dropdowns all use the shared component.

## Verification

The component is loaded once on each of the 16 app pages. All nine current selects have explicit accessible names and use the same enhancement path.

Validation passed 18 JavaScript tests, 42 browser interaction checks, and 12 targeted positioning checks. Browser checks covered native values and events, required validation, form resets, disabled options/groups, dynamic option replacement, search, keyboard controls, existing reference/goal handlers, and cleanup. Desktop light and 390px mobile dark views showed no unexpected script errors or horizontal page overflow. Active options remain fully visible when menus open or resize.

Screenshots: [desktop](verification/dropdown-desktop.png) and [mobile dark theme](verification/dropdown-mobile-dark.png), using an isolated test account.
