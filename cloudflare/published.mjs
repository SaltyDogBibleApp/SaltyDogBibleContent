// Published-article corrections use the existing admin session and an atomic
// Contents API update. No draft, source identity, or publication ID is writable.
const REPOSITORY = "SaltyDogBibleApp/SaltyDogBibleContent";
const FEED_PATH = "reserve-content-feed.json";
const API = "https://api.github.com";
export const CHECKS = [
  "I opened the official source.",
  "I verified the facts against the official source.",
  "I verified the status and effective date.",
  "I verified the intended audience.",
  "I reviewed the title, summary, Why It Matters, and details.",
  "I approve this update to the published article.",
];
class UpdateError extends Error {
  constructor(message, status = 400) { super(message); this.status = status; }
}
function exactKeys(value, keys, label) {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      Object.keys(value).length !== keys.length || keys.some(k => !Object.hasOwn(value, k))) {
    throw new UpdateError(`${label} contains missing or unexpected fields.`);
  }
}
export function validatePatch(value) {
  exactKeys(value, ["title", "summary", "whyItMatters", "details", "category", "status", "priority", "effectiveDate", "audience", "isPinned"], "Article update");
  const result = {};
  for (const [key, max] of Object.entries({title:300, summary:4000, whyItMatters:6000, details:20000})) {
    if (typeof value[key] !== "string" || !value[key].trim() || value[key].length > max) throw new UpdateError(`${key} must contain 1–${max} characters.`);
    result[key] = value[key].trim();
  }
  const choices = {
    category: ["Legislation / NDAA", "Policy", "Pay & Benefits", "Retirement", "VA / Veteran Benefits", "Training & Readiness", "Admin", "Other"],
    status: ["TRACKING", "PROPOSED", "INTRODUCED", "COMMITTEE", "PASSED HOUSE", "PASSED SENATE", "SIGNED", "EFFECTIVE", "SUPERSEDED"],
    priority: ["NORMAL", "HIGH"],
  };
  for (const [key, allowed] of Object.entries(choices)) {
    if (!allowed.includes(value[key])) throw new UpdateError(`Unsupported ${key}.`);
    result[key] = value[key];
  }
  const date = value.effectiveDate;
  if (date !== null && (typeof date !== "string" || !/^\d{4}-\d{2}-\d{2}T00:00:00Z$/.test(date) ||
      !Number.isFinite(Date.parse(date)) || new Date(date).toISOString().replace(".000Z", "Z") !== date)) throw new UpdateError("Effective date must be a valid calendar date.");
  result.effectiveDate = date;
  exactKeys(value.audience, ["service", "reserveStatus", "trainingWing", "squadron"], "Audience");
  if (!["ALL", "USN", "USMC"].includes(value.audience.service) || !["ALL", "SELRES", "VTU"].includes(value.audience.reserveStatus)) throw new UpdateError("Unsupported audience.");
  result.audience = {...value.audience};
  for (const key of ["trainingWing", "squadron"]) {
    const text = value.audience[key];
    if (text !== null && (typeof text !== "string" || text.length > 120)) throw new UpdateError(`Invalid ${key}.`);
    result.audience[key] = text?.trim() || null;
  }
  if (typeof value.isPinned !== "boolean") throw new UpdateError("Pinned must be true or false.");
  result.isPinned = value.isPinned;
  return result;
}
async function boundedJson(input, limit) {
  if (!input.body) throw new UpdateError("Empty response or request.");
  const reader = input.body.getReader();
  const decoder = new TextDecoder();
  let size = 0, text = "";
  try {
    for (;;) {
      const {done, value} = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) { await reader.cancel(); throw new UpdateError("Payload is too large.", 413); }
      text += decoder.decode(value, {stream:true});
    }
    return JSON.parse(text + decoder.decode());
  } catch (error) {
    if (error instanceof UpdateError) throw error;
    throw new UpdateError("Invalid JSON response or request.");
  } finally { reader.releaseLock(); }
}
async function github(path, token, method = "GET", body) {
  const response = await fetch(`${API}${path}`, {
    method, redirect:"error", signal:AbortSignal.timeout(15000),
    headers:{Accept:"application/vnd.github+json", Authorization:`Bearer ${token}`,
      "X-GitHub-Api-Version":"2026-03-10", "User-Agent":"Salty-Dog-Reserve-Intel", "Content-Type":"application/json"},
    ...(body === undefined ? {} : {body:JSON.stringify(body)}),
  });
  if (!response.ok) {
    await response.body?.cancel();
    if (response.status === 409) throw new UpdateError("The feed changed while you were editing. Cancel and reopen the article before updating.", 409);
    throw new UpdateError(`GitHub could not complete the request (HTTP ${response.status}).`, 502);
  }
  return boundedJson(response, 2 * 1024 * 1024);
}
async function installationToken(env, deps, write) {
  const jwt = await deps.createGitHubAppJwt(env);
  const installation = await github(`/repos/${REPOSITORY}/installation`, jwt);
  if (!Number.isSafeInteger(installation.id)) throw new UpdateError("GitHub App installation was not found.", 502);
  const data = await github(`/app/installations/${installation.id}/access_tokens`, jwt, "POST", {
    repositories:["SaltyDogBibleContent"], permissions:{contents:write ? "write" : "read"},
  });
  if (typeof data.token !== "string" || !data.token) throw new UpdateError("GitHub App token was not available.", 502);
  return data.token;
}
function encode(text) {
  let binary = "";
  for (const byte of new TextEncoder().encode(text)) binary += String.fromCharCode(byte);
  return btoa(binary);
}
function decode(text) {
  return new TextDecoder().decode(Uint8Array.from(atob(text.replace(/\s/g, "")), c => c.charCodeAt(0)));
}
export async function handlePublished(request, env, deps) {
  const respond = (payload, status = 200) => deps.jsonResponse(payload, status, env, request);
  try {
    if (!["GET", "POST"].includes(request.method)) throw new UpdateError("Method not allowed.", 405);
    if (request.headers.get("Origin") !== env.FRONTEND_ORIGIN) throw new UpdateError("Origin is not authorized.", 403);
    const match = (request.headers.get("Authorization") || "").match(/^Bearer\s+(.+)$/i);
    if (!match) throw new UpdateError("GitHub sign-in is required.", 401);
    let session;
    try { session = await deps.verifySession(match[1], env.SESSION_SECRET); }
    catch { throw new UpdateError("Your session expired. Sign in again; your edits are still in this tab.", 401); }
    if (session.sub?.toLowerCase() !== "saltydogbibleapp" || session.repository !== REPOSITORY || env.GITHUB_REPOSITORY !== REPOSITORY) throw new UpdateError("Session is not authorized.", 403);
    const write = request.method === "POST";
    let body, patch;
    if (write) {
      if (request.headers.get("Content-Type")?.split(";")[0].trim() !== "application/json") throw new UpdateError("JSON content type is required.", 415);
      body = await boundedJson(request, 128 * 1024);
      exactKeys(body, ["articleId", "baseSha", "patch", "confirmations"], "Update request");
      if (!Array.isArray(body.confirmations) || body.confirmations.length !== CHECKS.length || body.confirmations.some((c, i) => c !== CHECKS[i])) throw new UpdateError("Complete all six update confirmations.");
      if (typeof body.baseSha !== "string" || !/^[a-f0-9]{40}$/.test(body.baseSha)) throw new UpdateError("Reopen this article to load its current version.");
      patch = validatePatch(body.patch);
    }
    const id = write ? body.articleId : new URL(request.url).searchParams.get("id");
    if (typeof id !== "string" || !/^[a-zA-Z0-9_-]{1,200}$/.test(id)) throw new UpdateError("Invalid article ID.");
    const token = await installationToken(env, deps, write);
    const path = `/repos/${REPOSITORY}/contents/${FEED_PATH}`;
    const file = await github(`${path}?ref=main`, token);
    if (file.encoding !== "base64" || typeof file.content !== "string" || typeof file.sha !== "string") throw new UpdateError("The published feed could not be read.", 502);
    const feed = JSON.parse(decode(file.content));
    if (!Array.isArray(feed.intelArticles)) throw new UpdateError("Invalid published feed.", 502);
    const matches = feed.intelArticles.filter(a => a?.id === id);
    if (matches.length !== 1 || matches[0].isActive !== true) throw new UpdateError("This article is missing, inactive, or has a duplicate ID.", 409);
    const article = matches[0];
    if (!write) return respond({ok:true, article, baseSha:file.sha});
    if (file.sha !== body.baseSha) throw new UpdateError("The feed changed while you were editing. Cancel and reopen the article before updating.", 409);
    if (Object.keys(patch).every(k => JSON.stringify(patch[k]) === JSON.stringify(article[k]))) throw new UpdateError("No changes to publish.");
    const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    const updated = {...article, ...patch, updatedAt:now};
    feed.intelArticles = feed.intelArticles.map(a => a.id === id ? updated : a);
    feed.generatedAt = now;
    const result = await github(path, token, "PUT", {
      branch:"main", sha:file.sha,
      message:`Update published Reserve Intel article ${id}\n\nApproved by ${session.sub} at ${now}\nBase feed: ${file.sha}\n\n${CHECKS.map(c => `- [x] ${c}`).join("\n")}`,
      content:encode(JSON.stringify(feed, null, 2) + "\n"),
    });
    return respond({ok:true, article:updated, baseSha:result.content?.sha, commit:result.commit?.sha});
  } catch (error) {
    if (!(error instanceof UpdateError)) console.error("Published update failed", {name:error.name});
    return respond({ok:false, error:error instanceof UpdateError ? error.message : "Update could not be confirmed. Reopen the article to check its current version before retrying."}, error instanceof UpdateError ? error.status : 502);
  }
}
