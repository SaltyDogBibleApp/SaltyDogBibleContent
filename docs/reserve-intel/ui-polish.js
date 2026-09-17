(() => {
  function byId(id) {
    return document.getElementById(id);
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

    note.textContent = authenticated
      ? "Edit this article, review your changes, then approve the update."
      : "Sign in with GitHub to edit and publish article updates.";
    button.textContent = authenticated ? "Edit Article" : "Sign In to Edit";
    button.disabled = article?.isActive !== true;
  }

  function applyPolish() {
    const hostedStatus = byId("save-service-status");
    if (hostedStatus && hostedStatus.textContent !== "Live Dashboard") {
      hostedStatus.textContent = "Live Dashboard";
    }

    const environmentValue = byId("ops-main-ref");
    if (environmentValue) {
      if (environmentValue.textContent !== "Live / Main") {
        environmentValue.textContent = "Live / Main";
      }
      const label = environmentValue.closest(".ops-stat")?.querySelector(".ops-label");
      if (label && label.textContent !== "Environment") {
        label.textContent = "Environment";
      }
    }

    const connectionStatus = byId("github-app-check-status");
    const verifyButton = byId("github-app-check-button");
    if (
      connectionStatus?.classList.contains("connected") &&
      connectionStatus.textContent.toLowerCase().includes("github connected")
    ) {
      if (connectionStatus.textContent !== "GitHub Connected") {
        connectionStatus.textContent = "GitHub Connected";
      }
      if (verifyButton && !verifyButton.classList.contains("hidden")) {
        verifyButton.classList.add("hidden");
      }
    }

    syncPublishedEditAuthState();
  }

  applyPolish();

  const observer = new MutationObserver(() => applyPolish());
  const topbar = document.querySelector(".topbar-meta");
  const operations = document.querySelector(".dashboard-ops");

  if (topbar) {
    observer.observe(topbar, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class"],
    });
  }

  if (operations) {
    observer.observe(operations, {
      subtree: true,
      childList: true,
      characterData: true,
    });
  }
})();
