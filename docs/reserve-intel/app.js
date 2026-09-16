const state = {
  data: null,
  selectedId: null,
  selectedKind: null,
};

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

  const parts = [
    item.priority,
    item.status,
    item.sourceName,
  ].filter(Boolean);

  parts.forEach((part) => {
    const span = document.createElement("span");
    span.textContent = part;
    meta.appendChild(span);
  });

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
    pending.forEach(item => pendingList.appendChild(createQueueCard(item, "pending")));
  }

  if (!published.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.style.padding = "8px";
    empty.textContent = "No published history available.";
    publishedList.appendChild(empty);
  } else {
    published.slice(0, 12).forEach(item => publishedList.appendChild(createQueueCard(item, "published")));
  }
}

function findItem(id, kind) {
  const collection = kind === "pending" ? state.data.pending : state.data.published;
  return collection.find(item => item.id === id);
}

function selectItem(id, kind) {
  const item = findItem(id, kind);
  if (!item) return;

  state.selectedId = id;
  state.selectedKind = kind;

  document.querySelectorAll(".queue-card").forEach(card => {
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
    ["Wording reviewed", checklist.summaryRewrittenFromSource &&
      checklist.whyItMattersRewrittenFromSource &&
      checklist.detailsRewrittenFromSource],
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
  hunks.forEach(hunk => {
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

    removed.forEach(line => {
      const el = document.createElement("div");
      el.className = "diff-line removed";
      el.textContent = `- ${line}`;
      box.appendChild(el);
    });

    added.forEach(line => {
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

function renderArticle(item, kind) {
  byId("empty-state").classList.add("hidden");
  byId("article-view").classList.remove("hidden");

  byId("article-kicker").textContent =
    kind === "pending" ? "PENDING HUMAN REVIEW" : "PUBLISHED";

  byId("article-title").textContent = item.title || item.id;
  byId("article-summary").textContent = safe(item.summary, "No summary provided.");
  byId("article-why").textContent = safe(item.whyItMatters, "No Why It Matters text provided.");
  byId("article-details").textContent = safe(item.details, "No details provided.");

  const sourceButton = byId("source-button");
  sourceButton.href = item.sourceURL || "#";
  sourceButton.classList.toggle("hidden", !item.sourceURL);

  const badges = byId("badges");
  badges.innerHTML = "";
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

async function load() {
  try {
    const response = await fetch(`data.json?ts=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    state.data = await response.json();

    byId("generated-at").textContent =
      `Dashboard generated ${formatDateTime(state.data.generatedAt)}`;

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

load();
