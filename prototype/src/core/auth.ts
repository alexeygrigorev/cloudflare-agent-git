/**
 * Authentication decisions (facade extraction, 2026-10-03): pure,
 * provider-neutral, HTTP-free. Adapters present bearer tokens and config;
 * the core decides. Every decision mirrors the pre-facade route behavior
 * (CONTRACT 0.1.1/0.1.2): fail closed on unconfigured secrets, hash both
 * sides before comparing (token length is not observable), never log or
 * echo tokens, and a VALID token for a DIFFERENT agent is 403, not 401.
 */

/** SHA-256 of a string as lowercase hex (token digests; never the token itself). */
export async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Constant-time compare; callers pass equal-length hex digests. */
export function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * muse-r46 nit + AUTH: compare SHA-256 digests, not raw strings, so token
 * LENGTH is not observable through timing either. Never logs either side.
 */
export async function tokensMatch(presented: string, expected: string): Promise<boolean> {
  return timingSafeEqual(await sha256Hex(presented), await sha256Hex(expected));
}

/** Bearer credentials a runtime may configure (env names kept for parity). */
export interface AuthTokens {
  /** ADMIN_TOKEN — full control (setup, task creation, any agent route). */
  admin?: string;
  /** RUNNER_TOKEN — trusted runner submissions (POST /checks). */
  runner?: string;
  /** LOCAL_ARTIFACTS_TOKEN — webhook/subscription ingest bearer. */
  sidecar?: string;
}

/** Failure bodies carry `error`; reads additionally carry a fixed `message` (C1462 Task 1). */
export type AuthDecision =
  | { ok: true }
  | { ok: false; status: 401 | 403 | 503; error: string; message?: string };

export function bearerFrom(headerValue: string | null): string | null {
  if (!headerValue || !headerValue.toLowerCase().startsWith("bearer ")) {
    return null;
  }
  return headerValue.slice(7).trim();
}

/**
 * Codex C-1305 #3: mutating/authenticated routes require a bearer token.
 * Fail closed when the secret is not configured. Error bodies never
 * include the presented token and tokens are never logged.
 */
export async function decideBearer(
  presented: string | null,
  expected: string | undefined,
  envName: "ADMIN_TOKEN" | "RUNNER_TOKEN",
): Promise<AuthDecision> {
  if (!expected) {
    return { ok: false, status: 503, error: `${envName} is not configured; refusing authenticated request (fail closed)` };
  }
  if (presented === null || !(await tokensMatch(presented, expected))) {
    return { ok: false, status: 401, error: `unauthorized: valid bearer token required (${envName})` };
  }
  return { ok: true };
}

export interface MutatingAuthOptions {
  /** Expected owning agent; undefined = any agent credential is accepted. */
  agent?: string | null;
  /** Whether the shared webhook bearer (sidecar) is acceptable here. */
  allowSidecar?: boolean;
}

/**
 * muse-r46 AUTH (CONTRACT 0.1.1): every mutating route is authenticated.
 * Accepted credentials: ADMIN_TOKEN; the relevant agent's per-task token
 * (the write token minted at task creation, verified by digest via
 * `credentialAgent`); and, where allowed, the webhook shared bearer. A
 * VALID token for a DIFFERENT agent is 403 (cross-agent writes rejected);
 * everything else is 401. Error bodies never echo the presented token.
 */
export async function decideMutatingAuth(
  presented: string | null,
  tokens: AuthTokens,
  opts: MutatingAuthOptions,
  credentialAgent: (presented: string) => Promise<string | null>,
): Promise<AuthDecision> {
  if (presented === null) {
    return { ok: false, status: 401, error: "unauthorized: bearer token required" };
  }
  if (tokens.admin && (await tokensMatch(presented, tokens.admin))) {
    return { ok: true };
  }
  if (opts.allowSidecar && tokens.sidecar && (await tokensMatch(presented, tokens.sidecar))) {
    return { ok: true };
  }
  const owner = await credentialAgent(presented);
  if (owner !== null) {
    if (opts.agent === undefined || owner === opts.agent) {
      return { ok: true };
    }
    return { ok: false, status: 403, error: `forbidden: this token belongs to ${owner}, not ${opts.agent}` };
  }
  return { ok: false, status: 401, error: "unauthorized: ADMIN_TOKEN, the agent's task token or the sidecar bearer required" };
}

/** Shared read-route 401 body (C1462 Task 1): identical for every flavor of
 * missing/invalid credential so callers cannot distinguish failure causes. */
export const READ_AUTH_UNAUTHORIZED = {
  error: "unauthorized",
  message: "Missing or invalid bearer token",
} as const;

export interface ReadAuthOptions {
  /** Ownership narrowing for GET /tasks/:id: only this agent (or admin) may
   * read; a valid token for a DIFFERENT agent stays 403 per CONTRACT.
   * Undefined = no narrowing (GET /status). */
  agent?: string;
}

/**
 * C1462 Task 1: read endpoints are authenticated too. Accepted credentials:
 * ADMIN_TOKEN; RUNNER_TOKEN on unnarrowed reads only (the runner fetches
 * /status for its heads vector before POST /checks); and any valid per-task
 * agent token — credentialAgent already denies revoked and expired tokens
 * (at the expiry instant) and unparsable expiry, so those gates apply to
 * reads exactly as to writes. Everything else — anonymous, non-bearer or
 * malformed header, unknown/garbage/expired/revoked token — is the shared
 * 401 above. The sidecar webhook bearer is ingest-only and is NOT a read
 * credential. Unconfigured admin does not fail reads closed with 503: an
 * unauthenticated caller gets 401 without learning whether secrets exist.
 */
export async function decideReadAuth(
  presented: string | null,
  tokens: AuthTokens,
  opts: ReadAuthOptions,
  credentialAgent: (presented: string) => Promise<string | null>,
): Promise<AuthDecision> {
  if (presented === null) {
    return { ok: false, status: 401, ...READ_AUTH_UNAUTHORIZED };
  }
  if (tokens.admin && (await tokensMatch(presented, tokens.admin))) {
    return { ok: true };
  }
  if (opts.agent === undefined && tokens.runner && (await tokensMatch(presented, tokens.runner))) {
    return { ok: true };
  }
  const owner = await credentialAgent(presented);
  if (owner === null) {
    return { ok: false, status: 401, ...READ_AUTH_UNAUTHORIZED };
  }
  if (opts.agent === undefined || owner === opts.agent) {
    return { ok: true };
  }
  return { ok: false, status: 403, error: `forbidden: this token belongs to ${owner}, not ${opts.agent}` };
}
