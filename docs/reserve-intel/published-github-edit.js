// Published article corrections are edited in the hosted dashboard, while
// GitHub remains the source of truth. This override reuses the existing editor
// and diff UI, then submits an approved correction to the authenticated Worker
// so it can create a GitHub review branch and pull request. It never edits the
// live feed directly.
(() => {
  const CORRECTION_PATH = "/api/published-article";

  function selectedPublishedArticle() {
    if (typeof state === "undefined" || state.selectedKind !== "published") return null;
    return findItem(state.selectedId, "published");
  }

  function stopLegacyHandler(event) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }

  function beginPublishedEdit(event) {
    stopLegacyHandler(event);

    const article = selectedPublishedArticle();
    if (!article || article.isActive !== true) return;

    if (!window.reserveIntelAuth?.isAuthenticated()) {
      showToast("Sign in with GitHub, then select Edit Article again.", "warning");
      return;
    }

    state.publishedEdit = {
      article: structuredClone(article),
      baseUpdatedAt: article.updatedAt || null,
      patch: null,
    };

    renderArticle(article, "published");

    const note = byId("published-update-note");
    if (note) {
      note.textContent =
        "Edit the article here. Review your changes before creating a GitHub review pull request; the currently published article stays live until that PR is merged and the publication workflow succeeds.";
    }
  }

  function renderPrResult(payload) {
    const note = byId("published-update-note");
    if (!note) return;

    note.replaceChildren();
    note.append(
      document.createTextNode(
        `Correction submitted as GitHub draft PR #${payload.prNumber}. The currently published article is unchanged until that PR is merged and the publication workflow succeeds. `
      )
    );

    if (typeof payload.prUrl === "string" && payload.prUrl.startsWith("https://github.com/")) {
      const link = document.createElement("a");
      link.href = payload.prUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Open Review PR";
      note.append(link);
    }
  }

  async function submitPublishedCorrection(event) {
    stopLegacyHandler(event);

    const edit = state.publishedEdit;
    if (!edit?.patch || state.updating) return;

    if (!window.reserveIntelAuth?.isAuthenticated()) {
      showToast("Your GitHub sign-in is required to create the review PR.", "warning");
      return;
    }

    const checks = Array.from(
      byId("update-confirmations").querySelectorAll("input")
    );
    if (checks.length !== 6 || !checks.every((check) => check.checked)) return;

    state.updating = true;
    const button = byId("publish-update-button");
    const backButton = byId("back-to-update-button");
    button.disabled = true;
    button.textContent = "Creating Review PR…";
    backButton.disabled = true;
    byId("update-error").textContent = "";

    try {
      const response = await window.reserveIntelAuth.authenticatedFetch(
        CORRECTION_PATH,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            articleId: edit.article.id,
            baseUpdatedAt: edit.baseUpdatedAt,
            patch: edit.patch,
            confirmations: UPDATE_CHECKS,
          }),
        }
      );

      const payload = await response.json().catch(() => null);
      if (!response.ok || payload?.ok !== true) {
        throw new Error(
          payload?.error || `Could not create the GitHub review PR (HTTP ${response.status}).`
        );
      }

      const article = findItem(edit.article.id, "published");
      state.publishedEdit = null;
      setDirty(false);
      byId("update-dialog").close();
      renderArticle(article, "published");
      renderPrResult(payload);
      showToast(`Created GitHub review PR #${payload.prNumber}.`, "success");
    } catch (error) {
      byId("update-error").textContent =
        error.message || "Could not create the GitHub review PR.";
    } finally {
      state.updating = false;
      button.disabled = false;
      button.textContent = "Create Review PR";
      backButton.disabled = false;
    }
  }

  document.addEventListener(
    "click",
    (event) => {
      const element = event.target instanceof Element ? event.target : null;
      if (!element) return;

      const editButton = element.closest("#edit-published-button");
      if (editButton) {
        beginPublishedEdit(event);
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
          if (publishButton) publishButton.textContent = "Create Review PR";
        });
      }
    },
    true
  );

  const publishButton = byId("publish-update-button");
  if (publishButton) publishButton.textContent = "Create Review PR";
})();
