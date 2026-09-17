import { handlePublished } from "./published.mjs";

const CALLBACK_PATH = "/auth/callback";
const LOGIN_PATH = "/auth/login";
const STATUS_PATH = "/auth/status";
const LOGOUT_PATH = "/auth/logout";
const GITHUB_APP_CHECK_PATH = "/api/github-app-check";

const GITHUB_API_VERSION = "2026-03-10";
const AUTHORIZED_GITHUB_LOGIN = "SaltyDogBibleApp";

const SESSION_LIFETIME_SECONDS = 30 * 60;
const SESSION_AUDIENCE = "salty-dog-reserve-intel-admin";

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);

      if (request.method === "OPTIONS") {
        return handleOptions(request, env);
      }

      if (url.pathname === "/api/published-article") {
        return await handlePublished(request, env, {
          verifySession, createGitHubAppJwt, jsonResponse,
        });
      }

      if (url.pathname === "/") {
        return jsonResponse(
          {
            ok: true,
            service: "Salty Dog Reserve Intel Auth",
            authLogin: `${url.origin}${LOGIN_PATH}`,
            repository: env.GITHUB_REPOSITORY,
          },
          200,
          env,
          request
        );
      }

      if (url.pathname === LOGIN_PATH && request.method === "GET") {
        return startGitHubLogin(url, env);
      }

      if (url.pathname === CALLBACK_PATH && request.method === "GET") {
        return finishGitHubLogin(request, url, env);
      }

      if (url.pathname === STATUS_PATH && request.method === "GET") {
        return sessionStatus(request, env);
      }

      if (
        url.pathname === GITHUB_APP_CHECK_PATH &&
        request.method === "GET"
      ) {
        return githubAppCheck(request, env);
      }

      if (url.pathname === LOGOUT_PATH && request.method === "POST") {
        return jsonResponse(
          {
            ok: true,
            loggedOut: true,
          },
          200,
          env,
          request
        );
      }

      return jsonResponse(
        {
          ok: false,
          error: "Not found.",
        },
        404,
        env,
        request
      );
    } catch (error) {
      console.error("Reserve Intel auth error:", error);

      return jsonResponse(
        {
          ok: false,
          error: "Authentication service error.",
        },
        500,
        env,
        request
      );
    }
  },
};

async function startGitHubLogin(url, env) {
  requireConfiguration(env);

  const state = randomToken(32);
  const redirectUri = `${url.origin}${CALLBACK_PATH}`;

  const authorize = new URL(
    "https://github.com/login/oauth/authorize"
  );

  authorize.searchParams.set(
    "client_id",
    env.GITHUB_CLIENT_ID
  );

  authorize.searchParams.set(
    "redirect_uri",
    redirectUri
  );

  authorize.searchParams.set(
    "state",
    state
  );

  authorize.searchParams.set(
    "allow_signup",
    "false"
  );

  const headers = new Headers();

  headers.set(
    "Location",
    authorize.toString()
  );

  headers.set(
    "Set-Cookie",
    [
      `reserve_intel_oauth_state=${state}`,
      "Path=/auth",
      "HttpOnly",
      "Secure",
      "SameSite=Lax",
      "Max-Age=600",
    ].join("; ")
  );

  headers.set("Cache-Control", "no-store");
  headers.set("X-Robots-Tag", "noindex, nofollow");

  return new Response(null, {
    status: 302,
    headers,
  });
}

async function finishGitHubLogin(request, url, env) {
  requireConfiguration(env);

  const code = url.searchParams.get("code");
  const returnedState = url.searchParams.get("state");
  const storedState = readCookie(
    request,
    "reserve_intel_oauth_state"
  );

  if (!code) {
    return authFailure(
      "GitHub did not return an authorization code."
    );
  }

  if (
    !returnedState ||
    !storedState ||
    !constantTimeEqual(returnedState, storedState)
  ) {
    return authFailure(
      "The GitHub authentication state did not match. Please start the login again."
    );
  }

  const redirectUri = `${url.origin}${CALLBACK_PATH}`;

  const tokenResponse = await fetch(
    "https://github.com/login/oauth/access_token",
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        client_id: env.GITHUB_CLIENT_ID,
        client_secret: env.GITHUB_CLIENT_SECRET,
        code,
        redirect_uri: redirectUri,
      }),
    }
  );

  const tokenPayload = await tokenResponse.json();

  if (
    !tokenResponse.ok ||
    typeof tokenPayload.access_token !== "string" ||
    !tokenPayload.access_token
  ) {
    console.error("GitHub token exchange failed:", {
      status: tokenResponse.status,
      error: tokenPayload.error,
      error_description: tokenPayload.error_description,
    });

    return authFailure(
      "GitHub did not issue a valid user access token."
    );
  }

  const accessToken = tokenPayload.access_token;

  const user = await githubJson(
    "https://api.github.com/user",
    accessToken
  );

  if (
    typeof user.login !== "string" ||
    user.login.toLowerCase() !==
      AUTHORIZED_GITHUB_LOGIN.toLowerCase()
  ) {
    return authFailure(
      `GitHub account ${
        user.login || "unknown"
      } is not authorized for Reserve Intel review.`,
      403
    );
  }

  const repositoryAccess =
    await verifyRepositoryAccess(
      accessToken,
      env.GITHUB_REPOSITORY
    );

  if (!repositoryAccess.authorized) {
    return authFailure(
      "Your GitHub account is authenticated, but the Salty Dog Reserve Intel GitHub App does not have the required repository access.",
      403
    );
  }

  const session = await createSession(
    {
      login: user.login,
      repository: env.GITHUB_REPOSITORY,
    },
    env.SESSION_SECRET
  );

  return authSuccess(
    user.login,
    session.token,
    session.expiresAt,
    env
  );
}

async function sessionStatus(request, env) {
  requireConfiguration(env);

  const authorization =
    request.headers.get("Authorization") || "";

  const match = authorization.match(
    /^Bearer\s+(.+)$/i
  );

  if (!match) {
    return jsonResponse(
      {
        ok: false,
        authenticated: false,
        error: "Authentication required.",
      },
      401,
      env,
      request
    );
  }

  try {
    const payload = await verifySession(
      match[1],
      env.SESSION_SECRET
    );

    if (
      payload.sub.toLowerCase() !==
        AUTHORIZED_GITHUB_LOGIN.toLowerCase() ||
      payload.repository.toLowerCase() !==
        env.GITHUB_REPOSITORY.toLowerCase()
    ) {
      throw new Error("Session authorization mismatch.");
    }

    return jsonResponse(
      {
        ok: true,
        authenticated: true,
        login: payload.sub,
        repository: payload.repository,
        expiresAt: new Date(
          payload.exp * 1000
        ).toISOString(),
      },
      200,
      env,
      request
    );
  } catch {
    return jsonResponse(
      {
        ok: false,
        authenticated: false,
        error: "Session is invalid or expired.",
      },
      401,
      env,
      request
    );
  }
}

async function createSession(identity, secret) {
  const issuedAt = Math.floor(Date.now() / 1000);

  const expiresAt =
    issuedAt + SESSION_LIFETIME_SECONDS;

  const payload = {
    iss: "salty-dog-reserve-intel-auth",
    aud: SESSION_AUDIENCE,
    sub: identity.login,
    repository: identity.repository,
    iat: issuedAt,
    exp: expiresAt,
  };

  const encodedPayload = base64UrlEncode(
    JSON.stringify(payload)
  );

  const signature = await signValue(
    encodedPayload,
    secret
  );

  return {
    token: `${encodedPayload}.${signature}`,
    expiresAt: new Date(
      expiresAt * 1000
    ).toISOString(),
  };
}

async function verifySession(token, secret) {
  if (
    typeof token !== "string" ||
    token.length > 4096
  ) {
    throw new Error("Invalid session token.");
  }

  const parts = token.split(".");

  if (parts.length !== 2) {
    throw new Error("Malformed session token.");
  }

  const [encodedPayload, suppliedSignature] = parts;

  const expectedSignature = await signValue(
    encodedPayload,
    secret
  );

  if (
    !constantTimeEqual(
      suppliedSignature,
      expectedSignature
    )
  ) {
    throw new Error("Invalid session signature.");
  }

  const payload = JSON.parse(
    base64UrlDecode(encodedPayload)
  );

  if (
    !payload ||
    payload.aud !== SESSION_AUDIENCE ||
    typeof payload.sub !== "string" ||
    typeof payload.repository !== "string" ||
    typeof payload.iat !== "number" ||
    typeof payload.exp !== "number"
  ) {
    throw new Error("Invalid session payload.");
  }

  const now = Math.floor(Date.now() / 1000);

  if (payload.exp <= now) {
    throw new Error("Session expired.");
  }

  if (payload.iat > now + 60) {
    throw new Error("Invalid session timestamp.");
  }

  return payload;
}

async function signValue(value, secret) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    {
      name: "HMAC",
      hash: "SHA-256",
    },
    false,
    ["sign"]
  );

  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(value)
  );

  return bytesToBase64Url(
    new Uint8Array(signature)
  );
}

function base64UrlEncode(value) {
  return bytesToBase64Url(
    new TextEncoder().encode(value)
  );
}

function base64UrlDecode(value) {
  const normalized = value
    .replaceAll("-", "+")
    .replaceAll("_", "/");

  const padded =
    normalized +
    "=".repeat(
      (4 - (normalized.length % 4)) % 4
    );

  const binary = atob(padded);

  const bytes = Uint8Array.from(
    binary,
    (char) => char.charCodeAt(0)
  );

  return new TextDecoder().decode(bytes);
}

function bytesToBase64Url(bytes) {
  let binary = "";

  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }

  return btoa(binary)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

async function verifyRepositoryAccess(
  accessToken,
  repositoryFullName
) {
  const installations = await githubJson(
    "https://api.github.com/user/installations?per_page=100",
    accessToken
  );

  if (
    !Array.isArray(
      installations.installations
    )
  ) {
    return {
      authorized: false,
    };
  }

  for (const installation of installations.installations) {
    if (!installation?.id) {
      continue;
    }

    const repositories = await githubJson(
      `https://api.github.com/user/installations/${installation.id}/repositories?per_page=100`,
      accessToken
    );

    if (
      !Array.isArray(
        repositories.repositories
      )
    ) {
      continue;
    }

    const repository =
      repositories.repositories.find(
        (candidate) =>
          typeof candidate?.full_name === "string" &&
          candidate.full_name.toLowerCase() ===
            repositoryFullName.toLowerCase()
      );

    if (!repository) {
      continue;
    }

    const permissions =
      repository.permissions || {};

    const canWrite =
      permissions.admin === true ||
      permissions.maintain === true ||
      permissions.push === true;

    return {
      authorized: canWrite,
      installationId: installation.id,
    };
  }

  return {
    authorized: false,
  };
}

async function githubJson(endpoint, accessToken) {
  const response = await fetch(
    endpoint,
    {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${accessToken}`,
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "Salty-Dog-Reserve-Intel",
      },
    }
  );

  let payload = null;

  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (
    !response.ok ||
    !payload
  ) {
    console.error(
      "GitHub API request failed:",
      {
        endpoint,
        status: response.status,
      }
    );

    throw new Error(
      `GitHub API request failed with HTTP ${response.status}.`
    );
  }

  return payload;
}

async function githubAppCheck(request, env) {
  const authorization =
    request.headers.get("Authorization") || "";

  const match = authorization.match(
    /^Bearer\s+(.+)$/i
  );

  if (!match) {
    return jsonResponse(
      {
        ok: false,
        error: "Authentication required.",
      },
      401,
      env,
      request
    );
  }

  let session;

  try {
    session = await verifySession(
      match[1],
      env.SESSION_SECRET
    );
  } catch {
    return jsonResponse(
      {
        ok: false,
        error: "Session is invalid or expired.",
      },
      401,
      env,
      request
    );
  }

  if (
    session.sub.toLowerCase() !==
      AUTHORIZED_GITHUB_LOGIN.toLowerCase() ||
    session.repository.toLowerCase() !==
      env.GITHUB_REPOSITORY.toLowerCase()
  ) {
    return jsonResponse(
      {
        ok: false,
        error: "Session is not authorized.",
      },
      403,
      env,
      request
    );
  }

  if (
    !env.GITHUB_APP_ID ||
    !env.GITHUB_PRIVATE_KEY
  ) {
    return jsonResponse(
      {
        ok: false,
        error: "GitHub App credentials are not configured.",
      },
      500,
      env,
      request
    );
  }

  const parts =
    env.GITHUB_REPOSITORY.split("/");

  if (parts.length !== 2) {
    throw new Error(
      "GITHUB_REPOSITORY must be owner/repository."
    );
  }

  const [owner, repository] = parts;

  const appJwt =
    await createGitHubAppJwt(env);

  const installationResponse = await fetch(
    `https://api.github.com/repos/${encodeURIComponent(
      owner
    )}/${encodeURIComponent(
      repository
    )}/installation`,
    {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${appJwt}`,
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "Salty-Dog-Reserve-Intel",
      },
    }
  );

  let installation = null;

  try {
    installation =
      await installationResponse.json();
  } catch {
    installation = null;
  }

  if (
    !installationResponse.ok ||
    !installation?.id
  ) {
    console.error(
      "GitHub installation lookup failed:",
      installationResponse.status
    );

    return jsonResponse(
      {
        ok: false,
        error: "Could not verify the GitHub App installation.",
      },
      502,
      env,
      request
    );
  }

  const tokenResponse = await fetch(
    `https://api.github.com/app/installations/${installation.id}/access_tokens`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${appJwt}`,
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "Salty-Dog-Reserve-Intel",
      },
      body: JSON.stringify({
        repositories: [
          repository,
        ],
        permissions: {
          contents: "read",
          pull_requests: "read",
        },
      }),
    }
  );

  let tokenPayload = null;

  try {
    tokenPayload =
      await tokenResponse.json();
  } catch {
    tokenPayload = null;
  }

  if (
    !tokenResponse.ok ||
    typeof tokenPayload?.token !== "string"
  ) {
    console.error(
      "Installation-token creation failed:",
      tokenResponse.status
    );

    return jsonResponse(
      {
        ok: false,
        error: "Could not create a GitHub installation token.",
      },
      502,
      env,
      request
    );
  }

  /*
   * Never return or log this token.
   */
  const installationToken =
    tokenPayload.token;

  const repositoriesResponse = await fetch(
    "https://api.github.com/installation/repositories?per_page=100",
    {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${installationToken}`,
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "Salty-Dog-Reserve-Intel",
      },
    }
  );

  let repositoriesPayload = null;

  try {
    repositoriesPayload =
      await repositoriesResponse.json();
  } catch {
    repositoriesPayload = null;
  }

  if (
    !repositoriesResponse.ok ||
    !Array.isArray(
      repositoriesPayload?.repositories
    )
  ) {
    return jsonResponse(
      {
        ok: false,
        error:
          "Installation token was created but repository access could not be verified.",
      },
      502,
      env,
      request
    );
  }

  const repositoryVerified =
    repositoriesPayload.repositories.some(
      (candidate) =>
        candidate?.full_name?.toLowerCase() ===
        env.GITHUB_REPOSITORY.toLowerCase()
    );

  if (!repositoryVerified) {
    return jsonResponse(
      {
        ok: false,
        error:
          "Installation token does not have access to the expected repository.",
      },
      403,
      env,
      request
    );
  }

  return jsonResponse(
    {
      ok: true,
      githubAppReady: true,
      appId: String(
        env.GITHUB_APP_ID
      ),
      repository: env.GITHUB_REPOSITORY,
      repositoryVerified: true,
      installationId: installation.id,
      installedOn:
        installation.account?.login || null,
      tokenExpiresAt:
        tokenPayload.expires_at || null,
      permissions:
        tokenPayload.permissions || null,
    },
    200,
    env,
    request
  );
}

async function createGitHubAppJwt(env) {
  const now =
    Math.floor(Date.now() / 1000);

  const header = base64UrlEncode(
    JSON.stringify({
      alg: "RS256",
      typ: "JWT",
    })
  );

  const payload = base64UrlEncode(
    JSON.stringify({
      iat: now - 60,
      exp: now + 9 * 60,
      iss: String(
        env.GITHUB_APP_ID
      ),
    })
  );

  const signingInput =
    `${header}.${payload}`;

  const privateKey =
    await importGitHubPrivateKey(
      env.GITHUB_PRIVATE_KEY
    );

  const signature =
    await crypto.subtle.sign(
      {
        name: "RSASSA-PKCS1-v1_5",
      },
      privateKey,
      new TextEncoder().encode(
        signingInput
      )
    );

  return (
    signingInput +
    "." +
    bytesToBase64Url(
      new Uint8Array(signature)
    )
  );
}

async function importGitHubPrivateKey(pem) {
  let keyData;

  if (
    pem.includes(
      "BEGIN RSA PRIVATE KEY"
    )
  ) {
    const pkcs1 =
      pemToDer(pem);

    keyData =
      wrapPkcs1InPkcs8(
        pkcs1
      );
  } else if (
    pem.includes(
      "BEGIN PRIVATE KEY"
    )
  ) {
    keyData =
      pemToDer(pem);
  } else {
    throw new Error(
      "Unsupported GitHub private key format."
    );
  }

  return crypto.subtle.importKey(
    "pkcs8",
    keyData,
    {
      name: "RSASSA-PKCS1-v1_5",
      hash: "SHA-256",
    },
    false,
    ["sign"]
  );
}

function pemToDer(pem) {
  const base64 =
    pem
      .replace(
        /-----BEGIN [^-]+-----/g,
        ""
      )
      .replace(
        /-----END [^-]+-----/g,
        ""
      )
      .replace(
        /\s+/g,
        ""
      );

  if (!base64) {
    throw new Error(
      "Private key PEM is empty."
    );
  }

  const binary =
    atob(base64);

  const bytes =
    new Uint8Array(
      binary.length
    );

  for (
    let index = 0;
    index < binary.length;
    index += 1
  ) {
    bytes[index] =
      binary.charCodeAt(index);
  }

  return bytes;
}

function wrapPkcs1InPkcs8(pkcs1) {
  const version =
    new Uint8Array([
      0x02,
      0x01,
      0x00,
    ]);

  const rsaAlgorithm =
    new Uint8Array([
      0x30,
      0x0d,
      0x06,
      0x09,
      0x2a,
      0x86,
      0x48,
      0x86,
      0xf7,
      0x0d,
      0x01,
      0x01,
      0x01,
      0x05,
      0x00,
    ]);

  const privateKey =
    concatBytes(
      new Uint8Array([
        0x04,
      ]),
      derLength(
        pkcs1.length
      ),
      pkcs1
    );

  const body =
    concatBytes(
      version,
      rsaAlgorithm,
      privateKey
    );

  return concatBytes(
    new Uint8Array([
      0x30,
    ]),
    derLength(
      body.length
    ),
    body
  );
}

function derLength(length) {
  if (length < 128) {
    return new Uint8Array([
      length,
    ]);
  }

  const bytes = [];
  let remaining = length;

  while (remaining > 0) {
    bytes.unshift(
      remaining & 0xff
    );

    remaining >>>= 8;
  }

  return new Uint8Array([
    0x80 | bytes.length,
    ...bytes,
  ]);
}

function concatBytes(...arrays) {
  const totalLength =
    arrays.reduce(
      (sum, array) =>
        sum + array.length,
      0
    );

  const result =
    new Uint8Array(
      totalLength
    );

  let offset = 0;

  for (const array of arrays) {
    result.set(
      array,
      offset
    );

    offset += array.length;
  }

  return result;
}

function authSuccess(
  login,
  sessionToken,
  expiresAt,
  env
) {
  const safeLogin =
    escapeHtml(login);

  const safeOrigin =
    JSON.stringify(
      env.FRONTEND_ORIGIN
    );

  const safeFrontend =
    escapeHtml(
      env.FRONTEND_URL
    );

  const safeToken =
    JSON.stringify(
      sessionToken
    );

  const safeExpires =
    JSON.stringify(
      expiresAt
    );

  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>Reserve Intel — Authorized</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #f4f6f8;
      color: #18202b;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    main {
      width: min(520px, calc(100% - 40px));
      padding: 36px;
      background: white;
      border: 1px solid #d9e0e7;
      border-radius: 18px;
      box-shadow: 0 12px 36px rgba(0,0,0,.08);
    }

    .eyebrow {
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .14em;
      color: #586574;
    }

    h1 {
      margin: 10px 0 14px;
      font-size: 30px;
    }

    p {
      line-height: 1.55;
      color: #4d5967;
    }

    .success {
      display: inline-block;
      margin: 8px 0 20px;
      padding: 8px 12px;
      border-radius: 999px;
      background: #e8f7ed;
      color: #176b37;
      font-weight: 700;
    }

    a {
      display: inline-block;
      margin-top: 8px;
      padding: 12px 16px;
      border-radius: 10px;
      background: #18202b;
      color: white;
      text-decoration: none;
      font-weight: 700;
    }
  </style>
</head>
<body>
  <main>
    <div class="eyebrow">SALTY DOG BIBLE</div>

    <h1>GitHub authentication successful</h1>

    <div class="success">Authorized</div>

    <p>
      Signed in as <strong>${safeLogin}</strong>.
    </p>

    <p>
      A secure 30-minute Reserve Intel admin session was created.
    </p>

    <p id="popup-status">
      You may now return to Reserve Intel.
    </p>

    <a href="${safeFrontend}">
      Return to Reserve Intel
    </a>
  </main>

  <script>
    const sessionMessage = {
      type: "salty-dog-reserve-intel-auth",
      token: ${safeToken},
      login: ${JSON.stringify(login)},
      expiresAt: ${safeExpires}
    };

    if (window.opener && !window.opener.closed) {
      window.opener.postMessage(
        sessionMessage,
        ${safeOrigin}
      );

      document.getElementById(
        "popup-status"
      ).textContent =
        "Authentication was sent securely back to the Reserve Intel dashboard. This window may be closed.";

      setTimeout(() => {
        window.close();
      }, 1200);
    }
  </script>
</body>
</html>`;

  const headers =
    new Headers({
      "Content-Type":
        "text/html; charset=utf-8",
      "Cache-Control":
        "no-store",
      "X-Robots-Tag":
        "noindex, nofollow",
    });

  headers.append(
    "Set-Cookie",
    "reserve_intel_oauth_state=; Path=/auth; HttpOnly; Secure; SameSite=Lax; Max-Age=0"
  );

  return new Response(
    html,
    {
      status: 200,
      headers,
    }
  );
}

function authFailure(
  message,
  status = 400
) {
  const safeMessage =
    escapeHtml(message);

  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>Reserve Intel — Authentication Failed</title>
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:40px;background:#f4f6f8;color:#18202b">
  <main style="max-width:600px;margin:auto;background:white;padding:32px;border-radius:16px">
    <h1>Authentication failed</h1>
    <p>${safeMessage}</p>
    <p>
      <a href="/auth/login">
        Try GitHub sign-in again
      </a>
    </p>
  </main>
</body>
</html>`;

  const headers =
    new Headers({
      "Content-Type":
        "text/html; charset=utf-8",
      "Cache-Control":
        "no-store",
      "X-Robots-Tag":
        "noindex, nofollow",
    });

  headers.append(
    "Set-Cookie",
    "reserve_intel_oauth_state=; Path=/auth; HttpOnly; Secure; SameSite=Lax; Max-Age=0"
  );

  return new Response(
    html,
    {
      status,
      headers,
    }
  );
}

function requireConfiguration(env) {
  const required = [
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "GITHUB_REPOSITORY",
    "FRONTEND_ORIGIN",
    "FRONTEND_URL",
    "SESSION_SECRET",
  ];

  const missing =
    required.filter(
      (key) =>
        typeof env[key] !== "string" ||
        !env[key].trim()
    );

  if (missing.length) {
    throw new Error(
      `Missing required Worker configuration: ${missing.join(
        ", "
      )}`
    );
  }
}

function randomToken(byteLength) {
  const bytes =
    new Uint8Array(
      byteLength
    );

  crypto.getRandomValues(bytes);

  return Array.from(
    bytes,
    (byte) =>
      byte
        .toString(16)
        .padStart(2, "0")
  ).join("");
}

function readCookie(request, name) {
  const raw =
    request.headers.get("Cookie") || "";

  for (const piece of raw.split(";")) {
    const [key, ...rest] =
      piece
        .trim()
        .split("=");

    if (key === name) {
      return rest.join("=");
    }
  }

  return null;
}

function constantTimeEqual(a, b) {
  if (
    typeof a !== "string" ||
    typeof b !== "string" ||
    a.length !== b.length
  ) {
    return false;
  }

  let mismatch = 0;

  for (
    let i = 0;
    i < a.length;
    i += 1
  ) {
    mismatch |=
      a.charCodeAt(i) ^
      b.charCodeAt(i);
  }

  return mismatch === 0;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function corsHeaders(env, request) {
  const origin =
    request.headers.get("Origin");

  if (
    !origin ||
    origin !== env.FRONTEND_ORIGIN
  ) {
    return {};
  }

  return {
    "Access-Control-Allow-Origin":
      env.FRONTEND_ORIGIN,
    "Access-Control-Allow-Methods":
      "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers":
      "Content-Type,Authorization",
    "Access-Control-Max-Age":
      "86400",
    Vary: "Origin",
  };
}

function handleOptions(request, env) {
  const origin =
    request.headers.get("Origin");

  if (
    origin !== env.FRONTEND_ORIGIN
  ) {
    return new Response(
      null,
      {
        status: 403,
        headers: {
          "Cache-Control":
            "no-store",
        },
      }
    );
  }

  return new Response(
    null,
    {
      status: 204,
      headers:
        corsHeaders(
          env,
          request
        ),
    }
  );
}

function jsonResponse(
  payload,
  status,
  env,
  request
) {
  return new Response(
    JSON.stringify(
      payload,
      null,
      2
    ),
    {
      status,
      headers: {
        "Content-Type":
          "application/json; charset=utf-8",
        "Cache-Control":
          "no-store",
        "X-Robots-Tag":
          "noindex, nofollow",
        ...corsHeaders(
          env,
          request
        ),
      },
    }
  );
}
