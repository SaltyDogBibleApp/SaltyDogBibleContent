// Published article corrections are edited in the hosted dashboard, while
// GitHub remains the source of truth. This override reuses the existing editor
// and diff UI, creates correction review PRs, and lets the authenticated admin
// approve (merge) or reject (close) those PRs from the dashboard.
(() => {
  const CORRECTION_PATH = "/api/published-article";
  const DEFAULT_NOTE =
    "Edit this article here. Changes are staged for review and do not affect the live article until you approve and publish them.";
  const SIGNED_OUT_NOTE =
    "Sign in with GitHub to edit and publish article updates.";
  const reviewsByArticle = new Map();
  const publicationPending = new Set();
  let reviewActionRunning = false;
  let statusRequestId = 0;

  const originalDateInputToIso =
    typeof dateInputToIso === "function" ? dateInputToIso : null;

  if (originalDateInputToIso) {
    dateInputToIso = function preservePublishedEffectiveDate(value) {
      const original =
        typeof state !== "undefined"
          ? state.publishedEdit?.article?.effectiveDate
          : null;

      if (
        value &&
        typeof original === "string" &&
        original.slice(0, 10) === value
      ) {
        return original;
      }

      return originalDateInputToIso(value);
    };
  }

  function selectedPublishedArticle() {
    if (typeof state === "undefined" || state.selectedKind !== "published") return null;
    return findItem(state.selectedId, "published");
  }

  function stopLegacyHandler(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }

  function actionRow() {
    return byId("published-update-actions")?.querySelector(".action-buttons") || null;
  }

  function removeReviewControls() {
    byId("published-review-controls")?.remove();
  }

  function makeButton(id, text, className, onClick) {
    const button = document.createElement("button");
    button.id = id;
    button.type = "button";
    button.className = className;
    button.textContent = text;
    button.addEventListener("click", onClick);
    return button;
  }

  function addGitHubLink(container, review) {
    if (typeof review?.prUrl !== "string" || !review.prUrl.startsWith("https://github.com/")) return;
    const link = document.createElement("a");
    link.className = "button secondary";
    link.href = review.prUrl;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "View in GitHub";
    container.appendChild(link);
  }

  function renderNoReview(article) {
    if (!article || state.publishedEdit) return;
    removeReviewControls();
    const note = byId("published-update-note");
    const editButton = byId("edit-published-button");
    if (publicationPending.has(article.id)) {
      if (note) {
        note.textContent =
          "Update approved. GitHub is publishing the new version now. Reload after the publication workflow finishes to confirm the live article.";
      }
      if (editButton) {
        editButton.disabled = true;
        editButton.textContent = "Publishing…";
      }
      const row = actionRow();
      if (row) {
        const controls = document.createElement("div");
        controls.id = "published-review-controls";
        controls.className = "action-buttons";
        controls.appendChild(
          makeButton("reload-published-button", "Reload Published Article", "button secondary", () => {
            window.location.reload();
          })
        );
        row.appendChild(controls);
      }
      return;
    }

    const authenticated = window.reserveIntelAuth?.isAuthenticated?.() === true;
    if (note) note.textContent = authenticated ? DEFAULT_NOTE : SIGNED_OUT_NOTE;
    if (editButton) {
      editButton.disabled = article.isActive !== true;
      editButton.textContent = authenticated ? "Edit Article" : "Sign In to Edit";
    }
  }

  function renderReviewControls(article, review) {
    if (!article || !review || state.publishedEdit) return;
    removeReviewControls();

    const note = byId("published-update-note");
    if (note) {
      note.textContent = review.draft
        ? `Update #${review.prNumber} is still in draft review. View it in GitHub to make it ready, or reject it.`
        : `Update #${review.prNumber} is ready for review. Approve & Publish applies it to the live article; Reject Update discards it without changing the published version.`;
    }

    const editButton = byId("edit-published-button");
    if (editButton) {
      editButton.disabled = true;
      editButton.textContent = "Review Pending";
    }

    const row = actionRow();
    if (!row) return;
    const controls = document.createElement("div");
    controls.id = "published-review-controls";
    controls.className = "action-buttons";

    const approve = makeButton(
      "approve-published-review-button",
      "Approve & Publish",
      "button primary",
      () => void actOnReview("approve-review", article, review)
    );
    approve.disabled = reviewActionRunning || review.draft === true;
    controls.appendChild(approve);

    const reject = makeButton(
      "reject-published-review-button",
      "Reject Update",
      "button secondary",
      () => void actOnReview("reject-review", article, review)
    );
    reject.disabled = reviewActionRunning;
    controls.appendChild(reject);
    addGitHubLink(controls, review);
    row.appendChild(controls);
  }

  async function api(body) {
    const response = await window.reserveIntelAuth.authenticatedFetch(CORRECTION_PATH, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || payload?.ok !== true) {
      throw new Error(payload?.error || `GitHub review request failed (HTTP ${response.status}).`);
    }
    return payload;
  }

  async function getReviewStatus(articleId, force = false) {
    if (!window.reserveIntelAuth?.isAuthenticated()) return null;
    if (!force && reviewsByArticle.has(articleId)) return reviewsByArticle.get(articleId);
    const payload = await api({ action: "review-status", articleId });
    const review = payload.review || null;
    reviewsByArticle.set(articleId, review);
    return review;
  }

  async function syncSelectedReview(force = false) {
    const article = selectedPublishedArticle();
    if (!article || state.publishedEdit || !window.reserveIntelAuth?.isAuthenticated()) return;

    const requestId = ++statusRequestId;
    const note = byId("published-update-note");
    const editButton = byId("edit-published-button");
    if (note) note.textContent = "Checking for a pending update…";
    if (editButton) editButton.disabled = true;

    try {
      const review = await getReviewStatus(article.id, force);
      if (requestId !== statusRequestId || state.selectedId !== article.id) return;
      if (review) renderReviewControls(article, review);
      else renderNoReview(article);
    } catch (error) {
      if (requestId !== statusRequestId || state.selectedId !== article.id) return;
      if (note) note.textContent = error.message || "Could not check update status.";
      if (editButton) editButton.disabled = false;
    }
  }

  async function beginPublishedEdit(event) {
    stopLegacyHandler(event);
    const article = selectedPublishedArticle();
    if (!article || article.isActive !== true) return;

    if (!window.reserveIntelAuth?.isAuthenticated()) {
      window.reserveIntelAuth?.signIn?.();
      showToast("Sign in with GitHub to continue editing.", "neutral");
      return;
    }

    try {
      const review = await getReviewStatus(article.id, true);
      if (review) {
        renderReviewControls(article, review);
        showToast(`Resolve pending update #${review.prNumber} before starting another edit.`, "warning");
        return;
      }
    } catch (error) {
      showToast(error.message || "Could not check for a pending update.", "warning");
      return;
    }

    removeReviewControls();
    state.publishedEdit = {
      article: structuredClone(article),
      baseUpdatedAt: article.updatedAt || null,
      patch: null,
    };
    renderArticle(article, "published");
    const note = byId("published-update-note");
    if (note) {
      note.textContent =
        "Edit the article here, then review the changes before submitting. The live article stays unchanged until you approve and publish the update.";
    }
  }

  function renderPrResult(article, payload) {
    const review = {
      prNumber: payload.prNumber,
      prUrl: payload.prUrl,
      title: null,
      branch: payload.branch,
      draft: payload.draft === true,
    };
    reviewsByArticle.set(article.id, review);
    renderReviewControls(article, review);
  }

  async function submitPublishedCorrection(event) {
    stopLegacyHandler(event);
    const edit = state.publishedEdit;
    if (!edit?.patch || state.updating) return;

    if (!window.reserveIntelAuth?.isAuthenticated()) {
      showToast("Your GitHub sign-in is required to submit this update.", "warning");
      return;
    }

    const checks = Array.from(byId("update-confirmations").querySelectorAll("input"));
    if (checks.length !== 6 || !checks.every((check) => check.checked)) return;

    state.updating = true;
    const button = byId("publish-update-button");
    const backButton = byId("back-to-update-button");
    button.disabled = true;
    button.textContent = "Submitting Update…";
    backButton.disabled = true;
    byId("update-error").textContent = "";

    try {
      const payload = await api({
        articleId: edit.article.id,
        baseUpdatedAt: edit.baseUpdatedAt,
        patch: edit.patch,
        confirmations: UPDATE_CHECKS,
      });
      const article = findItem(edit.article.id, "published");
      state.publishedEdit = null;
      setDirty(false);
      byId("update-dialog").close();
      renderArticle(article, "published");
      renderPrResult(article, payload);
      showToast(`Update #${payload.prNumber} is ready for review.`, "success");
    } catch (error) {
      byId("update-error").textContent = error.message || "Could not submit the update for review.";
    } finally {
      state.updating = false;
      button.disabled = false;
      button.textContent = "Submit for Review";
      backButton.disabled = false;
    }
  }

  async function actOnReview(action, article, review) {
    if (reviewActionRunning) return;
    const approving = action === "approve-review";
    const confirmation = approving
      ? `Approve and publish update #${review.prNumber}? This will apply the reviewed change to Reserve Intel and preserve the GitHub audit history.`
      : `Reject update #${review.prNumber}? The proposed change will be discarded and the live article will remain unchanged.`;
    if (!window.confirm(confirmation)) return;

    reviewActionRunning = true;
    renderReviewControls(article, review);
    const note = byId("published-update-note");
    if (note) note.textContent = approving ? "Publishing approved update…" : "Rejecting update…";

    try {
      const payload = await api({
        action,
        articleId: article.id,
        prNumber: review.prNumber,
      });
      reviewsByArticle.set(article.id, null);
      removeReviewControls();

      if (payload.action === "approved") {
        publicationPending.add(article.id);
        renderNoReview(article);
        showToast(`Update #${review.prNumber} approved. Publishing started.`, "success");
      } else {
        renderNoReview(article);
        showToast(`Update #${review.prNumber} rejected. The live article was not changed.`, "success");
      }
    } catch (error) {
      showToast(error.message || "Could not complete the review action.", "warning");
      renderReviewControls(article, review);
    } finally {
      reviewActionRunning = false;
    }
  }

  document.addEventListener(
    "click",
    (event) => {
      const element = event.target instanceof Element ? event.target : null;
      if (!element) return;

      const editButton = element.closest("#edit-published-button");
      if (editButton) {
        void beginPublishedEdit(event);
        return;
      }

      const submitButton = element.closest("#publish-update-button");
      if (submitButton) {
        void submitPublishedCorrection(event);
        return;
      }

      const reviewButton = element.closest("#review-update-button");
      if (reviewButton) {
        queueMicrotask(() => {
          const publishButton = byId("publish-update-button");
          if (publishButton) publishButton.textContent = "Submit for Review";
        });
        return;
      }

      const publishedCard = element.closest('.queue-card[data-kind="published"]');
      if (publishedCard) {
        queueMicrotask(() => void syncSelectedReview(true));
      }
    },
    true
  );

  const publishButton = byId("publish-update-button");
  if (publishButton) publishButton.textContent = "Submit for Review";
})();
