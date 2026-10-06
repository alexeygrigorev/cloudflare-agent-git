/* Bearer-token auth helpers for the Agent Branches review UI (C1470).
   The read endpoints GET /status and GET /tasks/:id require a bearer token
   (C1462 Task 1): missing/invalid credentials come back 401 with
   { error: "unauthorized", message: "Missing or invalid bearer token" }, and
   a valid token for a DIFFERENT agent reading GET /tasks/:id comes back 403
   with { error: "forbidden: this token belongs to <owner>, not <expected>" }.
   No DOM, no fetch, no direct localStorage access — storage is injected, so
   node --test loads the exact module the browser uses. Tokens are never
   logged, echoed in errors, or rendered into the page. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else if (root) root.AgentBranchesAuth = api;
})(typeof self !== "undefined" ? self : this, function () {
  /* localStorage key for the persisted bearer token. The in-memory session
     copy in ui.js is authoritative at runtime; storage is only the reload
     carry-over (and may be blocked — callers always tolerate that). */
  var STORAGE_KEY = "agent-branches-auth-token";

  /* Trimmed token, or null when there is nothing usable. Non-strings and
     blank input are null — never an empty Authorization header. */
  function normalizeToken(raw) {
    if (typeof raw !== "string") return null;
    var token = raw.trim();
    return token ? token : null;
  }

  function safeGet(storage) {
    try {
      if (!storage || typeof storage.getItem !== "function") return null;
      return storage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  /* Read the persisted token (null when absent, blank or unreadable). */
  function getStoredToken(storage) {
    return normalizeToken(safeGet(storage));
  }

  /* Persist (or forget when blank) the token. Always returns the normalized
     token for the in-memory session copy; `ok` reports whether the storage
     write itself succeeded. */
  function setStoredToken(storage, raw) {
    var token = normalizeToken(raw);
    try {
      if (!storage || typeof storage.setItem !== "function" || typeof storage.removeItem !== "function") {
        return { ok: false, token: token };
      }
      if (token === null) storage.removeItem(STORAGE_KEY);
      else storage.setItem(STORAGE_KEY, token);
      return { ok: true, token: token };
    } catch (e) {
      return { ok: false, token: token };
    }
  }

  /* Forget the persisted token. True when storage cooperated. */
  function clearStoredToken(storage) {
    try {
      if (!storage || typeof storage.removeItem !== "function") return false;
      storage.removeItem(STORAGE_KEY);
      return true;
    } catch (e) {
      return false;
    }
  }

  /* Headers to send with an authenticated read. Empty object when there is
     no token — callers must not send `Authorization: Bearer ` with nothing
     after it. Fixture-mode (static-file) reads never call this. */
  function authHeaders(token) {
    var normalized = normalizeToken(token);
    if (normalized === null) return {};
    return { Authorization: "Bearer " + normalized };
  }

  /* Classify an HTTP status for the auth UI. Only 401/403 are auth
     failures; everything else (including 503 outages) is null so the
     existing stale-error path keeps owning it. */
  function authFailureKind(status) {
    if (status === 401) return "unauthorized";
    if (status === 403) return "forbidden";
    return null;
  }

  function isAuthFailure(status) {
    return authFailureKind(status) !== null;
  }

  /* Error for a failed fetch with the historical message shape
     ("request failed: HTTP <status> for <url>") plus machine-readable
     `status` and `authKind` fields for the 401/403 branches. The message
     never carries the token or the response body. */
  function httpError(status, url) {
    var err = new Error("request failed: HTTP " + status + " for " + url);
    err.status = status;
    err.authKind = authFailureKind(status);
    return err;
  }

  /* Pull { owner, expected } out of the server's 403 body
     ("forbidden: this token belongs to <owner>, not <expected>"), or null
     when the body says anything else. The body may be the raw JSON envelope,
     so trailing quote/brace characters are stripped from the capture. Never
     touches tokens. */
  function parseForbiddenOwner(errorText) {
    if (typeof errorText !== "string" || !errorText) return null;
    var m = /this token belongs to\s+(.+?),\s*not\s+(.+?)\s*["}]?\s*$/.exec(errorText);
    if (!m) return null;
    var owner = m[1].replace(/["}]+$/, "");
    var expected = m[2].replace(/["}]+$/, "");
    if (!owner || !expected) return null;
    return { owner: owner, expected: expected };
  }

  /* Fixed prompt shown on 401: what happened, what to do, what NOT to do
     (no token is ever echoed back). `scope` names the view ("status" or
     "task <id>") so the banner reads concretely on both pages. */
  function describeUnauthorized(scope) {
    var where = scope ? String(scope) : "this view";
    return (
      "Authentication is required to load " + where + " (the server answered 401 Unauthorized). " +
      "Enter a bearer token below — an admin token or the owning agent's task token — " +
      "and the page will retry automatically. Nothing here is shown as clean until the retry succeeds."
    );
  }

  /* Fixed diagnostic shown on 403: which credential was presented (by owner
     name only, never the token), what it cannot read, and the concrete fix.
     Falls back to a generic-but-actionable line for unparseable bodies. */
  function describeForbidden(errorText, taskId) {
    var parsed = parseForbiddenOwner(errorText);
    var target = taskId ? "task " + taskId : "this task";
    if (parsed) {
      return (
        "Access was refused for " + target + " (the server answered 403 Forbidden): " +
        "the entered token belongs to " + parsed.owner + ", not " + parsed.expected + ". " +
        "A valid token for a different agent never unlocks another agent's task — " +
        "enter the admin token or " + parsed.expected + "'s own task token instead."
      );
    }
    return (
      "Access was refused for " + target + " (the server answered 403 Forbidden). " +
      "The entered token is valid but does not unlock this task — " +
      "enter the admin token or the owning agent's own task token instead."
    );
  }

  /* Small state machine for the auth UI so 401/403 transitions update one
     place cleanly: setting a token always clears the failure flags (the
     next fetch is a fresh attempt); markOk clears both flags; 401 raises
     needsToken and drops any stale forbidden detail; 403 records the
     diagnostic detail and drops the token prompt. */
  function createAuthState(initialToken) {
    var state = {
      token: normalizeToken(initialToken),
      needsToken: false,
      forbidden: null,
    };
    return {
      snapshot: function () {
        return { token: state.token, needsToken: state.needsToken, forbidden: state.forbidden };
      },
      hasToken: function () {
        return state.token !== null;
      },
      setToken: function (raw) {
        state.token = normalizeToken(raw);
        state.needsToken = false;
        state.forbidden = null;
        return this.snapshot();
      },
      clearToken: function () {
        state.token = null;
        state.needsToken = true;
        state.forbidden = null;
        return this.snapshot();
      },
      markUnauthorized: function () {
        state.needsToken = true;
        state.forbidden = null;
        return this.snapshot();
      },
      markForbidden: function (detail) {
        state.needsToken = false;
        state.forbidden = typeof detail === "string" && detail ? detail : "forbidden";
        return this.snapshot();
      },
      markOk: function () {
        state.needsToken = false;
        state.forbidden = null;
        return this.snapshot();
      },
    };
  }

  return {
    STORAGE_KEY: STORAGE_KEY,
    normalizeToken: normalizeToken,
    getStoredToken: getStoredToken,
    setStoredToken: setStoredToken,
    clearStoredToken: clearStoredToken,
    authHeaders: authHeaders,
    authFailureKind: authFailureKind,
    isAuthFailure: isAuthFailure,
    httpError: httpError,
    parseForbiddenOwner: parseForbiddenOwner,
    describeUnauthorized: describeUnauthorized,
    describeForbidden: describeForbidden,
    createAuthState: createAuthState,
  };
});
