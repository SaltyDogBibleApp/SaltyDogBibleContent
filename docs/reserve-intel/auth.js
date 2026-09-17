(() => {
  const AUTH_ORIGIN = "https://salty-dog-reserve-intel-auth.saltydogbibleapp.workers.dev";
  const SESSION_KEY = "reserveIntelAdminSession";

  const authState = {
    token: null,
    login: null,
    expiresAt: null,
    authenticated: false,
  };

  let loginPopup = null;
  let appCheckRunning = false;

  function byIdSafe(id) {
    return document.getElementById(id);
  }

  function notify(message, tone = "neutral") {
    if (typeof window.showToast === "function") {
      window.showToast(message, tone);
      return;
    }
    console.log(message);
  }

  function ensureAuthControls() {
    if (byIdSafe("auth-status")) return;

    const container = document.querySelector(".topbar-meta");
    if (!container) return;

    const status = document.createElement("span");
    status.id = "auth-status";
    status.className = "service-status";
    status.textContent = "Checking GitHub sign-in…";

    const signIn = document.createElement("button");
    signIn.id = "auth-sign-in-button";
    signIn.className = "button secondary";
    signIn.type = "button";
    signIn.textContent = "Sign in with GitHub";

    const signOut = document.createElement("button");
    signOut.id = "auth-sign-out-button";
    signOut.className = "button secondary hidden";
    signOut.type = "button";
    signOut.textContent = "Sign out";

    const appCheck = document.createElement("button");
    appCheck.id = "github-app-check-button";
    appCheck.className = "button secondary hidden";
    appCheck.type = "button";
    appCheck.textContent = "Verify GitHub Connection";

    const appStatus = document.createElement("span");
    appStatus.id = "github-app-check-status";
    appStatus.className = "service-status hidden";
    appStatus.setAttribute("role", "status");
    appStatus.setAttribute("aria-live", "polite");

    container.prepend(appStatus);
    container.prepend(appCheck);
    container.prepend(signOut);
    container.prepend(signIn);
    container.prepend(status);
  }

  function loadStoredSession() {
    try {
      const raw = window.sessionStorage.getItem(SESSION_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed.token !== "string") return null;
      return parsed;
    } catch {
      return null;
    }
  }

  function storeSession(session) {
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }

  function clearSession() {
    window.sessionStorage.removeItem(SESSION_KEY);
    authState.token = null;
    authState.login = null;
    authState.expiresAt = null;
    authState.authenticated = false;
  }

  function applySession(session) {
    authState.token = session.token;
    authState.login = session.login || null;
    authState.expiresAt = session.expiresAt || null;
    authState.authenticated = true;
    storeSession({
      token: authState.token,
      login: authState.login,
      expiresAt: authState.expiresAt,
    });
  }

  function renderAuthState() {
    const status = byIdSafe("auth-status");
    const signIn = byIdSafe("auth-sign-in-button");
    const signOut = byIdSafe("auth-sign-out-button");

    if (!status || !signIn || !signOut) return;

    const appCheck = byIdSafe("github-app-check-button");
    const appStatus = byIdSafe("github-app-check-status");
    appCheck.classList.toggle("hidden", !authState.authenticated);
    appCheck.disabled = appCheckRunning || !authState.authenticated;
    if (!authState.authenticated) {
      appStatus.textContent = "";
      appStatus.className = "service-status hidden";
    }

    if (authState.authenticated) {
      status.textContent = `Signed in as ${authState.login || "GitHub user"}`;
      status.className = "service-status connected";
      signIn.classList.add("hidden");
      signOut.classList.remove("hidden");
      return;
    }

    status.textContent = "GitHub sign-in required";
    status.className = "service-status unavailable";
    signIn.classList.remove("hidden");
    signOut.classList.add("hidden");
  }

  async function checkGitHubApp() {
    if (appCheckRunning || !authState.authenticated) return;
    const tokenAtStart = authState.token;
    const status = byIdSafe("github-app-check-status");
    const button = byIdSafe("github-app-check-button");
    appCheckRunning = true;
    button.textContent = "Verifying GitHub Connection…";
    status.textContent = "Verifying repository connection…";
    status.className = "service-status";
    renderAuthState();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 20000);

    try {
      const response = await authenticatedFetch("/api/github-app-check", {
        method: "GET",
        cache: "no-store",
        signal: controller.signal,
      });
      if (response.status === 401) {
        notify("Your session expired. Sign in with GitHub and try again.", "warning");
        return;
      }
      const payload = await response.json().catch(() => null);
      if (authState.token !== tokenAtStart) return;
      if (!response.ok) {
        throw new Error(payload?.error || `GitHub connection check failed (HTTP ${response.status}).`);
      }
      if (
        payload?.ok !== true ||
        payload.githubAppReady !== true ||
        payload.repositoryVerified !== true ||
        payload.repository !== "SaltyDogBibleApp/SaltyDogBibleContent" ||
        payload.permissions?.contents !== "read" ||
        payload.permissions?.pull_requests !== "read"
      ) {
        throw new Error("The response did not confirm the expected repository access.");
      }
      status.textContent = "GitHub connected — repository access verified";
      status.className = "service-status connected";
      notify("GitHub connection verified.", "success");
    } catch (error) {
      if (authState.token !== tokenAtStart) return;
      status.textContent = error.name === "AbortError"
        ? "GitHub connection check timed out. Try again."
        : error.message || "Could not verify the GitHub connection. Try again.";
      status.className = "service-status unavailable";
    } finally {
      window.clearTimeout(timeout);
      appCheckRunning = false;
      button.textContent = "Verify GitHub Connection";
      renderAuthState();
    }
  }

  async function validateSession(token) {
    const response = await fetch(`${AUTH_ORIGIN}/auth/status`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok || payload?.authenticated !== true) {
      throw new Error(payload?.error || "Session is invalid or expired.");
    }

    return payload;
  }

  async function restoreSession() {
    const stored = loadStoredSession();
    if (!stored?.token) {
      clearSession();
      renderAuthState();
      return;
    }

    try {
      const payload = await validateSession(stored.token);
      applySession({
        token: stored.token,
        login: payload.login,
        expiresAt: payload.expiresAt,
      });
    } catch {
      clearSession();
    }

    renderAuthState();
  }

  function signIn() {
    const width = 720;
    const height = 760;
    const left = Math.max(0, Math.round(window.screenX + (window.outerWidth - width) / 2));
    const top = Math.max(0, Math.round(window.screenY + (window.outerHeight - height) / 2));

    loginPopup = window.open(
      `${AUTH_ORIGIN}/auth/login`,
      "reserve-intel-github-auth",
      `popup=yes,width=${width},height=${height},left=${left},top=${top}`
    );

    if (!loginPopup) {
      notify("GitHub sign-in popup was blocked. Allow popups for this page and try again.", "warning");
      return;
    }

    loginPopup.focus();
  }

  async function signOut() {
    const previousToken = authState.token;
    clearSession();
    renderAuthState();

    if (previousToken) {
      try {
        await fetch(`${AUTH_ORIGIN}/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${previousToken}`,
          },
        });
      } catch {
        // The browser session is already cleared locally.
      }
    }

    notify("Signed out of Reserve Intel review.", "success");
  }

  async function handleAuthMessage(event) {
    if (event.origin !== AUTH_ORIGIN) return;
    if (loginPopup && event.source !== loginPopup) return;

    const payload = event.data;
    if (
      !payload ||
      payload.type !== "salty-dog-reserve-intel-auth" ||
      typeof payload.token !== "string" ||
      !payload.token
    ) {
      return;
    }

    try {
      const verified = await validateSession(payload.token);
      applySession({
        token: payload.token,
        login: verified.login,
        expiresAt: verified.expiresAt,
      });
      renderAuthState();
      notify(`Signed in as ${verified.login}.`, "success");
    } catch (error) {
      clearSession();
      renderAuthState();
      notify(error.message || "GitHub sign-in could not be verified.", "warning");
    }
  }

  async function authenticatedFetch(path, options = {}) {
    if (!authState.authenticated || !authState.token) {
      throw new Error("GitHub sign-in is required.");
    }

    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${authState.token}`);

    const response = await fetch(`${AUTH_ORIGIN}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      clearSession();
      renderAuthState();
    }

    return response;
  }

  window.reserveIntelAuth = {
    signIn,
    signOut,
    authenticatedFetch,
    isAuthenticated: () => authState.authenticated,
    getSessionToken: () => authState.token,
    getLogin: () => authState.login,
    getExpiresAt: () => authState.expiresAt,
  };

  ensureAuthControls();

  window.addEventListener("message", handleAuthMessage);

  byIdSafe("auth-sign-in-button")?.addEventListener("click", signIn);
  byIdSafe("auth-sign-out-button")?.addEventListener("click", signOut);
  byIdSafe("github-app-check-button")?.addEventListener("click", checkGitHubApp);

  renderAuthState();
  restoreSession();
})();
