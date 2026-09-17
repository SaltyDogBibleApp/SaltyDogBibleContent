// Published-article corrections are edited in the hosted dashboard, but GitHub
// remains the source of truth. This authenticated endpoint can only create a
// correction branch, pending draft, review marker, and draft pull request. It
// never writes reserve-content-feed.json directly.
const REPOSITORY = "SaltyDogBibleApp/SaltyDogBibleContent";
const REPOSITORY_NAME = "SaltyDogBibleContent";
const FEED_PATH = "reserve-content-feed.json";
const API = "https://api.github.com";

// These are the confirmations currently rendered by the dashboard update UI.
export const CHECKS = [
  "I opened the official source.",
  "I verified the facts against the official source.",
  "I verified the status and effective date.",
  "I verified the intended audience.",
  "I reviewed the title, summary, Why It Matters, and details.",
  "I approve this update to the published article.",
];

// The existing publication workflow requires these exact PR-body labels.
const PUBLISH_CHECKS = [
  "I opened the official source.",
  "I verified the facts against the official source.",
  "I verified the status and effective date.",
  "I verified the intended audience.",
  "I reviewed the title, summary, Why It Matters, and details.",
  "I approve publication to Reserve Intel.",
];

class UpdateError extends Error {
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
    throw new UpdateError(`${label} contains missing or unexpected fields.`);
  }
}

export function validatePatch(value) {
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
    "Article update"
  );

  const result = {};
  for (const [key, max] of Object.entries({
    title: 300,
    summary: 4000,
    whyItMatters: 6000,
    details: 20000,
  })) {
    if (
      typeof value[key] !== "string" ||
      !value[key].trim() ||
      value[key].length > max
    ) {
      throw new UpdateError(`${key} must contain 1–${max} characters.`);
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
    if (!allowed.includes(value[key])) {
      throw new UpdateError(`Unsupported ${key}.`);
    }
    result[key] = value[key];
  }

  const date = value.effectiveDate;
  if (
    date !== null &&
    (
      typeof date !== "string" ||
      !/^\d{4}-\d{2}-\d{2}T00:00:00Z$/.test(date) ||
      !Number.isFinite(Date.parse(date)) ||
      new Date(date).toISOString().replace(".000Z", "Z") !== date
    )
  ) {
    throw new UpdateError("Effective date must be a valid calendar date.");
  }
  result.effectiveDate = date;

  exactKeys(
    value.audience,
    ["service", "reserveStatus", "trainingWing", "squadron"],
    "Audience"
  );

  if (
    !["ALL", "USN", "USMC"].includes(value.audience.service) ||
    !["ALL", "SELRES", "VTU"].includes(value.audience.reserveStatus)
  ) {
    throw new UpdateError("Unsupported audience.");
  }

  result.audience = { ...value.audience };
  for (const key of ["trainingWing", "squadron"]) {
    const text = value.audience[key];
    if (
      text !== null &&
      (typeof text !== "string" || text.length > 120)
    ) {
      throw new UpdateError(`Invalid ${key}.`);
    }
    result.audience[key] = text?.trim() || null;
  }

  if (typeof value.isPinned !== "boolean") {
    throw new UpdateError("Pinned must be true or false.");
  }
  result.isPinned = value.isPinned;

  return result;
}

async function readJsonRequest(request, limit) {
  let text;
  try {
    text = await request.text();
  } catch {
    throw new UpdateError("Could not read the request body.");
  }

  if (!text) throw new UpdateError("Empty request body.");
  if (new TextEncoder().encode(text).byteLength > limit) {
    throw new UpdateError("Payload is too large.", 413);
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new UpdateError("Invalid JSON request.");
  }
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
    console.error("GitHub fetch failed", {
      path,
      method,
      name: error?.name || "Error",
      message: error?.message || String(error),
    });
    throw new UpdateError(`GitHub request failed before receiving a response (${method} ${path}).`, 502);
  }

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      if (response.ok) {
        throw new UpdateError("GitHub returned an invalid response.", 502);
      }
    }
  }

  if (!response.ok) {
    if (
      path.includes("/access_tokens") &&
      (response.status === 403 || response.status === 422)
    ) {
      throw new UpdateError(
        "The GitHub App needs Contents and Pull requests permissions set to Read and write before it can create correction review PRs.",
        502
      );
    }

    if (response.status === 409) {
      throw new UpdateError(
        "GitHub reported a conflict while creating the correction. Refresh the dashboard and try again.",
        409
      );
    }

    const detail =
      typeof payload?.message === "string" && payload.message.length <= 300
        ? ` ${payload.message}`
        : "";
    throw new UpdateError(
      `GitHub could not complete the request (HTTP ${response.status}).${detail}`,
      502
    );
  }

  return payload;
}

async function installationToken(env, deps) {
  const jwt = await deps.createGitHubAppJwt(env);
  const installation = await github(
    `/repos/${REPOSITORY}/installation`,
    jwt
  );

  if (!Number.isSafeInteger(installation?.id)) {
    throw new UpdateError("GitHub App installation was not found.", 502);
  }

  const data = await github(
    `/app/installations/${installation.id}/access_tokens`,
    jwt,
    "POST",
    {
      repositories: [REPOSITORY_NAME],
      permissions: {
        contents: "write",
        pull_requests: "write",
      },
    }
  );

  if (typeof data?.token !== "string" || !data.token) {
    throw new UpdateError("GitHub App token was not available.", 502);
  }

  return data.token;
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
    Uint8Array.from(
      atob(text.replace(/\s/g, "")),
      (character) => character.charCodeAt(0)
    )
  );
}

function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function makeCorrectionId(articleId, now) {
  const stamp = now.replace(/\D/g, "").slice(0, 14);
  const random = crypto.getRandomValues(new Uint32Array(1))[0]
    .toString(36)
    .padStart(6, "0")
    .slice(-6);
  const safeArticleId = articleId.replace(/[^a-zA-Z0-9_-]/g, "-").slice(0, 120);
  return `correction-${safeArticleId}-${stamp}-${random}`;
}

function sameValue(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function reviewChecklist() {
  return {
    sourceOpenedAndRead: true,
    factsVerifiedAgainstSource: true,
    statusVerified: true,
    effectiveDateVerified: true,
    audienceVerified: true,
    summaryRewrittenFromSource: true,
    whyItMattersRewrittenFromSource: true,
    detailsRewrittenFromSource: true,
    approvedForPublication: true,
  };
}

function makeCorrectionDraft(current, patch, correctionId, session, now) {
  if (
    typeof current.sourceName !== "string" ||
    !current.sourceName.trim() ||
    typeof current.sourceURL !== "string" ||
    !current.sourceURL.startsWith("https://") ||
    typeof current.publishedAt !== "string" ||
    !current.publishedAt
  ) {
    throw new UpdateError(
      "This published article is missing immutable source or publication metadata and cannot be corrected through the dashboard.",
      409
    );
  }

  const articleDraft = {
    id: correctionId,
    publishedAt: current.publishedAt,
    updatedAt: current.updatedAt || null,
    ...patch,
    sourceName: current.sourceName,
    sourceURL: current.sourceURL,
    isActive: false,
  };

  return {
    draftSchemaVersion: 1,
    draftStatus: "PENDING_HUMAN_REVIEW",
    requiresHumanReview: true,
    publishReady: false,
    detectedAt: now,
    sourceEvidence: {
      sourceName: current.sourceName,
      sourceType: "manual_correction",
      sourceURL: current.sourceURL,
      listedDate:
        typeof current.effectiveDate === "string"
          ? current.effectiveDate.slice(0, 10)
          : now.slice(0, 10),
      reserveSignals: ["ADMIN_CORRECTION"],
      categoryHints: [patch.category],
      officialHostVerified: true,
      verificationMethod: "authenticated-admin-correction-confirmation",
      correctionOfArticleId: current.id,
    },
    reviewChecklist: reviewChecklist(),
    articleDraft,
    correction: {
      liveArticleId: current.id,
      submittedBy: session.sub,
      submittedAt: now,
      baseUpdatedAt: current.updatedAt || null,
    },
  };
}

function safeFence(value) {
  const text =
    typeof value === "object" && value !== null
      ? JSON.stringify(value, null, 2)
      : String(value ?? "Not specified");
  return `\`\`\`text\n${text.replaceAll("```", "`` `")}\n\`\`\``;
}

function renderReview(current, patch, correctionId, session, now) {
  const labels = {
    title: "Title",
    summary: "Summary",
    whyItMatters: "Why It Matters",
    details: "Details",
    category: "Category",
    status: "Status",
    priority: "Priority",
    effectiveDate: "Effective Date",
    audience: "Audience",
    isPinned: "Pinned",
  };

  const changedFields = Object.keys(patch).filter(
    (key) => !sameValue(patch[key], current[key])
  );

  const lines = [
    "# Reserve Intel Published Article Correction",
    "",
    "> **Human-approved dashboard correction.** The currently published article remains live until this pull request is merged and the existing publication workflow succeeds.",
    "",
    `- Live article ID: \`${current.id}\``,
    `- Correction draft ID: \`${correctionId}\``,
    `- Submitted by: \`${session.sub}\``,
    `- Submitted at: ${now}`,
    `- Official source: ${current.sourceURL}`,
    "- Source identity is immutable in the dashboard correction flow.",
    "",
    "## Proposed Changes",
    "",
  ];

  for (const key of changedFields) {
    lines.push(`### ${labels[key] || key}`);
    lines.push("");
    lines.push("**Currently published**");
    lines.push("");
    lines.push(safeFence(current[key]));
    lines.push("");
    lines.push("**Proposed correction**");
    lines.push("");
    lines.push(safeFence(patch[key]));
    lines.push("");
  }

  lines.push("## Publication Approval");
  lines.push("");
  lines.push(
    "> These confirmations were completed in the authenticated Reserve Intel dashboard before this correction PR was created. Merging this PR is the final publication action."
  );
  lines.push("");
  for (const check of PUBLISH_CHECKS) {
    lines.push(`- [x] ${check}`);
  }
  lines.push("");

  return lines.join("\n");
}

export async function handlePublished(request, env, deps) {
  const respond = (payload, status = 200) =>
    deps.jsonResponse(payload, status, env, request);
  let stage = "request-validation";

  try {
    if (request.method !== "POST") {
      throw new UpdateError(
        "Published corrections are now loaded from the hosted dashboard and submitted as GitHub review PRs.",
        405
      );
    }

    if (request.headers.get("Origin") !== env.FRONTEND_ORIGIN) {
      throw new UpdateError("Origin is not authorized.", 403);
    }

    const match = (request.headers.get("Authorization") || "").match(
      /^Bearer\s+(.+)$/i
    );
    if (!match) {
      throw new UpdateError("GitHub sign-in is required.", 401);
    }

    let session;
    try {
      session = await deps.verifySession(match[1], env.SESSION_SECRET);
    } catch {
      throw new UpdateError(
        "Your session expired. Sign in again; your edits are still in this tab.",
        401
      );
    }

    if (
      session.sub?.toLowerCase() !== "saltydogbibleapp" ||
      session.repository !== REPOSITORY ||
      env.GITHUB_REPOSITORY !== REPOSITORY
    ) {
      throw new UpdateError("Session is not authorized.", 403);
    }

    if (
      request.headers.get("Content-Type")?.split(";")[0].trim() !==
      "application/json"
    ) {
      throw new UpdateError("JSON content type is required.", 415);
    }

    stage = "request-parse";
    const body = await readJsonRequest(request, 128 * 1024);
    exactKeys(
      body,
      ["articleId", "baseUpdatedAt", "patch", "confirmations"],
      "Correction request"
    );

    if (
      typeof body.articleId !== "string" ||
      !/^[a-zA-Z0-9_-]{1,200}$/.test(body.articleId)
    ) {
      throw new UpdateError("Invalid article ID.");
    }

    if (
      body.baseUpdatedAt !== null &&
      (typeof body.baseUpdatedAt !== "string" || body.baseUpdatedAt.length > 80)
    ) {
      throw new UpdateError("Invalid article version.");
    }

    if (
      !Array.isArray(body.confirmations) ||
      body.confirmations.length !== CHECKS.length ||
      body.confirmations.some((check, index) => check !== CHECKS[index])
    ) {
      throw new UpdateError("Complete all six update confirmations.");
    }

    const patch = validatePatch(body.patch);

    stage = "installation-token";
    const token = await installationToken(env, deps);

    stage = "feed-fetch";
    const feedFile = await github(
      `/repos/${REPOSITORY}/contents/${FEED_PATH}?ref=main`,
      token
    );
    if (
      feedFile?.encoding !== "base64" ||
      typeof feedFile.content !== "string"
    ) {
      throw new UpdateError("The published feed could not be read.", 502);
    }

    let feed;
    try {
      feed = JSON.parse(decode(feedFile.content));
    } catch {
      throw new UpdateError("The published feed could not be decoded.", 502);
    }

    if (!Array.isArray(feed.intelArticles)) {
      throw new UpdateError("Invalid published feed.", 502);
    }

    stage = "article-lookup";
    const matches = feed.intelArticles.filter(
      (article) => article?.id === body.articleId
    );
    if (matches.length !== 1 || matches[0].isActive !== true) {
      throw new UpdateError(
        "This article is missing, inactive, or has a duplicate ID.",
        409
      );
    }

    const current = matches[0];
    const currentUpdatedAt = current.updatedAt || null;
    if (currentUpdatedAt !== body.baseUpdatedAt) {
      throw new UpdateError(
        "This article changed after your dashboard snapshot was generated. Cancel editing, refresh the dashboard, and reopen the article before submitting the correction.",
        409
      );
    }

    if (
      Object.keys(patch).every((key) => sameValue(patch[key], current[key]))
    ) {
      throw new UpdateError("No changes to submit.");
    }

    const now = nowIso();
    const correctionId = makeCorrectionId(current.id, now);
    const branch = `reserve-intel-review/${correctionId}`;
    const draftPath = `drafts/pending/${correctionId}.json`;
    const reviewPath = `reviews/pending/${correctionId}.md`;
    const draft = makeCorrectionDraft(
      current,
      patch,
      correctionId,
      session,
      now
    );
    const review = renderReview(
      current,
      patch,
      correctionId,
      session,
      now
    );

    stage = "branch-create";
    const mainRef = await github(
      `/repos/${REPOSITORY}/git/ref/heads/main`,
      token
    );
    const baseCommit = mainRef?.object?.sha;
    if (typeof baseCommit !== "string" || !/^[a-f0-9]{40}$/.test(baseCommit)) {
      throw new UpdateError("GitHub main branch could not be resolved.", 502);
    }

    await github(
      `/repos/${REPOSITORY}/git/refs`,
      token,
      "POST",
      {
        ref: `refs/heads/${branch}`,
        sha: baseCommit,
      }
    );

    stage = "draft-write";
    await github(
      `/repos/${REPOSITORY}/contents/${draftPath}`,
      token,
      "PUT",
      {
        branch,
        message: `Create Reserve Intel correction draft for ${current.id}`,
        content: encode(JSON.stringify(draft, null, 2) + "\n"),
      }
    );

    stage = "review-write";
    await github(
      `/repos/${REPOSITORY}/contents/${reviewPath}`,
      token,
      "PUT",
      {
        branch,
        message: `Add Reserve Intel correction review for ${current.id}`,
        content: encode(review + "\n"),
      }
    );

    stage = "pull-request-create";
    const title = `Reserve Intel Correction: ${current.title}`.slice(0, 250);
    const pr = await github(
      `/repos/${REPOSITORY}/pulls`,
      token,
      "POST",
      {
        title,
        head: branch,
        base: "main",
        body: review,
        draft: true,
        maintainer_can_modify: false,
      }
    );

    if (
      !Number.isSafeInteger(pr?.number) ||
      typeof pr?.html_url !== "string" ||
      !pr.html_url.startsWith("https://github.com/")
    ) {
      throw new UpdateError(
        "GitHub created the correction branch but did not return a valid review PR.",
        502
      );
    }

    return respond({
      ok: true,
      articleId: current.id,
      correctionId,
      branch,
      prNumber: pr.number,
      prUrl: pr.html_url,
    });
  } catch (error) {
    if (!(error instanceof UpdateError)) {
      console.error("Published correction failed", {
        stage,
        name: error?.name || "Error",
        message: error?.message || String(error),
      });
    }

    return respond(
      {
        ok: false,
        error:
          error instanceof UpdateError
            ? error.message
            : "The GitHub review PR could not be created. Your published article was not changed.",
      },
      error instanceof UpdateError ? error.status : 502
    );
  }
}
