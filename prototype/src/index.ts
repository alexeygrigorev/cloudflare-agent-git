import type { ArtifactsNamespaceBinding } from "./artifacts/real.js";
import { corsPolicyFromEnv, corsify, preflightResponse } from "./cors.js";
import { Coordinator, sha256Hex, timingSafeEqual } from "./coordinator.js";
import { parseChecksPayload, type NormalizedChecksPayload } from "./checks-wire.js";
import { logSafe } from "./redact.js";
import { parseArtifactsPushedEvent } from "./types.js";
import {
  WEBHOOK_SIGNATURE_HEADER,
  WEBHOOK_TIMESTAMP_HEADER,
  verifyWebhookSignature,
} from "./webhook.js";

export { Coordinator } from "./coordinator.js";

declare global {
  interface Env {
    ARTIFACTS?: ArtifactsNamespaceBinding;
    RADAR_IMPL?: string;
    ADMIN_TOKEN?: string;
    RUNNER_TOKEN?: string;
    LOCAL_ARTIFACTS_URL?: string;
    LOCAL_ARTIFACTS_TOKEN?: string;
    /** §5.7 CORS allowlist: comma-separated exact origins; empty = none. */
    ALLOWED_ORIGINS?: string;
    /** §5.8 namespace isolation: /events/artifacts rejects other namespaces. */
    ARTIFACTS_NAMESPACE?: string;
    /** §5.4 per-principal requests/minute; "0" disables; unset = default. */
    RATE_LIMIT_PER_MINUTE?: string;
    /** §5.1 webhook authenticity: when set, /events/* require HMAC signature. */
    EVENTS_WEBHOOK_SECRET?: string;
  }
}

declare module "cloudflare:workers" {
  namespace Cloudflare {
    interface Env {
      COORDINATOR: DurableObjectNamespace<Coordinator>;
      ARTIFACTS?: ArtifactsNamespaceBinding;
      RADAR_IMPL?: string;
      ADMIN_TOKEN?: string;
      RUNNER_TOKEN?: string;
      LOCAL_ARTIFACTS_URL?: string;
      LOCAL_ARTIFACTS_TOKEN?: string;
      ALLOWED_ORIGINS?: string;
      ARTIFACTS_NAMESPACE?: string;
      RATE_LIMIT_PER_MINUTE?: string;
      EVENTS_WEBHOOK_SECRET?: string;
    }
  }
}

export interface FetchHandler {
  fetch(request: Request, env: Env): Promise<Response>;
}

function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

async function readJson(request: Request): Promise<Record<string, unknown>> {
  try {
    return (await request.json()) as Record<string, unknown>;
  } catch {
    throw new Error("request body must be valid JSON");
  }
}

function parseJsonText(raw: string): Record<string, unknown> {
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    throw new Error("request body must be valid JSON");
  }
}

function coordinator(env: Env): DurableObjectStub<Coordinator> {
  return env.COORDINATOR.get(env.COORDINATOR.idFromName("global"));
}

/**
 * muse-r46 nit + AUTH: compare SHA-256 digests, not raw strings, so token
 * LENGTH is not observable through timing either. Never logs either side.
 */
async function tokensMatch(presented: string, expected: string): Promise<boolean> {
  return timingSafeEqual(await sha256Hex(presented), await sha256Hex(expected));
}

function bearerToken(request: Request): string | null {
  const header = request.headers.get("authorization");
  if (!header || !header.toLowerCase().startsWith("bearer ")) {
    return null;
  }
  return header.slice(7).trim();
}

/**
 * Codex C-1305 #3: mutating/authenticated routes require a bearer token from
 * env. Fail closed when the env secret is not configured. Error bodies never
 * include the presented token and tokens are never logged.
 */
function requireBearer(
  request: Request,
  expected: string | undefined,
  envName: "ADMIN_TOKEN" | "RUNNER_TOKEN",
): Promise<Response | null> {
  if (!expected) {
    return Promise.resolve(
      json({ error: `${envName} is not configured; refusing authenticated request (fail closed)` }, 503),
    );
  }
  return (async () => {
    const presented = bearerToken(request);
    if (presented === null || !(await tokensMatch(presented, expected))) {
      return json({ error: `unauthorized: valid bearer token required (${envName})` }, 401);
    }
    return null;
  })();
}

/**
 * muse-r46 AUTH (CONTRACT 0.1.1): every mutating route is authenticated.
 * Accepted credentials: ADMIN_TOKEN; the relevant agent's per-task token
 * (the write token minted at task creation, verified by digest in the DO);
 * and for the webhook ingest routes (`/events/*`) the sidecar shared bearer
 * (`LOCAL_ARTIFACTS_TOKEN`), which is what the post-receive webhook and a
 * real Artifacts event subscription authenticate with. A VALID token for a
 * DIFFERENT agent is 403 (cross-agent writes rejected); everything else is
 * 401. Error bodies never echo the presented token.
 */
async function requireMutatingAuth(
  request: Request,
  env: Env,
  opts: { agent?: string | null; allowSidecar?: boolean } = {},
): Promise<Response | null> {
  const presented = bearerToken(request);
  if (presented === null) {
    return json({ error: "unauthorized: bearer token required" }, 401);
  }
  if (env.ADMIN_TOKEN && (await tokensMatch(presented, env.ADMIN_TOKEN))) {
    return null;
  }
  if (opts.allowSidecar && env.LOCAL_ARTIFACTS_TOKEN && (await tokensMatch(presented, env.LOCAL_ARTIFACTS_TOKEN))) {
    return null;
  }
  const owner = await coordinator(env).credentialAgent(presented);
  if (owner !== null) {
    if (opts.agent === undefined || owner === opts.agent) {
      return null;
    }
    return json({ error: `forbidden: this token belongs to ${owner}, not ${opts.agent}` }, 403);
  }
  return json({ error: "unauthorized: ADMIN_TOKEN, the agent's task token or the sidecar bearer required" }, 401);
}

/**
 * PLAN-L1-REAL §5.4: per-principal rate limiting in front of every route
 * (except CORS preflight). Key = SHA-256 of the presented bearer, or the
 * client IP bucket for anonymous callers — the plaintext token is never a
 * key, a log field or part of a 429 body. Fails open if the counter itself
 * is unavailable: an availability incident must not masquerade as abuse
 * control, and the upstream Artifacts limits (2,000 req/10 s) still bound it.
 */
const DEFAULT_RATE_LIMIT_PER_MINUTE = 120;

export function parseRateLimit(raw: string | undefined): number {
  const trimmed = (raw ?? "").trim();
  if (trimmed === "") {
    return DEFAULT_RATE_LIMIT_PER_MINUTE;
  }
  const parsed = Number.parseInt(trimmed, 10);
  if (Number.isNaN(parsed)) {
    return DEFAULT_RATE_LIMIT_PER_MINUTE;
  }
  if (parsed === 0) {
    return 0; // explicit opt-out, documented in DEPLOY.md
  }
  return parsed > 0 ? parsed : DEFAULT_RATE_LIMIT_PER_MINUTE;
}

async function enforceRateLimit(request: Request, env: Env): Promise<Response | null> {
  const limit = parseRateLimit(env.RATE_LIMIT_PER_MINUTE);
  if (limit === 0) {
    return null;
  }
  const presented = bearerToken(request);
  const key = presented
    ? await sha256Hex(presented)
    : `ip:${request.headers.get("cf-connecting-ip") ?? "unknown"}`;
  let verdict: { allowed: boolean; retryAfterSeconds: number };
  try {
    verdict = await coordinator(env).rateLimit(key, limit);
  } catch (error) {
    logSafe(
      [env.ADMIN_TOKEN, env.RUNNER_TOKEN, env.LOCAL_ARTIFACTS_TOKEN].filter(
        (secret): secret is string => typeof secret === "string",
      ),
      "rate limiter unavailable; failing open:",
      (error as Error).message,
    );
    return null;
  }
  if (verdict.allowed) {
    return null;
  }
  return json(
    { error: "rate limit exceeded; retry later", retryAfterSeconds: verdict.retryAfterSeconds },
    429,
    { "retry-after": String(verdict.retryAfterSeconds) },
  );
}

/**
 * §5.1 webhook authenticity: when EVENTS_WEBHOOK_SECRET is configured,
 * /events/* require a valid HMAC signature over the exact raw body plus a
 * fresh timestamp (replay window). Without the secret the routes fall back
 * to bearer-only auth; setting it is a REQUIRED deploy gate (DEPLOY.md).
 */
async function verifyWebhookAuthenticity(request: Request, env: Env, rawBody: string): Promise<Response | null> {
  if (!env.EVENTS_WEBHOOK_SECRET) {
    return null;
  }
  const ok = await verifyWebhookSignature({
    rawBody,
    timestamp: request.headers.get(WEBHOOK_TIMESTAMP_HEADER),
    signature: request.headers.get(WEBHOOK_SIGNATURE_HEADER),
    secret: env.EVENTS_WEBHOOK_SECRET,
  });
  return ok ? null : json({ error: "webhook signature verification failed" }, 401);
}

const routes: FetchHandler = {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    try {
      if (method === "POST" && path === "/setup") {
        const denied = await requireBearer(request, env.ADMIN_TOKEN, "ADMIN_TOKEN");
        if (denied) {
          return denied;
        }
        return json(await coordinator(env).setup(), 201);
      }

      if (method === "POST" && path === "/tasks") {
        const denied = await requireBearer(request, env.ADMIN_TOKEN, "ADMIN_TOKEN");
        if (denied) {
          return denied;
        }
        const body = await readJson(request);
        const created = await coordinator(env).createTask({
          agent: typeof body.agent === "string" ? body.agent : undefined,
          intent: typeof body.intent === "string" ? body.intent : undefined,
          baseSha: typeof body.base_sha === "string" ? body.base_sha : undefined,
          ttlSeconds: typeof body.ttlSeconds === "number" ? body.ttlSeconds : undefined,
        });
        return json(created, 201);
      }

      if (method === "POST" && path === "/events/push") {
        // §5.1: signature over the EXACT raw bytes, verified before the body
        // is parsed or trusted for anything.
        const rawBody = await request.text();
        const sigDenied = await verifyWebhookAuthenticity(request, env, rawBody);
        if (sigDenied) {
          return sigDenied;
        }
        const body = parseJsonText(rawBody);
        // Either agent or fork identifies the pusher: the sidecar's
        // post-receive webhook posts {fork, ref, sha} (C-1309 #7a).
        const agent = typeof body.agent === "string" ? body.agent : undefined;
        const fork = typeof body.fork === "string" ? body.fork : undefined;
        if ((agent === undefined && fork === undefined) || typeof body.sha !== "string") {
          return json({ error: "agent or fork, and sha are required strings" }, 400);
        }
        // muse-r46 AUTH: head advances are privileged (an anonymous caller
        // could invalidate/suppress conflict warnings). The pushing agent's
        // own task token, ADMIN_TOKEN, or the sidecar webhook bearer.
        const requiredAgent = agent ?? (fork !== undefined ? await coordinator(env).forkOwner(fork) : undefined);
        const denied = await requireMutatingAuth(request, env, { agent: requiredAgent, allowSidecar: true });
        if (denied) {
          return denied;
        }
        const result = await coordinator(env).recordPush({
          agent,
          fork,
          ref: typeof body.ref === "string" ? body.ref : undefined,
          sha: body.sha,
        });
        return json(result);
      }

      if (method === "POST" && path === "/events/artifacts") {
        const rawBody = await request.text();
        const sigDenied = await verifyWebhookAuthenticity(request, env, rawBody);
        if (sigDenied) {
          return sigDenied;
        }
        let event;
        try {
          event = parseArtifactsPushedEvent(parseJsonText(rawBody));
        } catch (error) {
          return json({ error: (error as Error).message }, 400);
        }
        // §5.8 namespace isolation: an event from any other namespace is a
        // forged/misrouted source and is rejected outright (source allowlist).
        if (env.ARTIFACTS_NAMESPACE && event.source.namespace !== env.ARTIFACTS_NAMESPACE) {
          return json({ error: "event source namespace not allowed" }, 403);
        }
        // muse-r46 AUTH: event-subscription ingest is webhook-only — admin
        // or the sidecar/shared subscription bearer (no agent credential).
        const denied = await requireMutatingAuth(request, env, { allowSidecar: true });
        if (denied) {
          return denied;
        }
        const status = await coordinator(env).status();
        const agent = status.agents.find(
          (candidate) =>
            candidate.forkName === event.source.repoName || candidate.forkRemote === event.source.repoName,
        );
        if (!agent) {
          return json({ accepted: false, reason: `no agent owns fork ${event.source.repoName}` }, 202);
        }
        const result = await coordinator(env).recordPush({
          agent: agent.agentId,
          fork: agent.forkName,
          ref: event.payload.ref,
          sha: event.payload.after,
        });
        return json(result);
      }

      if (method === "POST" && path === "/checks") {
        const denied = await requireBearer(request, env.RUNNER_TOKEN, "RUNNER_TOKEN");
        if (denied) {
          return denied;
        }
        const body = await readJson(request);
        // C-1350: the payload declares its wire — contract "0.1" is the
        // canonical typed shape (L3 export_l1_payload), "0.0" the legacy
        // string adapter; anything else (incl. no contract field) is 400.
        let parsed: NormalizedChecksPayload;
        try {
          parsed = parseChecksPayload(body);
        } catch (error) {
          return json({ error: (error as Error).message }, 400);
        }
        const outcome = await coordinator(env).submitChecks(parsed);
        if (outcome.stale) {
          return json(
            {
              error: "stale vector: heads have moved since the runner fetched them; re-fetch /status and retry",
              currentHeads: outcome.currentHeads,
            },
            409,
          );
        }
        return json(outcome);
      }

      if (method === "GET" && path === "/status") {
        return json(await coordinator(env).status());
      }

      const taskMatch = /^\/tasks\/([^/]+)$/.exec(path);
      if (method === "GET" && taskMatch) {
        try {
          return json(await coordinator(env).getTask(decodeURIComponent(taskMatch[1])));
        } catch (error) {
          if ((error as Error).message.startsWith("unknown task")) {
            return json({ error: (error as Error).message }, 404);
          }
          throw error;
        }
      }

      const taskTestsMatch = /^\/tasks\/([^/]+)\/tests$/.exec(path);
      if (method === "POST" && taskTestsMatch) {
        // muse-r46 AUTH + deploy-prep: 401 BEFORE any existence check, so an
        // unauthenticated caller cannot enumerate task ids.
        if (bearerToken(request) === null) {
          return json({ error: "unauthorized: bearer token required" }, 401);
        }
        const taskId = decodeURIComponent(taskTestsMatch[1]);
        // muse-r46 AUTH (evidence forgery, review §a.2): only the owning
        // agent's task token or ADMIN_TOKEN may attach test provenance.
        const owner = await coordinator(env).taskOwner(taskId);
        if (owner === null) {
          return json({ error: `unknown task: ${taskId}` }, 404);
        }
        const denied = await requireMutatingAuth(request, env, { agent: owner });
        if (denied) {
          return denied;
        }
        const body = await readJson(request);
        if (typeof body.command !== "string" || typeof body.exit !== "number" || typeof body.head_sha !== "string") {
          return json({ error: "command (string), exit (number) and head_sha (string) are required" }, 400);
        }
        const result = await coordinator(env).recordTestProvenance(taskId, {
          command: body.command,
          exit: body.exit,
          head_sha: body.head_sha,
        });
        return json(result, 201);
      }

      const ackMatch = /^\/warnings\/([^/]+)\/ack$/.exec(path);
      if (method === "POST" && ackMatch) {
        // Same enumeration guard as /tasks/:id/tests: auth first.
        if (bearerToken(request) === null) {
          return json({ error: "unauthorized: bearer token required" }, 401);
        }
        const body = await readJson(request);
        if (typeof body.agent !== "string" || body.agent.length === 0) {
          return json({ error: "agent is a required string" }, 400);
        }
        // muse-r46 AUTH: the acking agent authenticates with its own task
        // token (or ADMIN_TOKEN) — agent A cannot ack as agent B. The ack is
        // attestational, so the sidecar bearer is NOT accepted here.
        const denied = await requireMutatingAuth(request, env, { agent: body.agent });
        if (denied) {
          return denied;
        }
        const result = await coordinator(env).ackWarning(decodeURIComponent(ackMatch[1]), {
          agent: body.agent,
          note: typeof body.note === "string" ? body.note : undefined,
        });
        return json(result);
      }

      return json({ error: `no route for ${method} ${path}` }, 404);
    } catch (error) {
      const message = (error as Error).message ?? "internal error";
      if (/^unknown (task|warning)/.test(message)) {
        return json({ error: message }, 404);
      }
      const status = /^(unknown agent|fork |commit |repo already|repo not found|request body|unsupported event|missing artifacts|pushed payload|invalid radar status|invalid radar kind|check result requires|runner results must|result heads|results must|base_sha|test provenance|command \(string\)|no Artifacts backend)/.test(
        message,
      )
        ? 400
        : 500;
      return json({ error: message }, status);
    }
  },
};

/**
 * Deploy-prep outer handler (PLAN-L1-REAL §5): CORS preflight + grants
 * (§5.7) and the per-principal rate-limit gate (§5.4) wrap EVERY route,
 * including error responses, so browser clients only ever see the policy
 * decided here and no route can bypass it.
 */
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      // Preflight must be answerable without credentials and is exempt from
      // the rate limit (browsers send it before they can attach anything).
      return preflightResponse(corsPolicyFromEnv(env.ALLOWED_ORIGINS), request);
    }
    const limited = await enforceRateLimit(request, env);
    if (limited) {
      return limited;
    }
    const response = await routes.fetch(request, env);
    return corsify(corsPolicyFromEnv(env.ALLOWED_ORIGINS), request, response);
  },
};
