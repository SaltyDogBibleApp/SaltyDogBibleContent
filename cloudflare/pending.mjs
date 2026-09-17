const REPOSITORY = "SaltyDogBibleApp/SaltyDogBibleContent";
const REPOSITORY_NAME = "SaltyDogBibleContent";
const API = "https://api.github.com";
const REVIEW_PREFIX = "reserve-intel-review/";

const APPROVAL_CHECKS = [
  "I opened the official source.",
  "I verified the facts against the official source.",
  "I verified the status and effective date.",
  "I verified the intended audience.",
  "I reviewed the title, summary, Why It Matters, and details.",
  "I approve publication to Reserve Intel.",
];

class PendingError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.status = status;
  }
}

function exactKeys(value, keys, label) {
  if (
    !value ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.keys(value).length !== keys.length ||
    keys.some((key) => !Object.hasOwn(value, key))
  ) {
    throw new PendingError(`${label} contains missing or unexpected fields.`);
  }
}

function validId(value) {
  return typeof value === "string" && /^[a-zA-Z0-9_-]{1,200}$/.test(value);
}

function encode(text) {
  let binary = "";
  for (const byte of new TextEncoder().encode(text)) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function decode(text) {
  return new TextDecoder().decode(
    Uint8Array.from(atob(text.replace(/\s/g, "")), (char) => char.charCodeAt(0))
  );
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function mdCell(value) {
  if (value === null || value === undefined || value === "") return "All";
  return String(value).replace(/\|/g, "\\|").replace(/\s+/g, " ").trim();
}

async function github(path, token, method = "GET", body) {
  let response;
  try {
    response = await fetch(`${API}${path}`, {
      method,
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "Salty-Dog-Reserve-Intel",
        "Content-Type": "application/json",
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (error) {
    console.error("Pending review GitHub fetch failed", {
      path,
      method,
      name: error?.name || "Error",
      message: error?.message || String(error),
    });
    throw new PendingError(
      `GitHub request failed before receiving a response (${method} ${path}).`,
      502
    );
  }

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      if (response.ok) throw new PendingError("GitHub returned an invalid response.", 502);
    }
  }

  if (!response.ok) {
    const detail =
      typeof payload?.message === "string" && payload.message.length <= 300
        ? ` ${payload.message}`
        : "";
    throw new PendingError(
      `GitHub could not complete the request (HTTP ${response.status}).${detail}`,
      response.status === 409 || response.status === 422 ? 409 : 502
    );
  }

  return payload;
}

async function githubGraphql(token, query, variables) {
  let response;
  try {
    response = await fetch(`${API}/graphql`, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "Salty-Dog-Reserve-Intel",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query, variables }),
    });
  } catch (error) {
    throw new PendingError(
      `GitHub request failed before receiving a response (POST /graphql): ${error?.message || "network error"}`,
      502
    );
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload || (Array.isArray(payload.errors) && payload.errors.length)) {
    const detail = Array.isArray(payload?.errors)
      ? payload.errors.map((item) => item?.message).filter(Boolean).join("; ").slice(0, 400)
      : "";
    throw new PendingError(
      detail ? `GitHub could not update the review state. ${detail}` : "GitHub could not update the review state.",
      502
    );
  }
  return payload.data;
}

function validatePatch(value) {
  exactKeys(
    value,
    [
      "title",
      "summary",
      "whyItMatters",
      "details",
      "category",
      "status",
      "priority",
      "effectiveDate",
      "audience",
      "isPinned",
    ],
    "Article draft"
  );

  const result = {};
  for (const [key, maximum] of Object.entries({
    title: 300,
    summary: 4000,
    whyItMatters: 6000,
    details: 20000,
  })) {
    if (
      typeof value[key] !== "string" ||
      !value[key].trim() ||
      value[key].length > maximum
    ) {
      throw new PendingError(`${key} must contain 1–${maximum} characters.`);
    }
    result[key] = value[key].trim();
  }

  const choices = {
    category: [
      "Legislation / NDAA",
      "Policy",
      "Pay & Benefits",
      "Retirement",
      "VA / Veteran Benefits",
      "Training & Readiness",
      "Admin",
      "Other",
    ],
    status: [
      "TRACKING",
      "PROPOSED",
      "INTRODUCED",
      "COMMITTEE",
      "PASSED HOUSE",
      "PASSED SENATE",
      "SIGNED",
      "EFFECTIVE",
      "SUPERSEDED",
    ],
    priority: ["NORMAL", "HIGH"],
  };

  for (const [key, allowed] of Object.entries(choices)) {
    if (!allowed.includes(value[key])) throw new PendingError(`Unsupported ${key}.`);
    result[key] = value[key];
  }

  const effectiveDate = value.effectiveDate;
  if (
    effectiveDate !== null &&
    (typeof effectiveDate !== "string" ||
      !/^\d{4}-\d{2}-\d{2}T00:00:00Z$/.test(effectiveDate) ||
      !Number.isFinite(Date.parse(effectiveDate)) ||
      new Date(effectiveDate).toISOString().replace(".000Z", "Z") !== effectiveDate)
  ) {
    throw new PendingError("Effective date must be a valid calendar date.");
  }
  result.effectiveDate = effectiveDate;

  exactKeys(
    value.audience,
    ["service", "reserveStatus", "trainingWing", "squadron"],
    "Audience"
  );
  if (
    !["ALL", "USN", "USMC"].includes(value.audience.service) ||
    !["ALL", "SELRES", "VTU"].includes(value.audience.reserveStatus)
  ) {
    throw new PendingError("Unsupported audience.");
  }

  result.audience = { ...value.audience };
  for (const key of ["trainingWing", "squadron"]) {
    const target = value.audience[key];
    if (target !== null && (typeof target !== "string" || target.length > 120)) {
      throw new PendingError(`Invalid ${key}.`);
    }
    result.audience[key] = target?.trim() || null;
  }

  if (typeof value.isPinned !== "boolean") {
    throw new PendingError("Pinned must be true or false.");
  }
  result.isPinned = value.isPinned;
  return result;
}

function validateIdentity(body) {
  if (!validId(body.articleId)) throw new PendingError("Invalid article ID.");
  const branch = `${REVIEW_PREFIX}${body.articleId}`;
  const sourceFile = `drafts/pending/${body.articleId}.json`;
  const reviewFile = `reviews/pending/${body.articleId}.md`;
  if (body.reviewBranch !== branch) throw new PendingError("Review branch does not match the article ID.");
  if (body.sourceFile !== sourceFile) throw new PendingError("Pending draft path does not match the article ID.");
  return { branch, sourceFile, reviewFile };
}

async function findReviewPr(token, branch, { allowMissing = false } = {}) {
  const pulls = await github(`/repos/${REPOSITORY}/pulls?state=open&base=main&per_page=100`, token);
  if (!Array.isArray(pulls)) throw new PendingError("GitHub returned an invalid pull-request list.", 502);

  const matches = pulls.filter(
    (pr) =>
      pr?.state === "open" &&
      pr?.base?.ref === "main" &&
      pr?.head?.ref === branch &&
      pr?.head?.repo?.full_name === REPOSITORY
  );

  if (!matches.length && allowMissing) return null;
  if (!matches.length) throw new PendingError("The Review PR is not ready yet. Refresh the queue after GitHub finishes preparing it.", 409);
  if (matches.length !== 1) throw new PendingError("More than one open Review PR matches this article. Resolve the duplicates in GitHub before continuing.", 409);

  const pr = await github(`/repos/${REPOSITORY}/pulls/${matches[0].number}`, token);
  const labels = Array.isArray(pr?.labels)
    ? pr.labels.map((label) => label?.name).filter(Boolean)
    : [];
  if (
    pr?.state !== "open" ||
    pr?.merged_at ||
    pr?.base?.ref !== "main" ||
    pr?.head?.ref !== branch ||
    pr?.head?.repo?.full_name !== REPOSITORY ||
    !labels.includes("reserve-intel-review")
  ) {
    throw new PendingError("The open pull request does not match the Reserve Intel review contract.", 409);
  }
  return pr;
}

async function fetchTextFile(token, path, ref) {
  const file = await github(
    `/repos/${REPOSITORY}/contents/${path}?ref=${encodeURIComponent(ref)}`,
    token
  );
  if (file?.encoding !== "base64" || typeof file.content !== "string" || typeof file.sha !== "string") {
    throw new PendingError(`GitHub could not read ${path}.`, 502);
  }
  return { text: decode(file.content), sha: file.sha };
}

async function fetchJsonFile(token, path, ref) {
  const file = await fetchTextFile(token, path, ref);
  let value;
  try {
    value = JSON.parse(file.text);
  } catch {
    throw new PendingError(`The pending draft ${path} is invalid JSON.`, 409);
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new PendingError("The pending draft has an invalid root.", 409);
  }
  return { value, sha: file.sha };
}

async function writeTextFile(token, path, branch, sha, text, message) {
  const response = await github(`/repos/${REPOSITORY}/contents/${path}`, token, "PUT", {
    branch,
    message,
    content: encode(text),
    sha,
  });
  return response?.commit?.sha || null;
}

function validateDraft(draft, articleId) {
  if (
    draft?.draftStatus !== "PENDING_HUMAN_REVIEW" ||
    draft?.requiresHumanReview !== true ||
    draft?.publishReady !== false
  ) {
    throw new PendingError("The remote draft is no longer pending human review.", 409);
  }
  if (draft?.sourceEvidence?.officialHostVerified !== true) {
    throw new PendingError("The official source host has not been verified.", 409);
  }
  const article = draft.articleDraft;
  if (!article || typeof article !== "object" || article.id !== articleId || article.isActive !== false) {
    throw new PendingError("The remote draft article does not match the selected review item.", 409);
  }
  if (
    typeof article.sourceName !== "string" ||
    !article.sourceName.trim() ||
    typeof article.sourceURL !== "string" ||
    !article.sourceURL.startsWith("https://")
  ) {
    throw new PendingError("The pending draft is missing its immutable official source identity.", 409);
  }
  return article;
}

async function validatedContext(token, body, { allowMissingPr = false } = {}) {
  const identity = validateIdentity(body);
  const pr = await findReviewPr(token, identity.branch, { allowMissing: allowMissingPr });
  if (!pr) return { ...identity, pr: null };

  const files = await github(`/repos/${REPOSITORY}/pulls/${pr.number}/files?per_page=100`, token);
  const names = Array.isArray(files) ? files.map((file) => file?.filename).filter(Boolean) : [];
  if (
    names.length !== 2 ||
    !names.includes(identity.sourceFile) ||
    !names.includes(identity.reviewFile)
  ) {
    throw new PendingError("The Review PR contains unexpected file changes and cannot be managed from the dashboard.", 409);
  }

  const draftFile = await fetchJsonFile(token, identity.sourceFile, identity.branch);
  const article = validateDraft(draftFile.value, body.articleId);
  const reviewFile = await fetchTextFile(token, identity.reviewFile, identity.branch);
  const marker = `<!-- reserve-intel-article-id: ${body.articleId} -->`;
  if (!reviewFile.text.includes(marker)) {
    throw new PendingError("The review file does not contain the expected article marker.", 409);
  }

  return {
    ...identity,
    pr,
    draft: draftFile.value,
    draftSha: draftFile.sha,
    article,
    reviewText: reviewFile.text,
    reviewSha: reviewFile.sha,
  };
}

function renderArticleBlock(article) {
  const audience = article.audience || {};
  const title = String(article.title || article.id).replace(/\s+/g, " ").trim();
  return [
    `## ${title}`,
    "",
    "| Field | Proposed value |",
    "| --- | --- |",
    `| Category | ${mdCell(article.category)} |`,
    `| Status | ${mdCell(article.status)} |`,
    `| Priority | ${mdCell(article.priority)} |`,
    `| Service | ${mdCell(audience.service || "ALL")} |`,
    `| Reserve status | ${mdCell(audience.reserveStatus || "ALL")} |`,
    `| Training Wing | ${mdCell(audience.trainingWing)} |`,
    `| Squadron | ${mdCell(audience.squadron)} |`,
    "",
    "### Summary",
    "",
    article.summary,
    "",
    "### Why It Matters",
    "",
    article.whyItMatters,
    "",
    "### Details",
    "",
    article.details,
    "",
  ].join("\n");
}

function setApprovalChecks(text, checked) {
  let updated = text;
  for (const label of APPROVAL_CHECKS) {
    const pattern = new RegExp(
      `(^\\s*-\\s*)\\[[ xX]\\](\\s*${escapeRegExp(label)}\\s*$)`,
      "mi"
    );
    if (!pattern.test(updated)) {
      throw new PendingError(`The review checklist is missing: ${label}`, 409);
    }
    updated = updated.replace(pattern, `$1[${checked ? "x" : " "}]$2`);
  }
  return updated;
}

function rewriteReview(existing, draft, checked) {
  const article = validateDraft(draft, draft?.articleDraft?.id);
  const marker = `<!-- reserve-intel-article-id: ${article.id} -->`;
  const markerIndex = existing.indexOf(marker);
  if (markerIndex < 0) throw new PendingError("The review marker is missing.", 409);

  const articleStart = existing.indexOf("\n## ");
  const officialSource = existing.lastIndexOf("\n### Official Source", markerIndex);
  if (articleStart < 0 || officialSource < 0 || officialSource <= articleStart) {
    throw new PendingError("The review file structure is not recognized.", 409);
  }

  const prefix = existing.slice(0, articleStart + 1);
  const suffix = existing.slice(officialSource + 1);
  return setApprovalChecks(`${prefix}${renderArticleBlock(article)}${suffix}`, checked);
}

function withRejectionNote(text, articleId, reason) {
  const marker = `<!-- reserve-intel-article-id: ${articleId} -->`;
  const safeReason = reason
    ? reason.split(/\r?\n/).map((line) => `> ${line}`).join("\n")
    : "> No reason provided.";
  const note = `### Rejection Note\n\n${safeReason}\n\n`;
  return text.replace(marker, `${note}${marker}`);
}

async function updateReviewBody(token, prNumber, body) {
  const updated = await github(`/repos/${REPOSITORY}/pulls/${prNumber}`, token, "PATCH", { body });
  if (updated?.number !== prNumber || updated?.body !== body) {
    throw new PendingError("GitHub did not confirm the updated Review PR body.", 502);
  }
}

async function markReady(token, pr) {
  if (pr.draft !== true) return;
  if (typeof pr.node_id !== "string" || !pr.node_id) {
    throw new PendingError("GitHub did not return the Review PR node ID.", 502);
  }
  const data = await githubGraphql(
    token,
    `mutation($pullRequestId: ID!) {\n      markPullRequestReadyForReview(input: {pullRequestId: $pullRequestId}) {\n        pullRequest { isDraft }\n      }\n    }`,
    { pullRequestId: pr.node_id }
  );
  if (data?.markPullRequestReadyForReview?.pullRequest?.isDraft !== false) {
    throw new PendingError("GitHub did not mark the Review PR ready for merge.", 502);
  }
}

function confirmChecks(value) {
  if (
    !Array.isArray(value) ||
    value.length !== APPROVAL_CHECKS.length ||
    value.some((item, index) => item !== APPROVAL_CHECKS[index])
  ) {
    throw new PendingError("Complete all six publication confirmations.");
  }
}

async function pendingStatus(body, token, respond) {
  exactKeys(body, ["action", "articleId", "sourceFile", "reviewBranch"], "Pending review status request");
  const context = await validatedContext(token, body, { allowMissingPr: true });
  if (!context.pr) {
    return respond({ ok: true, action: "pending-status", articleId: body.articleId, ready: false });
  }
  return respond({
    ok: true,
    action: "pending-status",
    articleId: body.articleId,
    ready: true,
    article: context.article,
    prNumber: context.pr.number,
    prUrl: context.pr.html_url,
    draft: context.pr.draft === true,
  });
}

async function savePending(body, token, respond) {
  exactKeys(body, ["action", "articleId", "sourceFile", "reviewBranch", "patch"], "Save Draft request");
  const patch = validatePatch(body.patch);
  const context = await validatedContext(token, body);
  const updatedDraft = JSON.parse(JSON.stringify(context.draft));
  for (const [key, value] of Object.entries(patch)) {
    updatedDraft.articleDraft[key] = value;
  }
  validateDraft(updatedDraft, body.articleId);

  const draftText = `${JSON.stringify(updatedDraft, null, 2)}\n`;
  const oldDraftText = `${JSON.stringify(context.draft, null, 2)}\n`;
  let commitSha = null;
  let draftChanged = draftText !== oldDraftText;
  if (draftChanged) {
    commitSha = await writeTextFile(
      token,
      context.sourceFile,
      context.branch,
      context.draftSha,
      draftText,
      `Update Reserve Intel review: ${body.articleId}`
    );
  }

  const latestReview = await fetchTextFile(token, context.reviewFile, context.branch);
  const reviewText = rewriteReview(latestReview.text, updatedDraft, false);
  const reviewChanged = reviewText !== latestReview.text;
  if (reviewChanged) {
    const reviewCommitSha = await writeTextFile(
      token,
      context.reviewFile,
      context.branch,
      latestReview.sha,
      reviewText,
      `Sync Reserve Intel review: ${body.articleId}`
    );
    if (!commitSha) commitSha = reviewCommitSha;
  }

  if (context.pr.body !== reviewText) {
    await updateReviewBody(token, context.pr.number, reviewText);
  }

  return respond({
    ok: true,
    action: "pending-save",
    articleId: body.articleId,
    article: updatedDraft.articleDraft,
    changed: draftChanged || reviewChanged || context.pr.body !== reviewText,
    commitSha,
    prNumber: context.pr.number,
  });
}

async function rejectPending(body, token, respond) {
  exactKeys(body, ["action", "articleId", "sourceFile", "reviewBranch", "reason"], "Reject request");
  if (typeof body.reason !== "string" || body.reason.length > 2000) {
    throw new PendingError("Rejection reason must be text with 2,000 characters or fewer.");
  }
  const context = await validatedContext(token, body);
  const rejectionText = withRejectionNote(setApprovalChecks(context.reviewText, false), body.articleId, body.reason.trim());
  if (rejectionText !== context.reviewText) {
    await writeTextFile(
      token,
      context.reviewFile,
      context.branch,
      context.reviewSha,
      rejectionText,
      `Reject Reserve Intel review: ${body.articleId}`
    );
  }
  if (context.pr.body !== rejectionText) {
    await updateReviewBody(token, context.pr.number, rejectionText);
  }
  const closed = await github(`/repos/${REPOSITORY}/pulls/${context.pr.number}`, token, "PATCH", { state: "closed" });
  if (closed?.state !== "closed" || closed?.merged_at) {
    throw new PendingError("GitHub did not close the Review PR without merging it.", 502);
  }
  return respond({
    ok: true,
    action: "pending-reject",
    articleId: body.articleId,
    prNumber: context.pr.number,
    prUrl: context.pr.html_url,
  });
}

async function approvePending(body, token, respond) {
  exactKeys(body, ["action", "articleId", "sourceFile", "reviewBranch", "confirmations"], "Approval request");
  confirmChecks(body.confirmations);
  let context = await validatedContext(token, body);
  const approvedReview = rewriteReview(context.reviewText, context.draft, true);
  if (approvedReview !== context.reviewText) {
    await writeTextFile(
      token,
      context.reviewFile,
      context.branch,
      context.reviewSha,
      approvedReview,
      `Approve Reserve Intel review: ${body.articleId}`
    );
  }
  if (context.pr.body !== approvedReview) {
    await updateReviewBody(token, context.pr.number, approvedReview);
  }

  let pr = await github(`/repos/${REPOSITORY}/pulls/${context.pr.number}`, token);
  await markReady(token, pr);
  pr = await github(`/repos/${REPOSITORY}/pulls/${context.pr.number}`, token);
  if (
    pr?.state !== "open" ||
    pr?.draft === true ||
    pr?.base?.ref !== "main" ||
    pr?.head?.ref !== context.branch ||
    typeof pr?.head?.sha !== "string" ||
    !pr.head.sha
  ) {
    throw new PendingError("The Review PR is not in a mergeable review state.", 409);
  }

  const pinnedDraft = await fetchJsonFile(token, context.sourceFile, pr.head.sha);
  validateDraft(pinnedDraft.value, body.articleId);
  const finalBody = typeof pr.body === "string" ? pr.body : "";
  for (const label of APPROVAL_CHECKS) {
    if (!new RegExp(`^\\s*-\\s*\\[[xX]\\]\\s*${escapeRegExp(label)}\\s*$`, "mi").test(finalBody)) {
      throw new PendingError("The Review PR no longer contains all six publication approvals.", 409);
    }
  }

  const merged = await github(`/repos/${REPOSITORY}/pulls/${context.pr.number}/merge`, token, "PUT", {
    sha: pr.head.sha,
    merge_method: "merge",
    commit_title: `Approve Reserve Intel review: ${body.articleId}`,
  });
  if (merged?.merged !== true) {
    throw new PendingError(merged?.message || "GitHub did not merge the Review PR.", 409);
  }

  return respond({
    ok: true,
    action: "pending-approve",
    articleId: body.articleId,
    prNumber: context.pr.number,
    prUrl: context.pr.html_url,
    mergeCommitSha: merged.sha || null,
  });
}

export async function handlePendingAction(body, token, respond) {
  switch (body.action) {
    case "pending-status":
      return pendingStatus(body, token, respond);
    case "pending-save":
      return savePending(body, token, respond);
    case "pending-reject":
      return rejectPending(body, token, respond);
    case "pending-approve":
      return approvePending(body, token, respond);
    default:
      return null;
  }
}
