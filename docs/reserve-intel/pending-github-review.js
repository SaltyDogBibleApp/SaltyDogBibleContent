// Hosted Needs Review actions. The existing editor UI is preserved, while
// Save Draft, Reject, and Approve are routed through the authenticated GitHub
// App bridge instead of the local Codespace review service.
(() => {
  const ENDPOINT = "/api/published-article";
  const APPROVAL_CHECKS = [
    "I opened the official source.",
    "I verified the facts against the official source.",
    "I verified the status and effective date.",
    "I verified the intended audience.",
    "I reviewed the title, summary, Why It Matters, and details.",
    "I approve publication to Reserve Intel.",
  ];

  let hostedRefreshRunning = false;
  let statusRunning = false;
  let lastAuthenticated = null;

  function selectedPending() {
    if (typeof state === "undefined" || state.selectedKind !== "pending") return null;
    return findItem(state.selectedId, "pending");
  }

  function signedIn() {
    return window.reserveIntelAuth?.isAuthenticated?.() === true;
  }

  function stopLegacy(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }

  async function api(body) {
    if (!window.reserveIntelAuth?.isAuthenticated()) {
      throw new Error("Sign in with GitHub to review pending articles.");
    }
    const response = await window.reserveIntelAuth.authenticatedFetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || payload?.ok !== true) {
      throw new Error(payload?.error || `Review request failed (HTTP ${response.status}).`);
    }
    return payload;
  }

  function identity(item) {
    return {
      articleId: item.id,
      sourceFile: item._sourceFile,
      reviewBranch: item._reviewBranch,
    };
  }

  function setIfDifferent(element, property, value) {
    if (element && element[property] !== value) element[property] = value;
  }

  function setClass(element, className) {
    if (element && element.className !== className) element.className = className;
  }

  function applyHostedActions() {
    const item = selectedPending();
    if (!item || item._demo === true) return;

    const saveButton = byId("save-draft-button");
    const rejectButton = byId("reject-button");
    const approveButton = byId("approve-button");
    const modePill = byId("action-mode-pill");
    const actionNote = byId("action-note");
    const busy = state.saving || state.rejecting || state.approving || statusRunning;
    const authenticated = signedIn();
    const ready = item._saveEligible === true;

    setIfDifferent(saveButton, "disabled", busy || !authenticated || !ready);
    setIfDifferent(rejectButton, "disabled", busy || !authenticated || !ready);
    setIfDifferent(approveButton, "disabled", busy || state.dirty || !authenticated || !ready);

    setIfDifferent(saveButton, "textContent", state.saving ? "Saving…" : "Save Draft");
    setIfDifferent(rejectButton, "textContent", state.rejecting ? "Rejecting…" : "Reject");
    setIfDifferent(approveButton, "textContent", state.approving ? "Approving…" : "Approve for Publication");

    if (!authenticated) {
      setIfDifferent(modePill, "textContent", "SIGN IN REQUIRED");
      setClass(modePill, "preview-only-pill waiting");
      setIfDifferent(actionNote, "textContent", "Sign in with GitHub to save, reject, or approve this review.");
      return;
    }

    if (!ready) {
      setIfDifferent(modePill, "textContent", statusRunning ? "CHECKING" : "WAITING");
      setClass(modePill, "preview-only-pill waiting");
      setIfDifferent(
        actionNote,
        "textContent",
        statusRunning
          ? "Checking whether GitHub has finished preparing the Review PR…"
          : "GitHub is still preparing the Review PR. Use Refresh Queue to check again."
      );
      return;
    }

    setIfDifferent(modePill, "textContent", "HOSTED REVIEW");
    setClass(modePill, "preview-only-pill all-live");
    setIfDifferent(
      actionNote,
      "textContent",
      state.dirty
        ? "Save the current edits before approving. Reject discards the review; Approve publishes only after all six confirmations."
        : "Save Draft commits edits to the protected review branch. Reject closes without merge. Approve requires six confirmations and starts the existing publication workflow."
    );
  }

  async function syncPendingStatus(item, { rerender = true } = {}) {
    if (!item || item._demo === true || !signedIn() || state.dirty) return false;
    if (!item._sourceFile || !item._reviewBranch) return false;

    statusRunning = true;
    applyHostedActions();
    try {
      const payload = await api({
        action: "pending-status",
        ...identity(item),
      });

      if (payload.ready !== true) {
        item._saveEligible = false;
        item._contentOrigin = "main";
        return false;
      }

      if (payload.article && typeof payload.article === "object") {
        applySavedArticleToItem(item, payload.article);
      }
      item._saveEligible = true;
      item._contentOrigin = "reviewBranch";

      if (
        rerender &&
        state.selectedKind === "pending" &&
        state.selectedId === item.id &&
        !state.dirty
      ) {
        rerenderSelectedPending(item);
      }
      return true;
    } catch (error) {
      showToast(error.message || "Could not check the GitHub review state.", "warning");
      return false;
    } finally {
      statusRunning = false;
      applyHostedActions();
    }
  }

  async function refreshHostedQueue() {
    if (hostedRefreshRunning) return;
    if (!signedIn()) {
      window.reserveIntelAuth?.signIn?.();
      return;
    }
    if (state.dirty) {
      const discard = window.confirm("You have unsaved edits. Discard them and refresh the review state?");
      if (!discard) return;
      setDirty(false);
    }

    hostedRefreshRunning = true;
    const button = byId("refresh-queue-button");
    if (button) {
      button.disabled = true;
      button.textContent = "Refreshing…";
    }

    try {
      let readyCount = 0;
      for (const item of state.data?.pending || []) {
        if (item._demo === true) continue;
        if (await syncPendingStatus(item, { rerender: false })) readyCount += 1;
      }
      renderQueues();
      const current = selectedPending();
      if (current) rerenderSelectedPending(current);
      showToast(`Queue checked. ${readyCount} review${readyCount === 1 ? " is" : "s are"} ready in GitHub.`, "success");
    } finally {
      hostedRefreshRunning = false;
      const refresh = byId("refresh-queue-button");
      if (refresh) {
        refresh.disabled = false;
        refresh.textContent = "Refresh Queue";
      }
      applyHostedActions();
    }
  }

  async function saveHostedDraft(event) {
    stopLegacy(event);
    const item = selectedPending();
    if (!item || item._demo === true || state.saving) return;
    if (!signedIn()) {
      window.reserveIntelAuth?.signIn?.();
      return;
    }
    if (item._saveEligible !== true) {
      await syncPendingStatus(item);
      if (item._saveEligible !== true) return;
    }

    const snapshot = editorSnapshot();
    try {
      validateEditorSnapshot(snapshot);
    } catch (error) {
      showToast(error.message, "warning");
      return;
    }

    state.saving = true;
    applyHostedActions();
    try {
      const payload = await api({
        action: "pending-save",
        ...identity(item),
        patch: snapshot,
      });
      if (payload.article) applySavedArticleToItem(item, payload.article);
      item._saveEligible = true;
      item._contentOrigin = "reviewBranch";
      rerenderSelectedPending(item);
      const shortSha = typeof payload.commitSha === "string" ? payload.commitSha.slice(0, 7) : null;
      showToast(
        payload.changed === false
          ? "No changes to save. GitHub already matches the editor."
          : shortSha
            ? `Draft saved to GitHub in commit ${shortSha}.`
            : "Draft saved to GitHub.",
        "success"
      );
    } catch (error) {
      showToast(error.message || "Could not save the draft.", "warning");
    } finally {
      state.saving = false;
      applyHostedActions();
    }
  }

  function openHostedReject(event) {
    stopLegacy(event);
    const item = selectedPending();
    if (!item || item._demo === true) return;
    if (!signedIn()) {
      window.reserveIntelAuth?.signIn?.();
      return;
    }
    if (item._saveEligible !== true) {
      showToast("GitHub is still preparing this Review PR. Use Refresh Queue and try again.", "warning");
      return;
    }
    byId("reject-modal-article").textContent = item.title || item.id;
    byId("reject-reason").value = "";
    byId("reject-modal").classList.remove("hidden");
    setTimeout(() => byId("reject-reason").focus(), 0);
  }

  async function rejectHosted(event) {
    stopLegacy(event);
    const item = selectedPending();
    if (!item || item._demo === true || state.rejecting) return;
    const reason = byId("reject-reason").value.trim();
    if (reason.length > 2000) {
      showToast("Rejection reason must be 2,000 characters or fewer.", "warning");
      return;
    }

    state.rejecting = true;
    const confirm = byId("reject-modal-confirm");
    confirm.disabled = true;
    confirm.textContent = "Rejecting…";
    applyHostedActions();
    try {
      const payload = await api({
        action: "pending-reject",
        ...identity(item),
        reason,
      });
      closeRejectModal();
      removeRejectedItemFromDashboard(item.id);
      showToast(`Review #${payload.prNumber} rejected. Nothing was published.`, "success");
    } catch (error) {
      showToast(error.message || "Could not reject this review.", "warning");
    } finally {
      state.rejecting = false;
      confirm.disabled = false;
      confirm.textContent = "Reject Article";
      applyHostedActions();
    }
  }

  function openHostedApprove(event) {
    stopLegacy(event);
    const item = selectedPending();
    if (!item || item._demo === true) return;
    if (!signedIn()) {
      window.reserveIntelAuth?.signIn?.();
      return;
    }
    if (state.dirty) {
      showToast("Save or discard the current edits before approving.", "warning");
      return;
    }
    if (item._saveEligible !== true) {
      showToast("GitHub is still preparing this Review PR. Use Refresh Queue and try again.", "warning");
      return;
    }
    byId("approve-modal-article").textContent = item.title || item.id;
    approvalCheckboxes().forEach((check) => { check.checked = false; });
    updateApproveConfirmationState();
    byId("approve-modal").classList.remove("hidden");
  }

  async function approveHosted(event) {
    stopLegacy(event);
    const item = selectedPending();
    if (!item || item._demo === true || state.approving) return;
    const checks = approvalCheckboxes();
    if (checks.length !== 6 || checks.some((check) => !check.checked)) {
      showToast("All six approval confirmations are required.", "warning");
      return;
    }
    if (state.dirty) {
      showToast("Save or discard the current edits before approving.", "warning");
      return;
    }

    state.approving = true;
    const confirm = byId("approve-modal-confirm");
    confirm.disabled = true;
    confirm.textContent = "Approving…";
    applyHostedActions();
    try {
      const payload = await api({
        action: "pending-approve",
        ...identity(item),
        confirmations: APPROVAL_CHECKS,
      });
      closeApproveModal();
      removeApprovedItemFromDashboard(item.id);
      showToast(`Review #${payload.prNumber} approved. Publishing started.`, "success");
    } catch (error) {
      showToast(error.message || "Could not approve this review.", "warning");
    } finally {
      state.approving = false;
      confirm.textContent = "Approve & Publish";
      updateApproveConfirmationState();
      applyHostedActions();
    }
  }

  function configureHostedRefreshButton() {
    const button = byId("refresh-queue-button");
    if (!button) return;
    button.disabled = hostedRefreshRunning;
    button.textContent = hostedRefreshRunning ? "Refreshing…" : "Refresh Queue";
  }

  document.addEventListener(
    "click",
    (event) => {
      const element = event.target instanceof Element ? event.target : null;
      if (!element) return;
      const pending = selectedPending();

      if (element.closest("#refresh-queue-button")) {
        stopLegacy(event);
        void refreshHostedQueue();
        return;
      }

      if (!pending || pending._demo === true) return;

      if (element.closest("#save-draft-button")) {
        void saveHostedDraft(event);
        return;
      }
      if (element.closest("#reject-button")) {
        openHostedReject(event);
        return;
      }
      if (element.closest("#approve-button")) {
        openHostedApprove(event);
        return;
      }
      if (element.closest("#reject-modal-confirm")) {
        void rejectHosted(event);
        return;
      }
      if (element.closest("#approve-modal-confirm")) {
        void approveHosted(event);
        return;
      }

      const card = element.closest('.queue-card[data-kind="pending"]');
      if (card) {
        queueMicrotask(() => {
          const item = selectedPending();
          if (item) void syncPendingStatus(item);
        });
      }
    },
    true
  );

  const observer = new MutationObserver(() => {
    configureHostedRefreshButton();
    applyHostedActions();
    const authenticated = signedIn();
    if (authenticated !== lastAuthenticated) {
      lastAuthenticated = authenticated;
      if (authenticated) {
        const item = selectedPending();
        if (item) queueMicrotask(() => void syncPendingStatus(item));
      }
    }
  });

  const articleActions = byId("editor-actions");
  const topbar = document.querySelector(".topbar-meta");
  const operations = document.querySelector(".dashboard-ops");
  for (const target of [articleActions, topbar, operations]) {
    if (!target) continue;
    observer.observe(target, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class", "disabled"],
    });
  }

  configureHostedRefreshButton();
  applyHostedActions();
  queueMicrotask(() => {
    const item = selectedPending();
    if (item && signedIn()) void syncPendingStatus(item);
  });
})();
