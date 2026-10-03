/* Tests for the bearer-token auth helpers (auth.js, C1470): token
   normalization, localStorage persistence (with blocked-storage tolerance),
   Authorization header building, 401/403 classification, the server's 403
   owner diagnostic, and the auth UI state machine. Run with:
     cd prototype/ui && node --test        (or: npm test)
   No dependencies: node:test + assert only; the test loads the exact module
   the browser uses. The last tests are tripwires on ui.js and the two pages:
   live reads must carry the bearer header, 401 must raise the token prompt,
   403 must raise the refusal diagnostic, and tokens must never be echoed. */
"use strict";

var test = require("node:test");
var assert = require("node:assert/strict");
var fs = require("node:fs");
var path = require("node:path");
var Auth = require("../auth.js");

function memStorage(initial) {
  var store = Object.assign({}, initial);
  return {
    getItem: function (k) {
      return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null;
    },
    setItem: function (k, v) {
      store[k] = String(v);
    },
    removeItem: function (k) {
      delete store[k];
    },
    _store: store,
  };
}

function blockedStorage() {
  function blocked() {
    throw new Error("storage blocked");
  }
  return { getItem: blocked, setItem: blocked, removeItem: blocked };
}

/* ---------- token normalization ---------- */

test("normalizeToken trims and rejects blank/non-string input", function () {
  assert.equal(Auth.normalizeToken("  abc123  "), "abc123");
  assert.equal(Auth.normalizeToken("abc123"), "abc123");
  assert.equal(Auth.normalizeToken(""), null);
  assert.equal(Auth.normalizeToken("   "), null);
  assert.equal(Auth.normalizeToken(null), null);
  assert.equal(Auth.normalizeToken(undefined), null);
  assert.equal(Auth.normalizeToken(42), null);
  assert.equal(Auth.normalizeToken({}), null);
});

/* ---------- storage persistence ---------- */

test("getStoredToken reads the persisted token and tolerates absence", function () {
  var s = memStorage({});
  assert.equal(Auth.getStoredToken(s), null);
  s.setItem(Auth.STORAGE_KEY, "  tok-1 ");
  assert.equal(Auth.getStoredToken(s), "tok-1");
});

test("getStoredToken returns null when storage is blocked or missing", function () {
  assert.equal(Auth.getStoredToken(blockedStorage()), null);
  assert.equal(Auth.getStoredToken(null), null);
  assert.equal(Auth.getStoredToken({}), null);
});

test("setStoredToken persists the trimmed token for reloads", function () {
  var s = memStorage({});
  var res = Auth.setStoredToken(s, "  tok-2 ");
  assert.deepEqual(res, { ok: true, token: "tok-2" });
  assert.equal(Auth.getStoredToken(s), "tok-2");
});

test("setStoredToken with a blank token forgets the persisted one", function () {
  var s = memStorage({});
  Auth.setStoredToken(s, "tok-3");
  var res = Auth.setStoredToken(s, "   ");
  assert.deepEqual(res, { ok: true, token: null });
  assert.equal(Auth.getStoredToken(s), null);
});

test("setStoredToken still returns the session token when storage is blocked", function () {
  var res = Auth.setStoredToken(blockedStorage(), "tok-4");
  assert.deepEqual(res, { ok: false, token: "tok-4" });
});

test("clearStoredToken forgets the token and reports storage health", function () {
  var s = memStorage({});
  Auth.setStoredToken(s, "tok-5");
  assert.equal(Auth.clearStoredToken(s), true);
  assert.equal(Auth.getStoredToken(s), null);
  assert.equal(Auth.clearStoredToken(blockedStorage()), false);
});

/* ---------- Authorization headers ---------- */

test("authHeaders sends Bearer only when a token is set", function () {
  assert.deepEqual(Auth.authHeaders(null), {});
  assert.deepEqual(Auth.authHeaders(""), {});
  assert.deepEqual(Auth.authHeaders("   "), {});
  assert.deepEqual(Auth.authHeaders("tok-6"), { Authorization: "Bearer tok-6" });
  assert.deepEqual(Auth.authHeaders("  tok-6 "), { Authorization: "Bearer tok-6" });
});

test("authHeaders never emits an empty Bearer value", function () {
  Object.values(Auth.authHeaders("")).forEach(function (v) {
    assert.notEqual(v, "Bearer ");
  });
  assert.deepEqual(Object.keys(Auth.authHeaders(null)).length, 0);
});

/* ---------- 401/403 classification ---------- */

test("authFailureKind classifies 401/403 and leaves other statuses alone", function () {
  assert.equal(Auth.authFailureKind(401), "unauthorized");
  assert.equal(Auth.authFailureKind(403), "forbidden");
  assert.equal(Auth.authFailureKind(200), null);
  assert.equal(Auth.authFailureKind(404), null);
  assert.equal(Auth.authFailureKind(500), null);
  assert.equal(Auth.authFailureKind(503), null);
  assert.equal(Auth.isAuthFailure(401), true);
  assert.equal(Auth.isAuthFailure(403), true);
  assert.equal(Auth.isAuthFailure(503), false);
});

test("httpError keeps the historical message shape with status + authKind", function () {
  var err401 = Auth.httpError(401, "/status");
  assert.match(err401.message, /request failed: HTTP 401 for \/status/);
  assert.equal(err401.status, 401);
  assert.equal(err401.authKind, "unauthorized");

  var err403 = Auth.httpError(403, "/tasks/task-0001");
  assert.match(err403.message, /request failed: HTTP 403 for \/tasks\/task-0001/);
  assert.equal(err403.status, 403);
  assert.equal(err403.authKind, "forbidden");

  var err503 = Auth.httpError(503, "/status");
  assert.match(err503.message, /request failed: HTTP 503 for \/status/);
  assert.equal(err503.authKind, null);
});

test("httpError messages never carry a token", function () {
  ["tok-secret", "Bearer tok-secret"].forEach(function (secret) {
    [401, 403].forEach(function (status) {
      assert.equal(Auth.httpError(status, "/status").message.indexOf(secret), -1);
    });
  });
});

/* ---------- 403 owner diagnostic ---------- */

test("parseForbiddenOwner names the token owner and the expected agent", function () {
  assert.deepEqual(
    Auth.parseForbiddenOwner('{"error":"forbidden: this token belongs to alpha-0001, not beta-0002"}'),
    { owner: "alpha-0001", expected: "beta-0002" }
  );
  assert.deepEqual(
    Auth.parseForbiddenOwner("forbidden: this token belongs to a, not b"),
    { owner: "a", expected: "b" }
  );
});

test("parseForbiddenOwner is null for anything else", function () {
  assert.equal(Auth.parseForbiddenOwner('{"error":"unauthorized"}'), null);
  assert.equal(Auth.parseForbiddenOwner(""), null);
  assert.equal(Auth.parseForbiddenOwner(null), null);
  assert.equal(Auth.parseForbiddenOwner("forbidden"), null);
});

test("describeUnauthorized prompts for a token and never reads as clean", function () {
  var msg = Auth.describeUnauthorized("the status overview");
  assert.match(msg, /401/);
  assert.match(msg, /token/i);
  assert.match(msg, /never.*clean|not.*clean|until the retry succeeds/i);
  assert.equal(msg.indexOf("tok-"), -1);
});

test("describeForbidden names owner + expected with a concrete fix", function () {
  var msg = Auth.describeForbidden(
    '{"error":"forbidden: this token belongs to alpha-0001, not beta-0002"}',
    "task-0002"
  );
  assert.match(msg, /403/);
  assert.match(msg, /alpha-0001/);
  assert.match(msg, /beta-0002/);
  assert.match(msg, /admin token/i);
});

test("describeForbidden falls back to an actionable generic line", function () {
  var msg = Auth.describeForbidden("{}", "task-0009");
  assert.match(msg, /403/);
  assert.match(msg, /task-0009/);
  assert.match(msg, /owning agent/i);
});

test("forbidden diagnostics never echo a token", function () {
  var secret = "tok-xyz-secret";
  var msg = Auth.describeForbidden('{"error":"unauthorized: ' + secret + '"}', "task-0001");
  assert.equal(msg.indexOf(secret), -1);
});

/* ---------- auth UI state machine ---------- */

test("createAuthState starts clean with the session token", function () {
  var snap = Auth.createAuthState("  tok-7 ").snapshot();
  assert.deepEqual(snap, { token: "tok-7", needsToken: false, forbidden: null });
  assert.deepEqual(Auth.createAuthState(null).snapshot(), { token: null, needsToken: false, forbidden: null });
  assert.equal(Auth.createAuthState("tok-7").hasToken(), true);
  assert.equal(Auth.createAuthState("").hasToken(), false);
});

test("setToken retries cleanly: stores the token and drops failure flags", function () {
  var a = Auth.createAuthState(null);
  a.markUnauthorized();
  a.setToken("tok-8");
  assert.deepEqual(a.snapshot(), { token: "tok-8", needsToken: false, forbidden: null });
});

test("clearToken forgets the token and raises the prompt", function () {
  var a = Auth.createAuthState("tok-9");
  a.clearToken();
  assert.deepEqual(a.snapshot(), { token: null, needsToken: true, forbidden: null });
});

test("markUnauthorized raises the prompt and drops stale refusal detail", function () {
  var a = Auth.createAuthState("tok-10");
  a.markForbidden("old refusal");
  a.markUnauthorized();
  assert.deepEqual(a.snapshot(), { token: "tok-10", needsToken: true, forbidden: null });
});

test("markForbidden records the diagnostic and drops the token prompt", function () {
  var a = Auth.createAuthState("tok-11");
  a.markUnauthorized();
  a.markForbidden("refused for task-0002");
  assert.deepEqual(a.snapshot(), { token: "tok-11", needsToken: false, forbidden: "refused for task-0002" });
});

test("markForbidden defaults an empty detail and markOk clears everything", function () {
  var a = Auth.createAuthState("tok-12");
  a.markForbidden("");
  assert.equal(a.snapshot().forbidden, "forbidden");
  a.markOk();
  assert.deepEqual(a.snapshot(), { token: "tok-12", needsToken: false, forbidden: null });
});

/* ---------- tripwire on ui.js itself (C1470) ---------- */

test("ui.js sends the bearer header on live reads and never on fixtures", function () {
  var src = fs.readFileSync(path.join(__dirname, "..", "ui.js"), "utf8");
  assert.match(src, /window\.AgentBranchesAuth/, "ui.js loads the auth module");
  assert.match(src, /Auth\.createAuthState\(/, "session auth state exists");
  assert.match(src, /Auth\.authHeaders\(/, "reads carry the Authorization header");
  assert.match(src, /FIXTURE \? \{\} :/, "fixture reads stay bare");
});

test("ui.js prompts for a token on 401 and diagnoses 403 without echoing tokens", function () {
  var src = fs.readFileSync(path.join(__dirname, "..", "ui.js"), "utf8");
  assert.match(src, /authState\.markUnauthorized\(\)/, "401 raises the token prompt");
  assert.match(src, /authState\.markForbidden\(/, "403 raises the refusal diagnostic");
  assert.match(src, /authState\.markOk\(\)/, "success clears the auth failure flags");
  assert.match(src, /Auth\.describeUnauthorized\(/, "401 prompt text is shown");
  assert.match(src, /Auth\.describeForbidden\(/, "403 diagnostic text is shown");
  assert.match(src, /initAuthUI/, "token form is wired");
  assert.match(src, /setAuthViews/, "auth banners are rendered");
  /* The token travels only as an Authorization header and a password input
     value: never into innerHTML, never logged, and never stored outside the
     Auth module (the storage key lives in auth.js alone — ui.js reaches
     storage only through Auth; the pre-existing review-decision keys keep
     their own localStorage use untouched). */
  assert.equal(src.indexOf("agent-branches-auth-token"), -1, "ui.js never touches the token storage key directly");
  assert.doesNotMatch(src, /innerHTML[^;]*token/i, "no token is rendered as HTML");
  assert.doesNotMatch(src, /console\.log/i, "no logging that could leak a token");
});

test("both pages ship the token form + refusal banner hidden and empty, loading auth.js first", function () {
  ["index.html", "task.html"].forEach(function (page) {
    var html = fs.readFileSync(path.join(__dirname, "..", page), "utf8");
    assert.match(html, /id="auth"/, page + " has the token section");
    assert.match(html, /id="auth-form"/, page + " has the token form");
    assert.match(html, /id="auth-token"[^>]*type="password"/, page + " masks token entry");
    assert.match(html, /id="auth-clear"/, page + " can clear the token");
    assert.match(html, /id="auth-forbidden"/, page + " has the refusal banner");
    var authPos = html.indexOf('src="auth.js"');
    var uiPos = html.indexOf('src="ui.js"');
    assert.notEqual(authPos, -1, page + " loads auth.js");
    assert.ok(authPos < uiPos, page + " loads auth.js before ui.js");
    /* Hidden and empty at first paint: identical with or without JS. */
    assert.match(html, /id="auth"[^>]*hidden/, page + " token section starts hidden");
    assert.match(html, /id="auth-prompt"[^>]*><\//, page + " prompt starts empty");
    assert.match(html, /id="auth-forbidden"[^>]*hidden/, page + " refusal banner starts hidden");
  });
});
