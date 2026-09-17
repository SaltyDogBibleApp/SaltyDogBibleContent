

const state = {
  data: null,
  selectedId: null,
  selectedKind: null,
  dirty: false,
  saveServiceAvailable: false,
  rejectServiceAvailable: false,
  approveServiceAvailable: false,
  refreshServiceAvailable: false,
  saveServiceRepository: null,
  dashboardMainRef: "origin/main",
  saving: false,
  refreshing: false,
  rejecting: false,
  approving: false,
  publishedEdit: null,
  updateLoading: false,
  updating: false,
};

const CATEGORIES = [
  "Legislation / NDAA",
  "Policy",
  "Pay & Benefits",
  "Retirement",
  "VA / Veteran Benefits",
  "Training & Readiness",
  "Admin",
  "Other",
];

const STATUSES = [
  "TRACKING",
  "PROPOSED",
  "INTRODUCED",
  "COMMITTEE",
  "PASSED HOUSE",
  "PASSED SENATE",
  "SIGNED",
  "EFFECTIVE",
  "SUPERSEDED",
];

function byId(id) {
  return document.getElementById(id);
}

function safe(value, fallback = "Not specified") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function formatDate(value) {
  if (!value) return "Not specified";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(d);
}

function formatDateTime(value) {
  if (!value) return "Unknown";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(d);
}

function latestPublishedTimestamp(items) {
  const timestamps = (items || [])
    .map((item) => item?.updatedAt || item?.publishedAt)
    .filter(Boolean)
    .sort();
  return timestamps.length ? timestamps[timestamps.length - 1] : null;
}

function renderOperationalStatus() {
  const data = state.data || {};
  byId("ops-refreshed").textContent = formatDateTime(data.generatedAt);
  byId("ops-pending").textContent = String((data.pending || []).length);
  byId("ops-published").textContent = String((data.published || []).length);
  byId("ops-last-published").textContent =
    formatDateTime(latestPublishedTimestamp(data.published));
  byId("ops-main-ref").textContent =
    data.mainRef || state.dashboardMainRef || "origin/main";

  const button = byId("refresh-queue-button");
  button.disabled = state.refreshing || !state.refreshServiceAvailable;
  button.textContent = state.refreshing ? "Refreshing…" : "Refresh Queue";
  button.classList.toggle("refreshing", state.refreshing);
}

function isoToDateInput(value) {
  if (!value) return "";
  const match = String(value).match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : "";
}

function dateInputToIso(value) {
  return value ? `${value}T00:00:00Z` : null;
}

function showToast(message, tone = "neutral") {
  const toast = byId("toast");
  toast.textContent = message;
  toast.className = `toast ${tone}`.trim();
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.classList.add("hidden");
  }, 3600);
}

function setDirty(value) {
  state.dirty = value;
  byId("dirty-pill").classList.toggle("hidden", !value);
  if (state.publishedEdit) byId("review-update-button").disabled = !value || state.updating;

  if (state.selectedKind === "pending" && state.data) {
    const item = findItem(state.selectedId, "pending");
    if (item) configureActions(item);
  }
}

function createQueueCard(item, kind) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "queue-card";
  button.dataset.id = item.id;
  button.dataset.kind = kind;
  button.style.textAlign = "left";
  button.style.width = "100%";

  const title = document.createElement("div");
  title.className = "queue-card-title";
  title.textContent = item.title || item.id;

  const meta = document.createElement("div");
  meta.className = "queue-card-meta";

  const parts = [item.priority, item.status, item.sourceName].filter(Boolean);
  parts.forEach((part) => {
    const span = document.createElement("span");
    span.textContent = part;
    meta.appendChild(span);
  });

  if (item._demo === true) {
    const demo = document.createElement("span");
    demo.className = "queue-demo-pill";
    demo.textContent = "DEMO";
    meta.appendChild(demo);
  }

  button.appendChild(title);
  button.appendChild(meta);

  button.addEventListener("click", () => selectItem(item.id, kind));
  return button;
}

function renderQueues() {
  const pendingList = byId("pending-list");
  const publishedList = byId("published-list");
  pendingList.innerHTML = "";
  publishedList.innerHTML = "";

  const pending = state.data.pending || [];
  const published = state.data.published || [];

  byId("pending-count").textContent = pending.length;

  if (!pending.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.style.padding = "8px";
    empty.textContent = "No articles currently need review.";
    pendingList.appendChild(empty);
  } else {
    pending.forEach((item) => pendingList.appendChild(createQueueCard(item, "pending")));
  }

  if (!published.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.style.padding = "8px";
    empty.textContent = "No published history available.";
    publishedList.appendChild(empty);
  } else {
    published.forEach((item) => publishedList.appendChild(createQueueCard(item, "published")));
  }
}

function findItem(id, kind) {
  const collection = kind === "pending" ? state.data.pending : state.data.published;
  return collection.find((item) => item.id === id);
}

function selectItem(id, kind) {
  if (state.updating || state.updateLoading) return;
  if (state.publishedEdit && id === state.selectedId && kind === state.selectedKind) return;
  if (state.dirty && (id !== state.selectedId || kind !== state.selectedKind)) {
    const leave = window.confirm("You have unsaved browser-only edits. Discard them and open another article?");
    if (!leave) return;
  }

  const item = findItem(id, kind);
  if (!item) return;

  state.publishedEdit = null;
  state.selectedId = id;
  state.selectedKind = kind;
  setDirty(false);

  document.querySelectorAll(".queue-card").forEach((card) => {
    card.classList.toggle(
      "selected",
      card.dataset.id === id && card.dataset.kind === kind
    );
  });

  renderArticle(item, kind);
}

function addBadge(label, cssClass = "") {
  const span = document.createElement("span");
  span.className = `badge ${cssClass}`.trim();
  span.textContent = label;
  byId("badges").appendChild(span);
}

function addMetadata(label, value) {
  const row = document.createElement("div");
  row.className = "metadata-row";

  const dt = document.createElement("dt");
  dt.textContent = label;

  const dd = document.createElement("dd");
  dd.textContent = safe(value);

  row.appendChild(dt);
  row.appendChild(dd);
  byId("metadata-list").appendChild(row);
}

function renderReviewStatus(item, kind) {
  const target = byId("review-status");
  target.innerHTML = "";

  const checklist = item.reviewChecklist || {};
  const checks = [
    ["Source opened", checklist.sourceOpenedAndRead],
    ["Facts verified", checklist.factsVerifiedAgainstSource],
    ["Status / date verified", checklist.statusVerified && checklist.effectiveDateVerified],
    ["Audience verified", checklist.audienceVerified],
    [
      "Wording reviewed",
      checklist.summaryRewrittenFromSource &&
        checklist.whyItMattersRewrittenFromSource &&
        checklist.detailsRewrittenFromSource,
    ],
    ["Approved for publication", checklist.approvedForPublication],
  ];

  if (kind !== "pending") {
    checks.length = 0;
    checks.push(["Published", true]);
  }

  checks.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "review-item";

    const dot = document.createElement("span");
    dot.className = `review-dot ${value === true ? "complete" : ""}`.trim();
    dot.textContent = value === true ? "✓" : "○";

    const text = document.createElement("span");
    text.textContent = label;

    row.appendChild(dot);
    row.appendChild(text);
    target.appendChild(row);
  });
}

function renderEvidence(item) {
  const section = byId("evidence-section");
  const target = byId("evidence-content");
  target.innerHTML = "";

  const evidence = item.textComparison;
  if (!evidence || evidence.available !== true) {
    section.classList.add("hidden");
    return;
  }

  section.classList.remove("hidden");

  const summary = document.createElement("div");
  summary.className = "muted";
  summary.textContent =
    `Extracted text changed: ${evidence.changed === true ? "Yes" : "No"} · ` +
    `Added lines: ${safe(evidence.addedLines, "0")} · ` +
    `Removed lines: ${safe(evidence.removedLines, "0")}`;
  target.appendChild(summary);

  const hunks = Array.isArray(evidence.hunks) ? evidence.hunks : [];
  hunks.forEach((hunk) => {
    const box = document.createElement("div");
    box.className = "diff-hunk";

    const heading = document.createElement("div");
    heading.className = "diff-heading";
    heading.textContent = [
      hunk.heading,
      hunk.page ? `Page ${hunk.page}` : null,
    ].filter(Boolean).join(" · ") || "Detected text change";
    box.appendChild(heading);

    const removed = Array.isArray(hunk.removedLines) ? hunk.removedLines : [];
    const added = Array.isArray(hunk.addedLines) ? hunk.addedLines : [];

    removed.forEach((line) => {
      const el = document.createElement("div");
      el.className = "diff-line removed";
      el.textContent = `- ${line}`;
      box.appendChild(el);
    });

    added.forEach((line) => {
      const el = document.createElement("div");
      el.className = "diff-line added";
      el.textContent = `+ ${line}`;
      box.appendChild(el);
    });

    target.appendChild(box);
  });

  if (!hunks.length) {
    const noHunks = document.createElement("div");
    noHunks.className = "muted";
    noHunks.style.marginTop = "12px";
    noHunks.textContent = "No displayable text-diff hunks were included.";
    target.appendChild(noHunks);
  }
}

function populateSelect(select, values, selectedValue) {
  select.innerHTML = "";
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    option.selected = value === selectedValue;
    select.appendChild(option);
  });
}

function renderSegmentedControl(containerId, options, selectedValue, onChange) {
  const container = byId(containerId);
  container.innerHTML = "";

  options.forEach(({ value, label }) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `segment-button ${value === selectedValue ? "selected" : ""}`.trim();
    button.textContent = label;
    button.dataset.value = String(value);
    button.addEventListener("click", () => {
      container.querySelectorAll(".segment-button").forEach((el) => el.classList.remove("selected"));
      button.classList.add("selected");
      onChange(value);
      setDirty(true);
    });
    container.appendChild(button);
  });
}

function selectedSegmentValue(containerId) {
  const selected = byId(containerId).querySelector(".segment-button.selected");
  return selected ? selected.dataset.value : null;
}

function attachDirtyInput(id) {
  byId(id).addEventListener("input", () => setDirty(true));
  byId(id).addEventListener("change", () => setDirty(true));
}

function populateEditor(item) {
  byId("edit-title").value = item.title || "";
  byId("edit-summary").value = item.summary || "";
  byId("edit-why").value = item.whyItMatters || "";
  byId("edit-details").value = item.details || "";
  byId("edit-effective-date").value = isoToDateInput(item.effectiveDate);
  byId("edit-training-wing").value = item.audience?.trainingWing || "";
  byId("edit-squadron").value = item.audience?.squadron || "";

  populateSelect(byId("edit-category"), CATEGORIES, item.category || "Other");
  populateSelect(byId("edit-status"), STATUSES, item.status || "TRACKING");

  renderSegmentedControl(
    "priority-control",
    [
      { value: "NORMAL", label: "NORMAL" },
      { value: "HIGH", label: "HIGH" },
    ],
    item.priority || "NORMAL",
    () => {}
  );

  renderSegmentedControl(
    "service-control",
    [
      { value: "ALL", label: "ALL" },
      { value: "USN", label: "USN" },
      { value: "USMC", label: "USMC" },
    ],
    item.audience?.service || "ALL",
    () => {}
  );

  renderSegmentedControl(
    "reserve-status-control",
    [
      { value: "ALL", label: "ALL" },
      { value: "SELRES", label: "SELRES" },
      { value: "VTU", label: "VTU" },
    ],
    item.audience?.reserveStatus || "ALL",
    () => {}
  );

  renderSegmentedControl(
    "pinned-control",
    [
      { value: "false", label: "No" },
      { value: "true", label: "Yes" },
    ],
    item.isPinned === true ? "true" : "false",
    () => {}
  );
}

function editorSnapshot() {
  return {
    title: byId("edit-title").value.trim(),
    summary: byId("edit-summary").value.trim(),
    whyItMatters: byId("edit-why").value.trim(),
    details: byId("edit-details").value.trim(),
    category: byId("edit-category").value,
    status: byId("edit-status").value,
    priority: selectedSegmentValue("priority-control") || "NORMAL",
    effectiveDate: dateInputToIso(byId("edit-effective-date").value),
    audience: {
      service: selectedSegmentValue("service-control") || "ALL",
      reserveStatus: selectedSegmentValue("reserve-status-control") || "ALL",
      trainingWing: byId("edit-training-wing").value.trim() || null,
      squadron: byId("edit-squadron").value.trim() || null,
    },
    isPinned: selectedSegmentValue("pinned-control") === "true",
  };
}

function validateEditorSnapshot(snapshot) {
  const required = [
    ["Title", snapshot.title],
    ["Summary", snapshot.summary],
    ["Why It Matters", snapshot.whyItMatters],
    ["Details", snapshot.details],
  ];

  const missing = required.filter(([, value]) => !value).map(([label]) => label);
  if (missing.length) {
    throw new Error(`Complete these fields before saving: ${missing.join(", ")}`);
  }
}

function applySavedArticleToItem(item, article) {
  const preserved = {
    _sourceFile: item._sourceFile,
    _reviewBranch: item._reviewBranch,
    _contentOrigin: item._contentOrigin,
    _saveEligible: item._saveEligible,
    _demo: item._demo,
    reviewChecklist: item.reviewChecklist,
    textComparison: item.textComparison,
  };

  Object.assign(item, article, preserved);
}

function rerenderSelectedPending(item) {
  setDirty(false);
  renderQueues();
  document.querySelectorAll(".queue-card").forEach((card) => {
    card.classList.toggle(
      "selected",
      card.dataset.id === state.selectedId && card.dataset.kind === state.selectedKind
    );
  });
  renderArticle(item, "pending");
}

function saveDemoLocally(item, snapshot) {
  Object.assign(item, snapshot);
  item.audience = snapshot.audience;
  rerenderSelectedPending(item);
  showToast("Demo draft saved in this browser only. GitHub was not changed.", "success");
}

async function saveDraft() {
  if (state.selectedKind !== "pending" || state.saving) return;

  const item = findItem(state.selectedId, "pending");
  if (!item) return;

  const snapshot = editorSnapshot();

  try {
    validateEditorSnapshot(snapshot);
  } catch (error) {
    showToast(error.message, "warning");
    return;
  }

  if (item._demo === true) {
    saveDemoLocally(item, snapshot);
    return;
  }

  if (item._saveEligible !== true) {
    showToast("This review branch is not ready for safe saving yet. Use Refresh Queue after the Review PR is created.", "warning");
    return;
  }

  if (!state.saveServiceAvailable) {
    showToast("Save service is unavailable. Start the dashboard with automation/start_review_dashboard.py.", "warning");
    return;
  }

  state.saving = true;
  configureActions(item);

  try {
    const response = await fetch("/api/reserve-intel/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        articleId: item.id,
        sourceFile: item._sourceFile,
        reviewBranch: item._reviewBranch,
        articleDraftPatch: snapshot,
      }),
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.error || `Save failed with HTTP ${response.status}`);
    }

    applySavedArticleToItem(item, payload.article);
    item._contentOrigin = "reviewBranch";
    item._saveEligible = true;
    rerenderSelectedPending(item);
    await syncDashboardAfterAction(payload, { preserveSelection: true });

    if (payload.changed === false) {
      showToast("No changes to save. The review branch already matches the editor.", "success");
    } else {
      const shortSha = payload.commitSha ? payload.commitSha.slice(0, 7) : null;
      showToast(
        shortSha
          ? `Saved to the review branch in commit ${shortSha}.`
          : "Saved to the review branch.",
        "success"
      );
    }
  } catch (error) {
    showToast(error.message || "Save failed.", "warning");
  } finally {
    state.saving = false;
    configureActions(item);
  }
}

async function checkSaveService() {
  const status = byId("save-service-status");

  try {
    const response = await fetch("/api/reserve-intel/health", { cache: "no-store" });
    const payload = await response.json();

    if (!response.ok || payload?.ok !== true || payload?.saveEnabled !== true) {
      throw new Error("Save service unavailable");
    }

    state.saveServiceAvailable = true;
    state.rejectServiceAvailable = payload?.rejectEnabled === true;
    state.approveServiceAvailable = payload?.approveEnabled === true;
    state.refreshServiceAvailable = payload?.manualRefreshEnabled === true;
    state.saveServiceRepository = payload.repository || null;
    state.dashboardMainRef = payload?.dashboardMainRef || "origin/main";
    status.textContent = (state.rejectServiceAvailable && state.approveServiceAvailable)
      ? "Review service connected"
      : "Save service connected";
    status.className = "service-status connected";
  } catch {
    state.saveServiceAvailable = false;
    state.rejectServiceAvailable = false;
    state.approveServiceAvailable = false;
    state.refreshServiceAvailable = false;
    state.saveServiceRepository = null;
    status.textContent = "Review service unavailable";
    status.className = "service-status unavailable";
  }
}

async function fetchDashboardSnapshot() {
  const response = await fetch(`data.json?ts=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Dashboard data failed with HTTP ${response.status}`);
  return response.json();
}

function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function fetchInitialDashboardSnapshot({
  attempts = 10,
  delayMs = 500,
} = {}) {
  let lastError = null;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await fetchDashboardSnapshot();
    } catch (error) {
      lastError = error;

      if (attempt === attempts) break;

      byId("generated-at").textContent =
        `Waiting for dashboard data… (${attempt}/${attempts})`;
      byId("ops-refreshed").textContent = "Starting…";

      await wait(delayMs);
    }
  }

  throw lastError || new Error("Dashboard data did not become available.");
}

function applyDashboardSnapshot(data, { preserveSelection = true } = {}) {
  const previousId = preserveSelection ? state.selectedId : null;
  const previousKind = preserveSelection ? state.selectedKind : null;

  state.data = data;
  byId("generated-at").textContent =
    `Dashboard generated ${formatDateTime(state.data.generatedAt)}`;
  byId("preview-banner").classList.toggle("hidden", state.data.demoMode !== true);

  setDirty(false);
  renderOperationalStatus();
  renderQueues();

  if (
    previousId &&
    previousKind &&
    findItem(previousId, previousKind)
  ) {
    selectItem(previousId, previousKind);
    return;
  }

  state.selectedId = null;
  state.selectedKind = null;

  if ((state.data.pending || []).length) {
    selectItem(state.data.pending[0].id, "pending");
  } else if ((state.data.published || []).length) {
    selectItem(state.data.published[0].id, "published");
  } else {
    byId("article-view").classList.add("hidden");
    byId("empty-state").classList.remove("hidden");
  }
}

async function reloadDashboardSnapshot(options = {}) {
  const data = await fetchDashboardSnapshot();
  applyDashboardSnapshot(data, options);
}

async function syncDashboardAfterAction(payload, options = {}) {
  if (payload?.dashboardRefresh?.ok !== true) return;
  try {
    await reloadDashboardSnapshot(options);
  } catch (error) {
    console.warn("Dashboard action succeeded but browser refresh failed:", error);
  }
}

async function refreshQueue() {
  if (state.refreshing) return;

  if (!state.refreshServiceAvailable) {
    showToast("Refresh service is unavailable. Start the dashboard with start_review_dashboard.py.", "warning");
    return;
  }

  if (state.dirty) {
    const discard = window.confirm(
      "You have unsaved browser edits. Refreshing the queue will discard them. Continue?"
    );
    if (!discard) return;
  }

  state.refreshing = true;
  renderOperationalStatus();

  try {
    const response = await fetch("/api/reserve-intel/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.error || `Refresh failed with HTTP ${response.status}`);
    }

    await checkSaveService();
    await reloadDashboardSnapshot({ preserveSelection: true });
    showToast(
      `Queue refreshed: ${payload.pending ?? "?"} pending, ${payload.published ?? "?"} published.`,
      "success"
    );
  } catch (error) {
    showToast(error.message || "Queue refresh failed.", "warning");
  } finally {
    state.refreshing = false;
    renderOperationalStatus();
  }
}

function configureActions(item) {
  const saveButton = byId("save-draft-button");
  const rejectButton = byId("reject-button");
  const approveButton = byId("approve-button");
  const modePill = byId("action-mode-pill");
  const actionNote = byId("action-note");

  if (!item || state.selectedKind !== "pending") return;

  if (item._demo === true) {
    saveButton.disabled = state.saving || state.rejecting || state.approving;
    saveButton.textContent = state.saving ? "Saving…" : "Save Draft";
    rejectButton.disabled = false;
    rejectButton.textContent = "Reject";
    approveButton.disabled = false;
    approveButton.textContent = "Approve for Publication";
    modePill.textContent = "DEMO";
    modePill.className = "preview-only-pill";
    actionNote.textContent = "Demo actions stay in this browser. Nothing is changed in GitHub.";
    return;
  }

  const ready = item._saveEligible === true;
  const saveConnected = state.saveServiceAvailable === true;
  const rejectConnected = state.rejectServiceAvailable === true;
  const approveConnected = state.approveServiceAvailable === true;
  const busy = state.saving || state.rejecting || state.approving;

  saveButton.disabled = busy || !ready || !saveConnected;
  saveButton.textContent = state.saving ? "Saving…" : "Save Draft";

  rejectButton.disabled = busy || !ready || !rejectConnected;
  rejectButton.textContent = state.rejecting ? "Rejecting…" : "Reject";

  approveButton.disabled = busy || state.dirty || !ready || !approveConnected;
  approveButton.textContent = state.approving ? "Approving…" : "Approve for Publication";

  if (ready && saveConnected && rejectConnected && approveConnected) {
    modePill.textContent = "ALL ACTIONS LIVE";
    modePill.className = "preview-only-pill all-live";
    actionNote.textContent = state.dirty
      ? "Save the current browser edits before approving. Reject closes without merge; Approve merges the exact Review PR and starts the existing publication workflow."
      : `Save commits editable fields to ${item._reviewBranch}. Reject closes without merge. Approve requires six confirmations, then merges the exact Review PR and starts the existing publication workflow.`;
  } else if (!ready) {
    modePill.textContent = "WAITING";
    modePill.className = "preview-only-pill waiting";
    actionNote.textContent = "The enriched review branch is not available yet. Use Refresh Queue after the Review PR is created.";
  } else {
    modePill.textContent = "REVIEW OFFLINE";
    modePill.className = "preview-only-pill waiting";
    actionNote.textContent = "Start automation/start_review_dashboard.py to enable the live review actions.";
  }
}

function closeRejectModal() {
  byId("reject-modal").classList.add("hidden");
  byId("reject-reason").value = "";
}

function openRejectModal() {
  if (state.selectedKind !== "pending") return;

  const item = findItem(state.selectedId, "pending");
  if (!item) return;

  if (item._demo === true) {
    showToast("Demo Reject is preview-only. Nothing was changed in GitHub.", "warning");
    return;
  }

  if (item._saveEligible !== true) {
    showToast("This review branch is not ready for safe rejection yet.", "warning");
    return;
  }

  if (!state.rejectServiceAvailable) {
    showToast("Reject service is unavailable. Start the dashboard with automation/start_review_dashboard.py.", "warning");
    return;
  }

  byId("reject-modal-article").textContent = item.title || item.id;
  byId("reject-reason").value = "";
  byId("reject-modal").classList.remove("hidden");
  setTimeout(() => byId("reject-reason").focus(), 0);
}

function removeRejectedItemFromDashboard(articleId) {
  state.data.pending = (state.data.pending || []).filter(item => item.id !== articleId);
  state.selectedId = null;
  state.selectedKind = null;
  setDirty(false);

  renderQueues();

  if ((state.data.pending || []).length) {
    selectItem(state.data.pending[0].id, "pending");
    return;
  }

  if ((state.data.published || []).length) {
    selectItem(state.data.published[0].id, "published");
    return;
  }

  byId("article-view").classList.add("hidden");
  byId("empty-state").classList.remove("hidden");
}

async function rejectSelectedArticle() {
  if (state.selectedKind !== "pending" || state.rejecting) return;

  const item = findItem(state.selectedId, "pending");
  if (!item || item._demo === true) return;

  const reason = byId("reject-reason").value.trim();
  if (reason.length > 2000) {
    showToast("Rejection reason must be 2,000 characters or fewer.", "warning");
    return;
  }

  state.rejecting = true;
  byId("reject-modal-confirm").disabled = true;
  byId("reject-modal-confirm").textContent = "Rejecting…";
  configureActions(item);

  try {
    const response = await fetch("/api/reserve-intel/reject", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        articleId: item.id,
        sourceFile: item._sourceFile,
        reviewBranch: item._reviewBranch,
        reason,
      }),
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.error || `Reject failed with HTTP ${response.status}`);
    }

    const rejectedId = item.id;
    closeRejectModal();
    removeRejectedItemFromDashboard(rejectedId);
    await syncDashboardAfterAction(payload, { preserveSelection: false });

    showToast(
      `Closed Review PR #${payload.prNumber} without merge. The rejection workflow can now archive the draft.`,
      "success"
    );
  } catch (error) {
    showToast(error.message || "Reject failed.", "warning");
  } finally {
    state.rejecting = false;
    byId("reject-modal-confirm").disabled = false;
    byId("reject-modal-confirm").textContent = "Reject Article";

    const current = state.selectedKind === "pending"
      ? findItem(state.selectedId, "pending")
      : null;
    if (current) configureActions(current);
  }
}

function approvalCheckboxes() {
  return Array.from(document.querySelectorAll(".approval-confirmation"));
}

function updateApproveConfirmationState() {
  const checks = approvalCheckboxes();
  byId("approve-modal-confirm").disabled =
    state.approving || checks.length !== 6 || checks.some((check) => !check.checked);
}

function closeApproveModal() {
  byId("approve-modal").classList.add("hidden");
  approvalCheckboxes().forEach((check) => {
    check.checked = false;
  });
  updateApproveConfirmationState();
}

function openApproveModal() {
  if (state.selectedKind !== "pending") return;

  const item = findItem(state.selectedId, "pending");
  if (!item) return;

  if (item._demo === true) {
    showToast("Demo Approve is preview-only. Nothing was changed in GitHub.", "warning");
    return;
  }

  if (state.dirty) {
    showToast("Save or discard the current browser edits before approving.", "warning");
    return;
  }

  if (item._saveEligible !== true) {
    showToast("This review branch is not ready for safe approval yet.", "warning");
    return;
  }

  if (!state.approveServiceAvailable) {
    showToast("Approve service is unavailable. Start the dashboard with automation/start_review_dashboard.py.", "warning");
    return;
  }

  byId("approve-modal-article").textContent = item.title || item.id;
  approvalCheckboxes().forEach((check) => {
    check.checked = false;
  });
  updateApproveConfirmationState();
  byId("approve-modal").classList.remove("hidden");
}

function removeApprovedItemFromDashboard(articleId) {
  state.data.pending = (state.data.pending || []).filter((item) => item.id !== articleId);
  state.selectedId = null;
  state.selectedKind = null;
  setDirty(false);

  renderQueues();

  if ((state.data.pending || []).length) {
    selectItem(state.data.pending[0].id, "pending");
    return;
  }

  if ((state.data.published || []).length) {
    selectItem(state.data.published[0].id, "published");
    return;
  }

  byId("article-view").classList.add("hidden");
  byId("empty-state").classList.remove("hidden");
}

async function approveSelectedArticle() {
  if (state.selectedKind !== "pending" || state.approving) return;

  const item = findItem(state.selectedId, "pending");
  if (!item || item._demo === true) return;

  const checks = approvalCheckboxes();
  if (checks.length !== 6 || checks.some((check) => !check.checked)) {
    showToast("All six approval confirmations are required.", "warning");
    return;
  }

  if (state.dirty) {
    showToast("Save or discard the current browser edits before approving.", "warning");
    return;
  }

  state.approving = true;
  byId("approve-modal-confirm").disabled = true;
  byId("approve-modal-confirm").textContent = "Approving…";
  configureActions(item);

  try {
    const response = await fetch("/api/reserve-intel/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        articleId: item.id,
        sourceFile: item._sourceFile,
        reviewBranch: item._reviewBranch,
        approvalConfirmed: true,
      }),
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.error || `Approve failed with HTTP ${response.status}`);
    }

    const approvedId = item.id;
    closeApproveModal();
    removeApprovedItemFromDashboard(approvedId);
    await syncDashboardAfterAction(payload, { preserveSelection: false });

    showToast(
      `Merged Review PR #${payload.prNumber}. The existing publication workflow has started; publication is not considered complete until that workflow succeeds.`,
      "success"
    );
  } catch (error) {
    showToast(error.message || "Approve failed.", "warning");
  } finally {
    state.approving = false;
    byId("approve-modal-confirm").textContent = "Approve & Merge PR";
    updateApproveConfirmationState();

    const current = state.selectedKind === "pending"
      ? findItem(state.selectedId, "pending")
      : null;
    if (current) configureActions(current);
  }
}

function renderArticle(item, kind) {
  const publishedEditing = kind === "published" && state.publishedEdit?.article.id === item.id;
  const editable = kind === "pending" || publishedEditing;
  byId("published-update-actions").classList.toggle("hidden", kind !== "published");
  byId("edit-published-button").classList.toggle("hidden", !!publishedEditing);
  byId("edit-published-button").disabled = item.isActive !== true;
  byId("review-update-button").classList.toggle("hidden", !publishedEditing);
  byId("cancel-update-button").classList.toggle("hidden", !publishedEditing);
  byId("published-update-note").textContent = publishedEditing
    ? "Your edits stay in this tab until you approve the update. The published article remains live."
    : item.isActive !== true ? "This article is inactive and cannot be updated here."
    : "Edit this article, review your changes, then approve the update. GitHub sign-in is required.";

  byId("empty-state").classList.add("hidden");
  byId("article-view").classList.remove("hidden");
  byId("article-kicker").textContent = publishedEditing ? "EDITING PUBLISHED ARTICLE" : editable ? "PENDING HUMAN REVIEW" : "PUBLISHED";

  byId("article-title").textContent = item.title || item.id;
  byId("article-summary").textContent = safe(item.summary, "No summary provided.");
  byId("article-why").textContent = safe(item.whyItMatters, "No Why It Matters text provided.");
  byId("article-details").textContent = safe(item.details, "No details provided.");

  byId("article-title").classList.toggle("hidden", editable);
  byId("title-editor-wrap").classList.toggle("hidden", !editable);
  byId("article-summary").classList.toggle("hidden", editable);
  byId("edit-summary").classList.toggle("hidden", !editable);
  byId("article-why").classList.toggle("hidden", editable);
  byId("edit-why").classList.toggle("hidden", !editable);
  byId("article-details").classList.toggle("hidden", editable);
  byId("edit-details").classList.toggle("hidden", !editable);
  byId("metadata-display-card").classList.toggle("hidden", editable);
  byId("metadata-editor-card").classList.toggle("hidden", !editable);
  byId("editor-actions").classList.toggle("hidden", kind !== "pending");

  if (editable) {
    populateEditor(item);
    setDirty(false);
    configureActions(item);
  }

  const sourceButton = byId("source-button");
  sourceButton.href = item.sourceURL || "#";
  sourceButton.classList.toggle("hidden", !item.sourceURL);

  const badges = byId("badges");
  badges.innerHTML = "";
  if (item._demo === true) addBadge("DEMO");
  if (item.priority) addBadge(item.priority, item.priority === "HIGH" ? "high" : "");
  if (item.status) addBadge(item.status);
  if (item.category) addBadge(item.category);

  const metadata = byId("metadata-list");
  metadata.innerHTML = "";
  addMetadata("Effective Date", formatDate(item.effectiveDate));
  addMetadata("Service", item.audience?.service);
  addMetadata("Reserve Status", item.audience?.reserveStatus);
  addMetadata("Training Wing", item.audience?.trainingWing || "All");
  addMetadata("Squadron", item.audience?.squadron || "All");
  addMetadata("Published", formatDateTime(item.publishedAt));
  addMetadata("Updated", formatDateTime(item.updatedAt));
  addMetadata("Article ID", item.id);

  renderReviewStatus(item, kind);
  byId("source-name").textContent = safe(item.sourceName);
  byId("source-url").textContent = safe(item.sourceURL);
  renderEvidence(item);
}

function bindEditorEvents() {
  byId("edit-published-button").addEventListener("click", editPublishedArticle);
  byId("cancel-update-button").addEventListener("click", cancelPublishedEdit);
  byId("review-update-button").addEventListener("click", reviewPublishedUpdate);
  byId("back-to-update-button").addEventListener("click", () => byId("update-dialog").close());
  byId("publish-update-button").addEventListener("click", publishArticleUpdate);
  byId("update-dialog").addEventListener("cancel", event => { if (state.updating) event.preventDefault(); });
  window.addEventListener("beforeunload", event => {
    if (state.dirty || state.updating) { event.preventDefault(); event.returnValue = ""; }
  });
  [
    "edit-title",
    "edit-summary",
    "edit-why",
    "edit-details",
    "edit-category",
    "edit-status",
    "edit-effective-date",
    "edit-training-wing",
    "edit-squadron",
  ].forEach(attachDirtyInput);

  byId("clear-effective-date").addEventListener("click", () => {
    byId("edit-effective-date").value = "";
    setDirty(true);
  });

  byId("refresh-queue-button").addEventListener("click", refreshQueue);
  byId("save-draft-button").addEventListener("click", saveDraft);
  byId("reject-button").addEventListener("click", openRejectModal);
  byId("approve-button").addEventListener("click", openApproveModal);

  byId("reject-modal-close").addEventListener("click", closeRejectModal);
  byId("reject-modal-cancel").addEventListener("click", closeRejectModal);
  byId("reject-modal-confirm").addEventListener("click", rejectSelectedArticle);
  byId("reject-modal").addEventListener("click", (event) => {
    if (event.target === byId("reject-modal")) closeRejectModal();
  });

  byId("approve-modal-close").addEventListener("click", closeApproveModal);
  byId("approve-modal-cancel").addEventListener("click", closeApproveModal);
  byId("approve-modal-confirm").addEventListener("click", approveSelectedArticle);
  byId("approve-modal").addEventListener("click", (event) => {
    if (event.target === byId("approve-modal")) closeApproveModal();
  });
  approvalCheckboxes().forEach((check) => {
    check.addEventListener("change", updateApproveConfirmationState);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!byId("reject-modal").classList.contains("hidden")) closeRejectModal();
    if (!byId("approve-modal").classList.contains("hidden")) closeApproveModal();
  });
}

async function load() {
  try {
    await checkSaveService();

    let data = null;

    try {
      data = await fetchInitialDashboardSnapshot();
    } catch (initialError) {
      if (!state.refreshServiceAvailable) throw initialError;

      byId("generated-at").textContent = "Refreshing dashboard data…";
      byId("ops-refreshed").textContent = "Refreshing…";

      const response = await fetch("/api/reserve-intel/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      let payload = null;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }

      if (!response.ok || !payload?.ok) {
        throw new Error(
          payload?.error ||
          initialError?.message ||
          `Startup refresh failed with HTTP ${response.status}`
        );
      }

      data = await fetchInitialDashboardSnapshot({
        attempts: 6,
        delayMs: 350,
      });
    }

    applyDashboardSnapshot(data, { preserveSelection: false });
  } catch (error) {
    byId("generated-at").textContent = "Dashboard data unavailable";
    byId("ops-refreshed").textContent = "Unavailable";
    byId("empty-state").innerHTML = `
      <div class="empty-icon">!</div>
      <h2>Could not load dashboard data</h2>
      <p>Start the dashboard with automation/start_review_dashboard.py and refresh the page.</p>
    `;
    renderOperationalStatus();
    console.error(error);
  }
}

bindEditorEvents();
load();

const UPDATE_CHECKS = [
  "I opened the official source.",
  "I verified the facts against the official source.",
  "I verified the status and effective date.",
  "I verified the intended audience.",
  "I reviewed the title, summary, Why It Matters, and details.",
  "I approve this update to the published article.",
];

async function editPublishedArticle() {
  if (state.selectedKind !== "published" || state.updateLoading || state.updating) return;
  if (!window.reserveIntelAuth?.isAuthenticated()) {
    showToast("Sign in with GitHub, then select Edit Article again.", "warning");
    return;
  }
  state.updateLoading = true;
  const button = byId("edit-published-button");
  button.disabled = true;
  button.textContent = "Loading current article…";
  try {
    const response = await window.reserveIntelAuth.authenticatedFetch(`/api/published-article?id=${encodeURIComponent(state.selectedId)}`, {cache:"no-store"});
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "Could not load this article.");
    const item = findItem(state.selectedId, "published");
    Object.assign(item, data.article);
    state.publishedEdit = {article:structuredClone(data.article), baseSha:data.baseSha, patch:null};
    renderArticle(item, "published");
  } catch (error) {
    byId("published-update-note").textContent = error.message || "Could not load the article. Try again.";
  } finally {
    state.updateLoading = false;
    button.disabled = false;
    button.textContent = "Edit Article";
  }
}

function cancelPublishedEdit() {
  if (state.updating) return;
  if (state.dirty && !window.confirm("Discard your unpublished edits?")) return;
  state.publishedEdit = null;
  setDirty(false);
  renderArticle(findItem(state.selectedId, "published"), "published");
}

function reviewPublishedUpdate() {
  if (!state.publishedEdit || state.updating) return;
  const patch = editorSnapshot();
  try { validateEditorSnapshot(patch); }
  catch (error) { showToast(error.message, "warning"); return; }
  const original = state.publishedEdit.article;
  const fields = Object.keys(patch).filter(key => JSON.stringify(patch[key]) !== JSON.stringify(original[key]));
  if (!fields.length) { showToast("No changes to publish."); return; }
  state.publishedEdit.patch = structuredClone(patch);
  const diff = byId("update-diff");
  diff.replaceChildren();
  const labels = {title:"Title", summary:"Summary", whyItMatters:"Why It Matters", details:"Details", category:"Category", status:"Status", priority:"Priority", effectiveDate:"Effective Date", audience:"Audience", isPinned:"Pinned"};
  const display = value => value === null ? "Not specified" : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
  for (const key of fields) {
    const section = document.createElement("section");
    section.className = "update-diff-field";
    const title = document.createElement("h3");
    title.textContent = labels[key];
    section.appendChild(title);
    for (const [label, value] of [["Currently published", original[key]], ["Your update", patch[key]]]) {
      const heading = document.createElement("strong");
      heading.textContent = label;
      const text = document.createElement("pre");
      text.textContent = display(value);
      section.append(heading, text);
    }
    diff.appendChild(section);
  }
  const checks = byId("update-confirmations");
  checks.replaceChildren();
  for (const text of UPDATE_CHECKS) {
    const label = document.createElement("label");
    label.className = "approval-check";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.addEventListener("change", () => {
      byId("publish-update-button").disabled = state.updating || !Array.from(checks.querySelectorAll("input")).every(c => c.checked);
    });
    const span = document.createElement("span");
    span.textContent = text;
    label.append(checkbox, span);
    checks.appendChild(label);
  }
  byId("update-error").textContent = "";
  byId("publish-update-button").disabled = true;
  byId("update-dialog").showModal();
}

async function publishArticleUpdate() {
  const edit = state.publishedEdit;
  if (!edit?.patch || state.updating) return;
  const checks = Array.from(byId("update-confirmations").querySelectorAll("input"));
  if (checks.length !== 6 || !checks.every(c => c.checked)) return;
  state.updating = true;
  const button = byId("publish-update-button");
  button.disabled = true;
  button.textContent = "Updating…";
  byId("back-to-update-button").disabled = true;
  byId("update-error").textContent = "";
  try {
    const response = await window.reserveIntelAuth.authenticatedFetch("/api/published-article", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({articleId:edit.article.id, baseSha:edit.baseSha, patch:edit.patch, confirmations:UPDATE_CHECKS}),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) throw new Error(payload.error || "Update could not be confirmed. Reopen the article to check its current version.");
    const item = findItem(edit.article.id, "published");
    Object.assign(item, payload.article);
    state.publishedEdit = null;
    setDirty(false);
    byId("update-dialog").close();
    renderQueues();
    renderArticle(item, "published");
    byId("published-update-note").textContent = "Update saved. The app will receive it when it next refreshes its feed; the dashboard snapshot may take a moment to rebuild.";
    showToast("Published article updated successfully.", "success");
  } catch (error) {
    byId("update-error").textContent = error.message || "Update could not be confirmed. Reopen the article before retrying.";
  } finally {
    state.updating = false;
    button.disabled = false;
    button.textContent = "Approve & Update";
    byId("back-to-update-button").disabled = false;
  }
}
