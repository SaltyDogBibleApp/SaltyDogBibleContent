(() => {
  function byId(id) {
    return document.getElementById(id);
  }

  function setTextIfDifferent(element, value) {
    if (element && element.textContent !== value) element.textContent = value;
  }

  function syncPublishedEditAuthState() {
    if (typeof state === "undefined" || state.selectedKind !== "published" || state.publishedEdit) return;
    if (byId("published-review-controls")) return;

    const button = byId("edit-published-button");
    const note = byId("published-update-note");
    if (!button || !note) return;

    const normalState = button.textContent === "Edit Article" || button.textContent === "Sign In to Edit";
    if (!normalState) return;

    const authenticated = window.reserveIntelAuth?.isAuthenticated?.() === true;
    const article = typeof findItem === "function" ? findItem(state.selectedId, "published") : null;

    setTextIfDifferent(
      note,
      authenticated
        ? "Edit this article, review your changes, then approve the update."
        : "Sign in with GitHub to edit and publish article updates."
    );
    setTextIfDifferent(button, authenticated ? "Edit Article" : "Sign In to Edit");
    const disabled = article?.isActive !== true;
    if (button.disabled !== disabled) button.disabled = disabled;
  }

  function applyPolish() {
    const hostedStatus = byId("save-service-status");
    setTextIfDifferent(hostedStatus, "Live Dashboard");

    const environmentValue = byId("ops-main-ref");
    if (environmentValue) {
      setTextIfDifferent(environmentValue, "Live / Main");
      const label = environmentValue.closest(".ops-stat")?.querySelector(".ops-label");
      setTextIfDifferent(label, "Environment");
    }

    const connectionStatus = byId("github-app-check-status");
    const verifyButton = byId("github-app-check-button");
    if (
      connectionStatus?.classList.contains("connected") &&
      connectionStatus.textContent.toLowerCase().includes("github connected")
    ) {
      setTextIfDifferent(connectionStatus, "GitHub Connected");
      if (verifyButton && !verifyButton.classList.contains("hidden")) {
        verifyButton.classList.add("hidden");
      }
    }

    syncPublishedEditAuthState();
  }

  function schedulePolishBurst() {
    [0, 100, 300, 750, 1500, 3000].forEach((delay) => {
      window.setTimeout(applyPolish, delay);
    });
  }

  schedulePolishBurst();

  window.addEventListener("focus", schedulePolishBurst);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) schedulePolishBurst();
  });

  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    if (
      target.closest("#github-sign-in-button") ||
      target.closest("#github-app-check-button") ||
      target.closest(".queue-card") ||
      target.closest("#edit-published-button")
    ) {
      schedulePolishBurst();
    }
  });
})();
