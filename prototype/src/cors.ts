/**
 * PLAN-L1-REAL §5.7 — CORS policy, required before any public deploy.
 *
 * - Allowed origins: explicit per-environment allowlist from the plain env
 *   var ALLOWED_ORIGINS (comma-separated exact origins). No wildcard, no
 *   reflecting arbitrary Origins; an unset/empty var allows NO browser origin
 *   (fail closed).
 * - Preflight: OPTIONS is answered with the matched allowlisted origin only,
 *   methods limited to the routes' methods, and the Authorization/Content-Type
 *   header allowlist.
 * - Credentials: auth is via Authorization headers, never cookies, so
 *   Access-Control-Allow-Credentials stays false — a browser client can
 *   never become a token-exfiltration path.
 *
 * CORS is irrelevant to non-browser agents and to the server-to-server
 * /events/* ingest, which authenticate per CONTRACT (§5.1).
 */

export interface CorsPolicy {
  allowedOrigins: readonly string[];
}

export function corsPolicyFromEnv(rawAllowedOrigins: string | undefined): CorsPolicy {
  const allowedOrigins = (rawAllowedOrigins ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter((origin) => origin.length > 0);
  return { allowedOrigins };
}

/** Exact match: scheme+host+port must equal an allowlist entry (no wildcards). */
export function matchOrigin(policy: CorsPolicy, origin: string | null): string | null {
  if (!origin) {
    return null;
  }
  return policy.allowedOrigins.includes(origin) ? origin : null;
}

/** Headers for any response to an allowlisted request origin (Vary always). */
export function corsHeaders(origin: string | null): Record<string, string> {
  const headers: Record<string, string> = { vary: "Origin" };
  if (origin) {
    headers["access-control-allow-origin"] = origin;
    // Must stay false (§5.7); set explicitly so the policy is observable.
    headers["access-control-allow-credentials"] = "false";
  }
  return headers;
}

/** Methods the coordinator routes actually use — nothing broader. */
const ALLOWED_METHODS = "GET, POST";
const ALLOWED_HEADERS = "Authorization, Content-Type";

/**
 * Answer a preflight. 204 with the CORS headers for an allowlisted origin;
 * 403 WITHOUT any Access-Control-* grant otherwise (the browser blocks).
 */
export function preflightResponse(policy: CorsPolicy, request: Request): Response {
  const origin = matchOrigin(policy, request.headers.get("origin"));
  if (!origin) {
    return new Response(JSON.stringify({ error: "origin not allowed" }), {
      status: 403,
      headers: { "content-type": "application/json", vary: "Origin" },
    });
  }
  return new Response(null, {
    status: 204,
    headers: {
      ...corsHeaders(origin),
      "access-control-allow-methods": ALLOWED_METHODS,
      "access-control-allow-headers": ALLOWED_HEADERS,
      "access-control-max-age": "600",
    },
  });
}

/** Attach the CORS grants to a real (non-preflight) response when allowed. */
export function corsify(policy: CorsPolicy, request: Request, response: Response): Response {
  const origin = matchOrigin(policy, request.headers.get("origin"));
  if (!origin) {
    return response;
  }
  const headers = new Headers(response.headers);
  for (const [name, value] of Object.entries(corsHeaders(origin))) {
    headers.set(name, value);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
