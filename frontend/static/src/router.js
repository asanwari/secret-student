export function createScreenRouter({ onBeforeChange, onAfterChange }) {
  const screens = new Map(
    [...document.querySelectorAll("[data-screen]")].map((element) => [element.dataset.screen, element]),
  );
  let current = null;

  function show(name, { replace = false, fromHistory = false } = {}) {
    const next = screens.get(name);
    if (!next || name === current) return;
    onBeforeChange?.(current, name);
    for (const [screenName, element] of screens) {
      const active = screenName === name;
      element.hidden = !active;
      element.inert = !active;
      element.setAttribute("aria-hidden", String(!active));
    }
    current = name;
    if (!fromHistory) {
      const method = replace ? "replaceState" : "pushState";
      history[method]({ screen: name }, "", `#${name}`);
    }
    document.activeElement?.blur?.();
    onAfterChange?.(name);
  }

  window.addEventListener("popstate", (event) => {
    const requested = event.state?.screen || location.hash.slice(1);
    if (screens.has(requested)) show(requested, { fromHistory: true });
  });

  return { show, current: () => current, has: (name) => screens.has(name) };
}

