export function mountPanel(root) {
  if (!(root instanceof HTMLElement)) {
    throw new TypeError("mountPanel requires an HTMLElement root");
  }

  const panel = document.createElement("section");
  panel.dataset.testid = "portable-panel";

  const status = document.createElement("p");
  status.setAttribute("role", "status");
  status.textContent = "Ready";

  const button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-pressed", "false");
  button.textContent = "Complete";
  button.addEventListener("click", () => {
    status.textContent = "Complete";
    button.setAttribute("aria-pressed", "true");
  });

  panel.append(status, button);
  root.replaceChildren(panel);
  return { panel, status, button };
}
