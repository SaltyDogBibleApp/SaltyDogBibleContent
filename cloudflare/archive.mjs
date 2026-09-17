const REPOSITORY = "SaltyDogBibleApp/SaltyDogBibleContent";
const API = "https://api.github.com";
const FEED_PATH = "reserve-content-feed.json";
const ARCHIVE_PATH = "reserve-content-archive.json";
const ARCHIVE_PREFIX = "reserve-intel-archive/";
const CORRECTION_PREFIX = "reserve-intel-review/correction-";

const REASONS = new Set([
  "SUPERSEDED",
  "REPLACED",
  "EXPIRED",
  "BOARD_CYCLE_COMPLETE",
  "DEADLINE_PASSED",
  "NO_LONGER_CURRENT",
  "OTHER",
]);

class ArchiveError extends Error {
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
    throw new ArchiveError(`${label} contains missing or unexpected fields.`);
  }
}

function validId(value) {
  return typeof value === "string" && /^[a-zA-Z0-9_-]{1,200}$/.test(value);
}

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function encode(text) {
  let binary = "";
  for (const byte of new TextEncoder().encode(text)) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function decode(text) {
  return new TextDecoder().decode(
    Uint8Array.from(atob(text.replace(/\s/g, "")), (char) => char.charCodeAt(0))
  );
}

function normalizeNote(value) {
  if (value === null) return null;
  if (typeof value !== "string") throw new ArchiveError("Archive note must be text or null.");
  const note = value.trim();
  if (note.length > 1000) throw new ArchiveError("Archive note must be 1000 characters or fewer.");
  return note || null;
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
    throw new ArchiveError(
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
      if (response.ok) throw new ArchiveError("GitHub returned an invalid response.", 502);
    }
  }

  if (!response.ok) {
    const detail =
      typeof payload?.message === "string" && payload.message.length <= 300
        ? ` ${payload.message}`
        : "";
    throw new ArchiveError(
      `GitHub could not complete the request (HTTP ${response.status}).${detail}`,
      response.status === 409 || response.status === 422 ? 409 : 502
    );
  }
  return payload;
}

async function readJsonFile(token, path, ref) {
  const file = await github(
    `/repos/${REPOSITORY}/contents/${path}?ref=${encodeURIComponent(ref)}`,
    token
  );
  if (file?.encoding !== "base64" || typeof file.content !== "string" || typeof file.sha !== "string") {
    throw new ArchiveError(`GitHub could not read ${path}.`, 502);
  }
  let value;
  try {
    value = JSON.parse(decode(file.content));
  } catch {
    throw new ArchiveError(`${path} is not valid JSON.`, 502);
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new ArchiveError(`${path} has an invalid root.`, 502);
  }
  return { value, sha: file.sha };
}

async function writeJsonFile(token, path, branch, sha, value, message) {
  await github(`/repos/${REPOSITORY}/contents/${path}`, token, "PUT", {
    branch,
    message,
    content: encode(JSON.stringify(value, null, 2) + "\n"),
    sha,
  });
}

function currentArticle(feed, articleId) {
  if (!Array.isArray(feed?.intelArticles)) throw new ArchiveError("The live feed is invalid.", 502);
  const matches = feed.intelArticles.filter((article) => article?.id === articleId);
  if (matches.length !== 1 || matches[0].isActive !== true) {
    throw new ArchiveError("This article is missing, inactive, or has a duplicate ID.", 409);
  }
  return matches[0];
}

function archiveArticles(archive) {
  if (!Array.isArray(archive?.archivedArticles)) {
    throw new ArchiveError("The archive feed is invalid.", 502);
  }
  return archive.archivedArticles;
}

function branchName(articleId, now) {
  const stamp = now.replace(/\D/g, "").slice(0, 14);
  const rand = crypto.getRandomValues(new Uint32Array(1))[0]
    .toString(36)
    .padStart(6, "0")
    .slice(-6);
  return `${ARCHIVE_PREFIX}${articleId.replace(/[^a-zA-Z0-9_-]/g, "-").slice(0, 120)}-${stamp}-${rand}`;
}

function marker(articleId) {
  return `- Live article ID: \`${articleId}\``;
}

function summary(pr) {
  return {
    prNumber: pr.number,
    prUrl: pr.html_url,
    title: pr.title,
    branch: pr.head?.ref || null,
  };
}

function renderReview(article, reason, note, successorArticleId, session, archivedAt) {
  const lines = [
    "# Reserve Intel Archive Review",
    "",
    "> **Lifecycle change only.** This moves one article out of the Current feed and into the permanent Reserve Intel archive. The article is not deleted.",
    "",
    marker(article.id),
    `- Title: ${article.title}`,
    `- Official source: ${article.sourceURL}`,
    `- Archive reason: \`${reason}\``,
    `- Archived by: \`${session.sub}\``,
    `- Proposed archive time: ${archivedAt}`,
    `- Successor article ID: ${successorArticleId ? `\`${successorArticleId}\`` : "None"}`,
    `- Note: ${note || "None"}`,
    "",
    "## Archive Confirmation",
    "",
    "- [x] I confirmed this article should no longer appear in Current Reserve Intel.",
    "- [x] I confirmed the complete article will remain retrievable in the Reserve Intel archive.",
    "",
  ];
  return lines.join("\n");
}

async function openArchiveReview(token, articleId) {
  const pulls = await github(`/repos/${REPOSITORY}/pulls?state=open&base=main&per_page=100`, token);
  if (!Array.isArray(pulls)) throw new ArchiveError("GitHub returned an invalid pull-request list.", 502);
  const prefix = `${ARCHIVE_PREFIX}${articleId}-`;
  const expectedMarker = marker(articleId);
  const matches = pulls.filter(
    (pr) =>
      pr?.state === "open" &&
      pr?.base?.ref === "main" &&
      pr?.head?.repo?.full_name === REPOSITORY &&
      typeof pr?.head?.ref === "string" &&
      pr.head.ref.startsWith(prefix) &&
      typeof pr?.body === "string" &&
      pr.body.includes(expectedMarker)
  );
  if (matches.length > 1) {
    throw new ArchiveError("More than one open archive PR exists for this article.", 409);
  }
  return matches[0] || null;
}

async function openCorrectionReview(token, articleId) {
  const pulls = await github(`/repos/${REPOSITORY}/pulls?state=open&base=main&per_page=100`, token);
  if (!Array.isArray(pulls)) throw new ArchiveError("GitHub returned an invalid pull-request list.", 502);
  const prefix = `${CORRECTION_PREFIX}${articleId}-`;
  return pulls.find(
    (pr) =>
      pr?.state === "open" &&
      pr?.base?.ref === "main" &&
      pr?.head?.repo?.full_name === REPOSITORY &&
      typeof pr?.head?.ref === "string" &&
      pr.head.ref.startsWith(prefix)
  ) || null;
}

async function requireNoOpenCorrection(token, articleId) {
  const correction = await openCorrectionReview(token, articleId);
  if (correction) {
    throw new ArchiveError(
      `Correction PR #${correction.number} is still open for this article. Approve or reject that correction before archiving it.`,
      409
    );
  }
}

async function createArchive(body, token, session, respond) {
  exactKeys(
    body,
    ["action", "articleId", "baseUpdatedAt", "reason", "note", "successorArticleId"],
    "Archive request"
  );
  if (!validId(body.articleId)) throw new ArchiveError("Invalid article ID.");
  if (!REASONS.has(body.reason)) throw new ArchiveError("Unsupported archive reason.");
  if (body.successorArticleId !== null && !validId(body.successorArticleId)) {
    throw new ArchiveError("Successor article ID must be a valid article ID or null.");
  }
  if (body.successorArticleId === body.articleId) {
    throw new ArchiveError("An article cannot supersede itself.");
  }
  const note = normalizeNote(body.note);

  const existingReview = await openArchiveReview(token, body.articleId);
  if (existingReview) {
    throw new ArchiveError("An archive review is already open for this article.", 409);
  }
  await requireNoOpenCorrection(token, body.articleId);

  const feedFile = await readJsonFile(token, FEED_PATH, "main");
  const archiveFile = await readJsonFile(token, ARCHIVE_PATH, "main");
  const article = currentArticle(feedFile.value, body.articleId);

  if ((article.updatedAt || null) !== body.baseUpdatedAt) {
    throw new ArchiveError(
      "This article changed after the dashboard loaded. Refresh before archiving it.",
      409
    );
  }

  if (archiveArticles(archiveFile.value).some((item) => item?.id === body.articleId)) {
    throw new ArchiveError("This article ID already exists in the archive.", 409);
  }

  if (body.successorArticleId !== null) {
    currentArticle(feedFile.value, body.successorArticleId);
  }

  const archivedAt = nowIso();
  const archivedArticle = {
    ...article,
    isActive: false,
    archivedAt,
    archiveReason: body.reason,
    archiveNote: note,
    supersededByArticleID: body.successorArticleId,
  };

  const nextFeed = {
    ...feedFile.value,
    generatedAt: archivedAt,
    intelArticles: feedFile.value.intelArticles.filter((item) => item?.id !== body.articleId),
  };
  const nextArchive = {
    ...archiveFile.value,
    schemaVersion: 1,
    generatedAt: archivedAt,
    archivedArticles: [archivedArticle, ...archiveArticles(archiveFile.value)],
  };

  const mainRef = await github(`/repos/${REPOSITORY}/git/ref/heads/main`, token);
  const mainSha = mainRef?.object?.sha;
  if (typeof mainSha !== "string" || !/^[a-f0-9]{40}$/.test(mainSha)) {
    throw new ArchiveError("GitHub main branch could not be resolved.", 502);
  }

  const branch = branchName(body.articleId, archivedAt);
  await github(`/repos/${REPOSITORY}/git/refs`, token, "POST", {
    ref: `refs/heads/${branch}`,
    sha: mainSha,
  });

  await writeJsonFile(
    token,
    FEED_PATH,
    branch,
    feedFile.sha,
    nextFeed,
    `Remove ${body.articleId} from current Reserve Intel`
  );
  await writeJsonFile(
    token,
    ARCHIVE_PATH,
    branch,
    archiveFile.sha,
    nextArchive,
    `Archive Reserve Intel article ${body.articleId}`
  );

  const review = renderReview(
    article,
    body.reason,
    note,
    body.successorArticleId,
    session,
    archivedAt
  );
  const pr = await github(`/repos/${REPOSITORY}/pulls`, token, "POST", {
    title: `Reserve Intel Archive: ${article.title}`.slice(0, 250),
    head: branch,
    base: "main",
    body: review,
    draft: false,
    maintainer_can_modify: false,
  });
  if (!Number.isSafeInteger(pr?.number) || typeof pr?.html_url !== "string") {
    throw new ArchiveError("GitHub created the archive branch but did not return a valid review PR.", 502);
  }
  return respond({
    ok: true,
    action: "archive-created",
    articleId: body.articleId,
    prNumber: pr.number,
    prUrl: pr.html_url,
    branch,
  });
}

async function validatedArchiveReview(token, articleId, prNumber) {
  if (!validId(articleId) || !Number.isSafeInteger(prNumber) || prNumber < 1) {
    throw new ArchiveError("Invalid archive review request.");
  }
  const pr = await github(`/repos/${REPOSITORY}/pulls/${prNumber}`, token);
  const prefix = `${ARCHIVE_PREFIX}${articleId}-`;
  if (
    pr?.number !== prNumber ||
    pr?.state !== "open" ||
    pr?.merged_at ||
    pr?.base?.ref !== "main" ||
    pr?.head?.repo?.full_name !== REPOSITORY ||
    typeof pr?.head?.ref !== "string" ||
    !pr.head.ref.startsWith(prefix) ||
    typeof pr?.body !== "string" ||
    !pr.body.includes(marker(articleId)) ||
    !pr.body.includes("- [x] I confirmed this article should no longer appear in Current Reserve Intel.") ||
    !pr.body.includes("- [x] I confirmed the complete article will remain retrievable in the Reserve Intel archive.")
  ) {
    throw new ArchiveError("This archive PR does not match the selected article.", 409);
  }

  await requireNoOpenCorrection(token, articleId);

  const files = await github(`/repos/${REPOSITORY}/pulls/${prNumber}/files?per_page=100`, token);
  const names = Array.isArray(files) ? files.map((file) => file?.filename).filter(Boolean) : [];
  if (
    names.length !== 2 ||
    !names.includes(FEED_PATH) ||
    !names.includes(ARCHIVE_PATH)
  ) {
    throw new ArchiveError("The archive PR contains unexpected file changes.", 409);
  }

  const mainFeed = await readJsonFile(token, FEED_PATH, "main");
  const mainArchive = await readJsonFile(token, ARCHIVE_PATH, "main");
  const branchFeed = await readJsonFile(token, FEED_PATH, pr.head.ref);
  const branchArchive = await readJsonFile(token, ARCHIVE_PATH, pr.head.ref);
  const article = currentArticle(mainFeed.value, articleId);

  if (branchFeed.value.intelArticles?.some((item) => item?.id === articleId)) {
    throw new ArchiveError("The archive branch still contains the article in Current.", 409);
  }
  const archivedMatches = archiveArticles(branchArchive.value).filter((item) => item?.id === articleId);
  if (archivedMatches.length !== 1 || archivedMatches[0].isActive !== false) {
    throw new ArchiveError("The archive branch does not contain exactly one inactive archived article.", 409);
  }
  if (
    archivedMatches[0].sourceURL !== article.sourceURL ||
    archivedMatches[0].publishedAt !== article.publishedAt ||
    archivedMatches[0].updatedAt !== article.updatedAt
  ) {
    throw new ArchiveError("The archived article no longer matches the current live article.", 409);
  }
  if (archiveArticles(mainArchive.value).some((item) => item?.id === articleId)) {
    throw new ArchiveError("This article was already archived after the review was created.", 409);
  }

  const expectedRemaining = mainFeed.value.intelArticles.filter((item) => item?.id !== articleId);
  if (JSON.stringify(branchFeed.value.intelArticles) !== JSON.stringify(expectedRemaining)) {
    throw new ArchiveError("The archive PR changes other Current articles and cannot be approved.", 409);
  }

  const expectedArchiveTail = archiveArticles(mainArchive.value);
  if (
    JSON.stringify(archiveArticles(branchArchive.value).slice(1)) !==
    JSON.stringify(expectedArchiveTail)
  ) {
    throw new ArchiveError("The archive PR changes unrelated archived articles and cannot be approved.", 409);
  }

  return { pr, article, archivedArticle: archivedMatches[0] };
}

export async function handleArchiveAction(body, token, session, respond) {
  if (body.action === "archive-status") {
    exactKeys(body, ["action", "articleId"], "Archive status request");
    if (!validId(body.articleId)) throw new ArchiveError("Invalid article ID.");
    const pr = await openArchiveReview(token, body.articleId);
    return respond({
      ok: true,
      articleId: body.articleId,
      archiveReview: pr ? summary(pr) : null,
    });
  }

  if (body.action === "create-archive") {
    return createArchive(body, token, session, respond);
  }

  if (body.action !== "approve-archive" && body.action !== "reject-archive") {
    return null;
  }

  exactKeys(body, ["action", "articleId", "prNumber"], "Archive review action");
  const { pr } = await validatedArchiveReview(token, body.articleId, body.prNumber);

  if (body.action === "approve-archive") {
    const merged = await github(`/repos/${REPOSITORY}/pulls/${body.prNumber}/merge`, token, "PUT", {
      merge_method: "merge",
      commit_title: `Archive Reserve Intel article ${body.articleId}`,
    });
    if (merged?.merged !== true) {
      throw new ArchiveError(merged?.message || "GitHub did not merge the archive PR.", 409);
    }
    return respond({
      ok: true,
      action: "archived",
      articleId: body.articleId,
      prNumber: body.prNumber,
      message: merged.message || "Archive PR merged.",
    });
  }

  const closed = await github(`/repos/${REPOSITORY}/pulls/${body.prNumber}`, token, "PATCH", {
    state: "closed",
  });
  if (closed?.state !== "closed") throw new ArchiveError("GitHub did not close the archive PR.", 502);
  return respond({
    ok: true,
    action: "archive-rejected",
    articleId: body.articleId,
    prNumber: body.prNumber,
  });
}

export { ArchiveError };
