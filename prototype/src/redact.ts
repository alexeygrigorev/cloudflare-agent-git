/**
 * PLAN-L1-REAL §3/§5.2/§5.6 — logging redaction. Anything that could contain
 * a credential reaches a log/emergency sink ONLY through redact()/logSafe();
 * the deploy-prep test suite proves no Authorization header or token shape
 * survives it. The worker currently logs nothing on the happy path; when a
 * sink is added, it MUST go through here (recorded in DEPLOY.md).
 */

export const REDACTED = "[REDACTED]";

/**
 * Artifacts repo-token shape, generalized from the artifacts-spike: the docs
 * claimed `art_v1_…` but the real service issues `art_v2_x_<40hex>` with an
 * optional `?expires=<unix>` suffix (CONTRACT 0.1.3, finding 1). The pattern
 * is deliberately version-agnostic so a future `art_v3_…` still matches.
 */
const ARTIFACTS_TOKEN_PATTERN = /\bart_[A-Za-z0-9_-]*\d[A-Za-z0-9_-]*_[0-9a-f]{8,}(?:\?expires=\d+)?\b/g;

/** `authorization: Bearer <token>` (any scheme/casing, JSON-ish quotes tolerated). */
const AUTHORIZATION_HEADER_PATTERN =
  /(authorization["']?\s*:\s*)(["']?)([A-Za-z][A-Za-z0-9_-]*\s+)?([A-Za-z0-9._~+/=-]{8,})/gi;

/** Standalone `Bearer <token>` (e.g. inside a JSON string value). */
const BEARER_PATTERN = /(\bbearer["'\s]+)([A-Za-z0-9._~+/=-]{8,})/gi;

/**
 * §5.6: remote URLs embed the account id — semi-public, redact the host in
 * evidence/logs to `<account>`.
 */
const ACCOUNT_URL_PATTERN = /https:\/\/[0-9a-f]{32}\.artifacts\.cloudflare\.net/g;

/**
 * Replace every credential-looking substring with REDACTED. `extraSecrets`
 * are exact values shared secrets (ADMIN_TOKEN, RUNNER_TOKEN, …) that carry
 * no guessable shape; shorter than 8 chars is never treated as a secret.
 */
export function redact(text: string, extraSecrets: ReadonlyArray<string> = []): string {
  let out = text;
  for (const secret of extraSecrets) {
    if (secret.length >= 8 && out.includes(secret)) {
      // split/join: no RegExp-escaping of arbitrary secret values
      out = out.split(secret).join(REDACTED);
    }
  }
  return out
    .replace(ARTIFACTS_TOKEN_PATTERN, REDACTED)
    .replace(AUTHORIZATION_HEADER_PATTERN, `$1$2$3${REDACTED}`)
    .replace(BEARER_PATTERN, `$1${REDACTED}`)
    .replace(ACCOUNT_URL_PATTERN, "https://<account>.artifacts.cloudflare.net");
}

/**
 * The only sanctioned console sink in the Worker: stringifies the parts,
 * redacts, emits ONE line. Callers pass every configured shared secret so
 * shapeless tokens are covered too (env values, never literals).
 */
export function logSafe(extraSecrets: ReadonlyArray<string>, ...parts: unknown[]): void {
  const line = parts
    .map((part) => (typeof part === "string" ? part : JSON.stringify(part)))
    .join(" ");
  console.error(redact(line, extraSecrets));
}
