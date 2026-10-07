/**
 * UI bearer auth integration (C1470): the review UI's live reads
 * (GET /status, GET /tasks/:id) carry a persisted bearer token, prompt for
 * one on 401, and diagnose 403 refusals — without ever echoing the token.
 *
 * These tests load the exact auth.js module the browser uses (via
 * createRequire, so the shared CommonJS module works under vitest's ESM),
 * plus text tripwires proving ui.js + both pages stay wired.
 */
import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";
// Bundled as text at transform time: file reads are unavailable in the
// workers test pool, so the wiring tripwires import the sources raw.
import uiSrc from "../ui/ui.js?raw";
import indexHtml from "../ui/index.html?raw";
import taskHtml from "../ui/task.html?raw";

const require = createRequire(import.meta.url);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const Auth: any = require("../ui/auth.js");

function memStorage(initial: Record<string, string> = {}) {
  const store: Record<string, string> = { ...initial };
  return {
    getItem: (k: string) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null),
    setItem: (k: string, v: string) => {
      store[k] = String(v);
    },
    removeItem: (k: string) => {
      delete store[k];
    },
  };
}

function blockedStorage() {
  const blocked = () => {
    throw new Error("storage blocked");
  };
  return { getItem: blocked, setItem: blocked, removeItem: blocked };
}

describe("token storage (localStorage or session fallback)", () => {
  it("normalizes: trims, rejects blank/non-string input", () => {
    expect(Auth.normalizeToken("  tok-1  ")).toBe("tok-1");
    expect(Auth.normalizeToken("")).toBeNull();
    expect(Auth.normalizeToken("   ")).toBeNull();
    expect(Auth.normalizeToken(null)).toBeNull();
    expect(Auth.normalizeToken(42)).toBeNull();
  });

  it("persists the trimmed token for reloads; blank input forgets it", () => {
    const s = memStorage();
    expect(Auth.setStoredToken(s, "  tok-2 ")).toEqual({ ok: true, token: "tok-2" });
    expect(Auth.getStoredToken(s)).toBe("tok-2");
    expect(Auth.setStoredToken(s, "   ")).toEqual({ ok: true, token: null });
    expect(Auth.getStoredToken(s)).toBeNull();
    expect(Auth.clearStoredToken(memStorage())).toBe(true);
  });

  it("tolerates blocked storage: reads null, writes keep the session token", () => {
    expect(Auth.getStoredToken(blockedStorage())).toBeNull();
    expect(Auth.setStoredToken(blockedStorage(), "tok-3")).toEqual({ ok: false, token: "tok-3" });
    expect(Auth.clearStoredToken(blockedStorage())).toBe(false);
  });
});

describe("Authorization headers on UI reads", () => {
  it("sends Bearer only when a token is set — never an empty header", () => {
    expect(Auth.authHeaders(null)).toEqual({});
    expect(Auth.authHeaders("")).toEqual({});
    expect(Auth.authHeaders("   ")).toEqual({});
    expect(Auth.authHeaders("tok-4")).toEqual({ Authorization: "Bearer tok-4" });
    expect(Auth.authHeaders("  tok-4 ")).toEqual({ Authorization: "Bearer tok-4" });
  });
});

describe("401 / 403 handling", () => {
  it("classifies 401/403 as auth failures and leaves outages alone", () => {
    expect(Auth.authFailureKind(401)).toBe("unauthorized");
    expect(Auth.authFailureKind(403)).toBe("forbidden");
    expect(Auth.authFailureKind(503)).toBeNull();
    expect(Auth.authFailureKind(200)).toBeNull();
    expect(Auth.isAuthFailure(401)).toBe(true);
    expect(Auth.isAuthFailure(403)).toBe(true);
    expect(Auth.isAuthFailure(503)).toBe(false);
  });

  it("httpError keeps the historical message shape with status + authKind", () => {
    const err401 = Auth.httpError(401, "/status");
    expect(err401.message).toMatch(/request failed: HTTP 401 for \/status/);
    expect(err401.status).toBe(401);
    expect(err401.authKind).toBe("unauthorized");
    const err403 = Auth.httpError(403, "/tasks/task-0001");
    expect(err403.message).toMatch(/request failed: HTTP 403 for \/tasks\/task-0001/);
    expect(err403.authKind).toBe("forbidden");
    const err503 = Auth.httpError(503, "/status");
    expect(err503.message).toMatch(/request failed: HTTP 503 for \/status/);
    expect(err503.authKind).toBeNull();
  });

  it("parses the server 403 owner diagnostic (never the token)", () => {
    expect(
      Auth.parseForbiddenOwner('{"error":"forbidden: this token belongs to alpha-0001, not beta-0002"}'),
    ).toEqual({ owner: "alpha-0001", expected: "beta-0002" });
    expect(Auth.parseForbiddenOwner('{"error":"unauthorized"}')).toBeNull();
    expect(Auth.parseForbiddenOwner(null)).toBeNull();
  });

  it("401 prompt asks for a token and never reads as clean", () => {
    const msg: string = Auth.describeUnauthorized("the status overview");
    expect(msg).toMatch(/401/);
    expect(msg).toMatch(/token/i);
    expect(msg).toMatch(/until the retry succeeds/i);
  });

  it("403 diagnostic names owner + expected with a concrete fix", () => {
    const msg: string = Auth.describeForbidden(
      '{"error":"forbidden: this token belongs to alpha-0001, not beta-0002"}',
      "task-0002",
    );
    expect(msg).toMatch(/403/);
    expect(msg).toMatch(/alpha-0001/);
    expect(msg).toMatch(/beta-0002/);
    expect(msg).toMatch(/admin token/i);
  });

  it("403 falls back to an actionable generic line for unparseable bodies", () => {
    const msg: string = Auth.describeForbidden("{}", "task-0009");
    expect(msg).toMatch(/403/);
    expect(msg).toMatch(/owning agent/i);
  });

  it("error text and diagnostics never echo a token", () => {
    const secret = "tok-xyz-secret";
    expect(Auth.httpError(401, "/status").message).not.toContain(secret);
    expect(Auth.describeForbidden(`{"error":"unauthorized: ${secret}"}`, "task-0001")).not.toContain(secret);
    expect(Auth.describeUnauthorized("x")).not.toContain("tok-");
  });
});

describe("auth UI state machine (clean updates on 401/403/success)", () => {
  it("starts clean with the session token", () => {
    expect(Auth.createAuthState("  tok-5 ").snapshot()).toEqual({
      token: "tok-5",
      needsToken: false,
      forbidden: null,
    });
  });

  it("setting a token retries cleanly: stores it and drops failure flags", () => {
    const a = Auth.createAuthState(null);
    a.markUnauthorized();
    a.setToken("tok-6");
    expect(a.snapshot()).toEqual({ token: "tok-6", needsToken: false, forbidden: null });
  });

  it("clearing the token raises the prompt", () => {
    const a = Auth.createAuthState("tok-7");
    a.clearToken();
    expect(a.snapshot()).toEqual({ token: null, needsToken: true, forbidden: null });
  });

  it("401 raises the prompt and drops stale refusal detail; 403 does the reverse", () => {
    const a = Auth.createAuthState("tok-8");
    a.markForbidden("old refusal");
    a.markUnauthorized();
    expect(a.snapshot()).toEqual({ token: "tok-8", needsToken: true, forbidden: null });
    a.markForbidden("refused for task-0002");
    expect(a.snapshot()).toEqual({ token: "tok-8", needsToken: false, forbidden: "refused for task-0002" });
    a.markOk();
    expect(a.snapshot()).toEqual({ token: "tok-8", needsToken: false, forbidden: null });
  });
});

describe("wiring tripwires: ui.js + both pages", () => {
  it("live reads carry the bearer header (fixtures stay bare)", () => {
    expect(uiSrc).toMatch(/window\.AgentBranchesAuth/);
    expect(uiSrc).toMatch(/Auth\.createAuthState\(/);
    expect(uiSrc).toMatch(/Auth\.authHeaders\(/);
    expect(uiSrc).toMatch(/FIXTURE \? \{\} :/);
  });

  it("401 prompts, 403 diagnoses, success clears — tokens never rendered or logged", () => {
    expect(uiSrc).toMatch(/authState\.markUnauthorized\(\)/);
    expect(uiSrc).toMatch(/authState\.markForbidden\(/);
    expect(uiSrc).toMatch(/authState\.markOk\(\)/);
    expect(uiSrc).toMatch(/Auth\.describeUnauthorized\(/);
    expect(uiSrc).toMatch(/Auth\.describeForbidden\(/);
    expect(uiSrc).toMatch(/initAuthUI/);
    expect(uiSrc).toMatch(/setAuthViews/);
    // The token storage key lives in auth.js alone; ui.js reaches storage
    // only through the Auth module (the pre-existing review-decision keys
    // keep their own localStorage use untouched).
    expect(uiSrc).not.toContain("agent-branches-auth-token");
    expect(uiSrc).not.toMatch(/innerHTML[^;]*token/i);
    expect(uiSrc).not.toMatch(/console\.log/);
  });

  it.each([
    ["index.html", indexHtml],
    ["task.html", taskHtml],
  ])(
    "%s ships the token form + refusal banner hidden and empty, loading auth.js first",
    (_page: string, html: string) => {
      expect(html).toMatch(/id="auth"/);
      expect(html).toMatch(/id="auth-form"/);
      expect(html).toMatch(/id="auth-token"[^>]*type="password"/);
      expect(html).toMatch(/id="auth-clear"/);
      expect(html).toMatch(/id="auth-forbidden"/);
      const authPos = html.indexOf('src="auth.js"');
      const uiPos = html.indexOf('src="ui.js"');
      expect(authPos).toBeGreaterThanOrEqual(0);
      expect(authPos).toBeLessThan(uiPos);
      expect(html).toMatch(/id="auth"[^>]*hidden/);
      expect(html).toMatch(/id="auth-prompt"[^>]*><\//);
      expect(html).toMatch(/id="auth-forbidden"[^>]*hidden/);
    },
  );
});
