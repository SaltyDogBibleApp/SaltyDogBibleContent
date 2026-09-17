(() => {
  const API_PATH = "/api/published-article";
  const REASONS = [
    ["SUPERSEDED", "Superseded by newer guidance"],
    ["REPLACED", "Replaced by newer article or policy"],
    ["EXPIRED", "Expired / no longer in effect"],
    ["BOARD_CYCLE_COMPLETE", "Board cycle complete"],
    ["DEADLINE_PASSED", "Deadline or event has passed"],
    ["NO_LONGER_CURRENT", "No longer current"],
    ["OTHER", "Other"],
  ];

  let activeArticle = null;
  let activeReview = null;

  function signedIn() {
    return window.reserveIntelAuth?.isAuthenticated?.() === true;
  }

  async function api(body) {
    if (!signedIn()) throw new Error("Sign in with GitHub to manage the Reserve Intel archive.");
    const response = await window.reserveIntelAuth.authenticatedFetch(API_PATH, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok || payload?.ok !== true) {
      throw new Error(payload?.error || `Archive request failed with HTTP ${response.status}.`);
    }
    return payload;
  }

  function ensureButton() {
    const actions = document.querySelector("#published-update-actions .action-buttons");
    if (!actions || document.getElementById("archive-published-button")) return;
    const button = document.createElement("button");
    button.id = "archive-published-button";
    button.className = "button danger";
    button.type = "button";
    button.textContent = "Archive Article";
    actions.appendChild(button);
    button.addEventListener("click", openArchiveFlow);
  }

  function ensureModal() {
    if (document.getElementById("archive-modal")) return;
    const wrapper = document.createElement("div");
    wrapper.id = "archive-modal";
    wrapper.className = "modal-backdrop hidden";
    wrapper.setAttribute("role", "dialog");
    wrapper.setAttribute("aria-modal", "true");
    wrapper.setAttribute("aria-labelledby", "archive-modal-title");
    wrapper.innerHTML = `
      <div class="modal-card">
        <div class="modal-header">
          <div>
            <div class="eyebrow">ARCHIVE ARTICLE</div>
            <h2 id="archive-modal-title">Move this article to Archive?</h2>
          </div>
          <button id="archive-modal-close" class="modal-close" type="button" aria-label="Close archive dialog">×</button>
        </div>
        <p id="archive-modal-article" class="modal-article-title"></p>
        <div id="archive-form">
          <p class="modal-warning">The article will leave Current Reserve Intel but remain permanently retrievable in the archive. This creates a GitHub review PR before anything changes.</p>
          <label class="modal-label" for="archive-reason">Archive reason</label>
          <select id="archive-reason" class="select-input"></select>
          <label class="modal-label" for="archive-successor">Successor article ID <span class="optional-label">(optional)</span></label>
          <input id="archive-successor" class="text-input" type="text" placeholder="Example: intel-navadmin-100-27">
          <label class="modal-label" for="archive-note">Archive note <span class="optional-label">(optional)</span></label>
          <textarea id="archive-note" class="editor-textarea" rows="4" placeholder="Example: FY27 guidance replaced this FY26 article."></textarea>
          <div class="modal-actions">
            <button id="archive-modal-cancel" class="button secondary" type="button">Cancel</button>
            <button id="archive-create-review" class="button danger" type="button">Create Archive Review</button>
          </div>
        </div>
        <div id="archive-review" class="hidden">
          <p id="archive-review-note" class="modal-warning"></p>
          <div class="modal-actions">
            <a id="archive-review-link" class="button secondary" target="_blank" rel="noopener noreferrer">View in GitHub</a>
            <button id="archive-reject-review" class="button secondary" type="button">Cancel Archive</button>
            <button id="archive-approve-review" class="button danger" type="button">Archive Article</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(wrapper);

    const reason = document.getElementById("archive-reason");
    for (const [value, label] of REASONS) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      reason.appendChild(option);
    }

    document.getElementById("archive-modal-close").addEventListener("click", closeModal);
    document.getElementById("archive-modal-cancel").addEventListener("click", closeModal);
    document.getElementById("archive-create-review").addEventListener("click", createReview);
    document.getElementById("archive-approve-review").addEventListener("click", approveReview);
    document.getElementById("archive-reject-review").addEventListener("click", rejectReview);
    wrapper.addEventListener("click", (event) => {
      if (event.target === wrapper) closeModal();
    });
  }

  function closeModal() {
    document.getElementById("archive-modal")?.classList.add("hidden");
  }

  function showForm() {
    activeReview = null;
    document.getElementById("archive-form").classList.remove("hidden");
    document.getElementById("archive-review").classList.add("hidden");
    document.getElementById("archive-successor").value = "";
    document.getElementById("archive-note").value = "";
    document.getElementById("archive-reason").value = "SUPERSEDED";
  }

  function showReview(review) {
    activeReview = review;
    document.getElementById("archive-form").classList.add("hidden");
    document.getElementById("archive-review").classList.remove("hidden");
    document.getElementById("archive-review-note").textContent =
      `Archive review PR #${review.prNumber} is ready. Approving it moves the article from Current to Archive.`;
    const link = document.getElementById("archive-review-link");
    link.href = review.prUrl;
  }

  async function openArchiveFlow() {
    if (state.selectedKind !== "published" || state.publishedEdit || state.updating || state.updateLoading) {
      showToast("Finish the current edit before archiving this article.", "warning");
      return;
    }
    activeArticle = findItem(state.selectedId, "published");
    if (!activeArticle) return;

    if (!signedIn()) {
      window.reserveIntelAuth?.signIn?.();
      return;
    }

    ensureModal();
    document.getElementById("archive-modal-article").textContent = activeArticle.title || activeArticle.id;
    document.getElementById("archive-modal").classList.remove("hidden");
    showForm();

    const createButton = document.getElementById("archive-create-review");
    createButton.disabled = true;
    createButton.textContent = "Checking…";
    try {
      const status = await api({ action: "archive-status", articleId: activeArticle.id });
      if (status.archiveReview) showReview(status.archiveReview);
    } catch (error) {
      closeModal();
      showToast(error.message, "warning");
    } finally {
      createButton.disabled = false;
      createButton.textContent = "Create Archive Review";
    }
  }

  async function createReview() {
    if (!activeArticle) return;
    const button = document.getElementById("archive-create-review");
    button.disabled = true;
    button.textContent = "Creating Review…";
    try {
      const successor = document.getElementById("archive-successor").value.trim() || null;
      const payload = await api({
        action: "create-archive",
        articleId: activeArticle.id,
        baseUpdatedAt: activeArticle.updatedAt || null,
        reason: document.getElementById("archive-reason").value,
        note: document.getElementById("archive-note").value,
        successorArticleId: successor,
      });
      showReview(payload);
      showToast("Archive review created.", "success");
    } catch (error) {
      showToast(error.message, "warning");
    } finally {
      button.disabled = false;
      button.textContent = "Create Archive Review";
    }
  }

  async function approveReview() {
    if (!activeArticle || !activeReview) return;
    if (!window.confirm("Archive this article now? It will leave Current Reserve Intel but remain in Archive.")) return;
    const button = document.getElementById("archive-approve-review");
    button.disabled = true;
    button.textContent = "Archiving…";
    try {
      await api({
        action: "approve-archive",
        articleId: activeArticle.id,
        prNumber: activeReview.prNumber,
      });
      const archivedId = activeArticle.id;
      if (state.data?.published) {
        state.data.published = state.data.published.filter((item) => item.id !== archivedId);
      }
      state.selectedId = null;
      state.selectedKind = null;
      state.publishedEdit = null;
      renderQueues();
      renderOperationalStatus();
      byId("article-view")?.classList.add("hidden");
      byId("empty-state")?.classList.remove("hidden");
      closeModal();
      showToast("Article moved to Archive.", "success");
    } catch (error) {
      showToast(error.message, "warning");
    } finally {
      button.disabled = false;
      button.textContent = "Archive Article";
    }
  }

  async function rejectReview() {
    if (!activeArticle || !activeReview) return;
    const button = document.getElementById("archive-reject-review");
    button.disabled = true;
    button.textContent = "Cancelling…";
    try {
      await api({
        action: "reject-archive",
        articleId: activeArticle.id,
        prNumber: activeReview.prNumber,
      });
      showForm();
      showToast("Archive review cancelled. The article remains Current.", "success");
    } catch (error) {
      showToast(error.message, "warning");
    } finally {
      button.disabled = false;
      button.textContent = "Cancel Archive";
    }
  }

  ensureButton();
  ensureModal();
})();
