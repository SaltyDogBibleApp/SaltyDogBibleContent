
const state = {
  data: null,
  selectedId: null,
  selectedKind: null,
  dirty: false,
  saveServiceAvailable: false,
  saveServiceRepository: null,
  saving: false,
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
    published.slice(0, 8).forEach((item) => publishedList.appendChild(createQueueCard(item, "published")));
  }
}

function findItem(id, kind) {
  const collection = kind === "pending" ? state.data.pending : state.data.published;
  return collection.find((item) => item.id === id);
}

function selectItem(id, kind) {
  if (state.dirty && (id !== state.selectedId || kind !== state.selectedKind)) {
    const leave = window.confirm("You have unsaved browser-only edits. Discard them and open another article?");
    if (!leave) return;
  }

  const item = findItem(id, kind);
  if (!item) return;

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
    showToast("This review branch is not ready for safe saving yet. Regenerate the dashboard after the Review PR is created.", "warning");
    return;
  }

  if (!state.saveServiceAvailable) {
    showToast("Save service is unavailable. Start review_dashboard_server.py instead of python -m http.server.", "warning");
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
    state.saveServiceRepository = payload.repository || null;
    status.textContent = "Save service connected";
    status.className = "service-status connected";
  } catch {
    state.saveServiceAvailable = false;
    state.saveServiceRepository = null;
    status.textContent = "Save service unavailable";
    status.className = "service-status unavailable";
  }
}

function configureActions(item) {
  const saveButton = byId("save-draft-button");
  const modePill = byId("action-mode-pill");
  const actionNote = byId("action-note");

  if (!item || state.selectedKind !== "pending") return;

  if (item._demo === true) {
    saveButton.disabled = state.saving;
    saveButton.textContent = state.saving ? "Saving…" : "Save Draft";
    modePill.textContent = "DEMO";
    modePill.className = "preview-only-pill";
    actionNote.textContent = "Demo Save stays in this browser. Reject and Approve are preview-only.";
    return;
  }

  const ready = item._saveEligible === true;
  const connected = state.saveServiceAvailable === true;

  saveButton.disabled = state.saving || !ready || !connected;
  saveButton.textContent = state.saving ? "Saving…" : "Save Draft";

  if (ready && connected) {
    modePill.textContent = "SAVE LIVE";
    modePill.className = "preview-only-pill live-save";
    actionNote.textContent = `Save Draft commits only the allowed editorial fields to ${item._reviewBranch}. Reject and Approve remain preview-only.`;
  } else if (!ready) {
    modePill.textContent = "WAITING";
    modePill.className = "preview-only-pill waiting";
    actionNote.textContent = "The enriched review branch is not available yet. Regenerate the dashboard after the Review PR is created.";
  } else {
    modePill.textContent = "SAVE OFFLINE";
    modePill.className = "preview-only-pill waiting";
    actionNote.textContent = "Start automation/review_dashboard_server.py to enable real Save Draft. Reject and Approve remain preview-only.";
  }
}

function previewReject() {
  if (state.selectedKind !== "pending") return;
  showToast("Reject preview only. Nothing was archived or changed in GitHub.", "warning");
}

function previewApprove() {
  if (state.selectedKind !== "pending") return;
  showToast("Approval preview only. Nothing was published or changed in GitHub.", "success");
}

function renderArticle(item, kind) {
  const editable = kind === "pending";

  byId("empty-state").classList.add("hidden");
  byId("article-view").classList.remove("hidden");
  byId("article-kicker").textContent = editable ? "PENDING HUMAN REVIEW" : "PUBLISHED";

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
  byId("editor-actions").classList.toggle("hidden", !editable);

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

  byId("save-draft-button").addEventListener("click", saveDraft);
  byId("reject-button").addEventListener("click", previewReject);
  byId("approve-button").addEventListener("click", previewApprove);
}

async function load() {
  try {
    await checkSaveService();

    const response = await fetch(`data.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    state.data = await response.json();

    byId("generated-at").textContent =
      `Dashboard generated ${formatDateTime(state.data.generatedAt)}`;

    byId("preview-banner").classList.toggle("hidden", state.data.demoMode !== true);

    renderQueues();

    if ((state.data.pending || []).length) {
      selectItem(state.data.pending[0].id, "pending");
    } else if ((state.data.published || []).length) {
      selectItem(state.data.published[0].id, "published");
    }
  } catch (error) {
    byId("generated-at").textContent = "Dashboard data unavailable";
    byId("empty-state").innerHTML = `
      <div class="empty-icon">!</div>
      <h2>Could not load dashboard data</h2>
      <p>Run the dashboard generator and confirm docs/reserve-intel/data.json exists.</p>
    `;
    console.error(error);
  }
}

bindEditorEvents();
load();
