/**
 * Provider-neutral HTTP routing (facade extraction, 2026-10-03).
 *
 * handleRoute is the ONE implementation of every wire route (CONTRACT.md):
 * the Cloudflare Worker fetch handler and the local node:http entry both
 * translate their platform request into the neutral HttpRequest view, call
 * handleRoute, and serialize the neutral HttpResponse. No Request/Response,
 * env bindings or Durable Object types appear here — the same statuses,
 * bodies and auth decisions are produced on every runtime.
 */

import { parseChecksPayload, type NormalizedChecksPayload } from "../checks-wire.js";
import type { PushEvents } from "../ports/push-events.js";
import {
  bearerFrom,
  decideBearer,
  decideMutatingAuth,
  type AuthDecision,
  type AuthTokens,
} from "./auth.js";
import type { CoordinatorAccess } from "./coordinator.js";

/** Runtime-agnostic request view (adapters translate to/from this). */
export interface HttpRequest {
  method: string;
  /** Path WITHOUT query string, e.g. "/tasks/task-0001/tests". */
  path: string;
  /** Case-insensitive header lookup; null when absent. */
  header(name: string): string | null;
  /** Parsed JSON body. Throws on malformed JSON (mapped to 400). */
  json(): Promise<unknown>;
  /** Best-effort client identity for the invalid-bearer rate limiter
   * (Worker: cf-connecting-ip; node: socket remote address). Null when the
   * runtime cannot tell — those callers share one conservative bucket. */
  clientKey?: string | null;
}

/** Runtime-agnostic response (adapters serialize body as pretty JSON).
 * Optional headers travel with the response so behavior like the CORS
 * policy the review UI depends on is identical on every runtime. */
export interface HttpResponse {
  status: number;
  body: unknown;
  headers?: Record<string, string>;
}

/** The review UI (prototype/ui) is served from its own origin and fetches
 * /status cross-origin (documented ?api= usage), so responses need CORS. */
const CORS_HEADERS: Record<string, string> = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type",
};

export interface RouterServices {
  coordinator: CoordinatorAccess;
  tokens: AuthTokens;
  /** POST /events/push normalizer (agent POSTs and webhook deliveries). */
  pushes: PushEvents;
  /** POST /events/artifacts normalizer (event subscription envelopes). */
  artifactsEvents: PushEvents;
  /** Invalid-bearer rate limiter (C-1441). Optional so minimal rigs stay
   * valid; every real runtime injects one with clean defaults. */
  rateLimiter?: BearerRateLimiter;
}

/**
 * Bounded invalid-bearer rate limiter (C-1441): pure, HTTP-free defense
 * against bearer-guessing floods. Tracks CONSECUTIVE 401 outcomes per
 * client key; after `maxFailures` failures inside `windowMs` the client is
 * blocked (the router answers 429 instead of 401) until the window from
 * the FIRST failure expires. A successful authentication clears the count,
 * so legitimate clients are never blocked. The tracked-client table is
 * hard-capped with LRU eviction — a flood of spoofed/unique sources can
 * evict other attackers' entries but can never grow memory.
 */
export interface BearerRateLimiterOptions {
  /** Tracked-client table cap; the least-recently-seen entry is evicted. */
  maxEntries?: number;
  /** Consecutive 401s inside the window that arm the block (default 5). */
  maxFailures?: number;
  /** Rolling window for consecutive failures, ms (default 60_000). */
  windowMs?: number;
  /** Seconds advertised in the 429 Retry-After header (default 60). */
  retryAfterSeconds?: number;
  /** Injectable clock in ms epoch (tests); defaults to Date.now. */
  now?: () => number;
}

interface FailureEntry {
  count: number;
  firstFailureAt: number;
}

/** Clients the adapters cannot identify share one conservative bucket. */
const UNKNOWN_CLIENT_KEY = "unknown";

export class BearerRateLimiter {
  private readonly entries = new Map<string, FailureEntry>();
  private readonly maxEntries: number;
  readonly maxFailures: number;
  private readonly windowMs: number;
  readonly retryAfterSeconds: number;
  private readonly now: () => number;

  constructor(options: BearerRateLimiterOptions = {}) {
    this.maxEntries = options.maxEntries ?? 500;
    this.maxFailures = options.maxFailures ?? 5;
    this.windowMs = options.windowMs ?? 60_000;
    this.retryAfterSeconds = options.retryAfterSeconds ?? 60;
    this.now = options.now ?? Date.now;
  }

  /** Number of tracked clients (never exceeds maxEntries). */
  get size(): number {
    return this.entries.size;
  }

  /**
   * Record one 401 outcome for the client; true when this failure ARMS the
   * block (i.e. the request must get 429, not 401). Failures outside the
   * window restart the count, so sustained-low-and-slow guessing is still
   * bounded per window.
   */
  recordFailure(clientKey: string | null): boolean {
    const key = clientKey ?? UNKNOWN_CLIENT_KEY;
    const at = this.now();
    const existing = this.entries.get(key);
    const entry =
      !existing || at - existing.firstFailureAt >= this.windowMs
        ? { count: 1, firstFailureAt: at }
        : { count: existing.count + 1, firstFailureAt: existing.firstFailureAt };
    // Delete + set refreshes recency: Map iteration order is insertion
    // order, so the OLDEST entry is always first for eviction.
    this.entries.delete(key);
    this.entries.set(key, entry);
    while (this.entries.size > this.maxEntries) {
      const oldest = this.entries.keys().next();
      if (oldest.done) {
        break;
      }
      this.entries.delete(oldest.value);
    }
    return entry.count > this.maxFailures;
  }

  /** Successful authentication clears the client's failure count. */
  recordSuccess(clientKey: string | null): void {
    this.entries.delete(clientKey ?? UNKNOWN_CLIENT_KEY);
  }
}

function json(body: unknown, status = 200): HttpResponse {
  return { status, body, headers: { ...CORS_HEADERS } };
}

async function readJson(request: HttpRequest): Promise<Record<string, unknown>> {
  try {
    return (await request.json()) as Record<string, unknown>;
  } catch {
    throw new Error("request body must be valid JSON");
  }
}

function deniedOrOk(decision: AuthDecision): HttpResponse | null {
  return decision.ok ? null : json({ error: decision.error }, decision.status);
}

const RATE_LIMITED_BODY = {
  error: "rate_limited",
  message: "Too many failed authentication attempts. Please retry later.",
};

/**
 * C-1441: shared epilogue of every bearer-auth check. Success clears the
 * client's failure count; 401 (unauthenticated) failures are counted and —
 * from the (maxFailures+1)-th consecutive one inside the window — answered
 * with 429 + Retry-After instead of 401. 403 (valid credential, wrong
 * agent) and 503 (fail-closed, server misconfig) are neither counted nor
 * cleared: they are not unauthenticated bearer failures.
 */
function authedOutcome(
  services: RouterServices,
  request: HttpRequest,
  decision: AuthDecision,
): HttpResponse | null {
  const limiter = services.rateLimiter;
  if (!limiter) {
    return deniedOrOk(decision);
  }
  if (decision.ok) {
    limiter.recordSuccess(request.clientKey ?? null);
    return null;
  }
  if (decision.status !== 401) {
    return deniedOrOk(decision);
  }
  if (limiter.recordFailure(request.clientKey ?? null)) {
    return {
      status: 429,
      body: RATE_LIMITED_BODY,
      headers: { ...CORS_HEADERS, "retry-after": String(limiter.retryAfterSeconds) },
    };
  }
  return deniedOrOk(decision);
}

async function requireBearer(
  request: HttpRequest,
  services: RouterServices,
  expected: string | undefined,
  envName: "ADMIN_TOKEN" | "RUNNER_TOKEN",
): Promise<HttpResponse | null> {
  const decision = await decideBearer(bearerFrom(request.header("authorization")), expected, envName);
  return authedOutcome(services, request, decision);
}

async function requireMutatingAuth(
  request: HttpRequest,
  services: RouterServices,
  opts: { agent?: string | null; allowSidecar?: boolean } = {},
): Promise<HttpResponse | null> {
  const decision = await decideMutatingAuth(
    bearerFrom(request.header("authorization")),
    services.tokens,
    opts,
    (presented) => services.coordinator.credentialAgent(presented),
  );
  return authedOutcome(services, request, decision);
}

/**
 * Error mapping, verbatim from the pre-facade Worker handler: known
 * caller mistakes are 400, unknown task/warning 404, everything else 500.
 */
function errorResponse(error: unknown): HttpResponse {
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

export async function handleRoute(services: RouterServices, request: HttpRequest): Promise<HttpResponse> {
  const path = request.path;
  const method = request.method;
  const coordinator = services.coordinator;

  try {
    if (method === "OPTIONS") {
      return {
        status: 204,
        body: null,
        headers: { ...CORS_HEADERS, "access-control-max-age": "86400" },
      };
    }

    if (method === "POST" && path === "/setup") {
      const denied = await requireBearer(request, services, services.tokens.admin, "ADMIN_TOKEN");
      if (denied) {
        return denied;
      }
      return json(await coordinator.setup(), 201);
    }

    if (method === "POST" && path === "/tasks") {
      const denied = await requireBearer(request, services, services.tokens.admin, "ADMIN_TOKEN");
      if (denied) {
        return denied;
      }
      const body = await readJson(request);
      const created = await coordinator.createTask({
        agent: typeof body.agent === "string" ? body.agent : undefined,
        intent: typeof body.intent === "string" ? body.intent : undefined,
        baseSha: typeof body.base_sha === "string" ? body.base_sha : undefined,
        ttlSeconds: typeof body.ttlSeconds === "number" ? body.ttlSeconds : undefined,
      });
      return json(created, 201);
    }

    if (method === "POST" && path === "/events/push") {
      const body = await readJson(request);
      // Either agent or fork identifies the pusher: the sidecar's
      // post-receive webhook posts {fork, ref, sha} (C-1309 #7a).
      let push;
      try {
        push = services.pushes.normalize(body);
      } catch (error) {
        return json({ error: (error as Error).message }, 400);
      }
      // muse-r46 AUTH: head advances are privileged (an anonymous caller
      // could invalidate/suppress conflict warnings). The pushing agent's
      // own task token, ADMIN_TOKEN, or the sidecar webhook bearer.
      const requiredAgent = push.agent ?? (push.fork !== undefined ? await coordinator.forkOwner(push.fork) : undefined);
      const denied = await requireMutatingAuth(request, services, { agent: requiredAgent, allowSidecar: true });
      if (denied) {
        return denied;
      }
      const result = await coordinator.recordPush({
        agent: push.agent,
        fork: push.fork,
        ref: push.ref,
        sha: push.sha,
      });
      return json(result);
    }

    if (method === "POST" && path === "/events/artifacts") {
      // muse-r46 AUTH: event-subscription ingest is webhook-only — admin
      // or the sidecar/shared subscription bearer (no agent credential).
      const denied = await requireMutatingAuth(request, services, { allowSidecar: true });
      if (denied) {
        return denied;
      }
      const body = await readJson(request);
      let event;
      try {
        event = services.artifactsEvents.normalize(body);
      } catch (error) {
        return json({ error: (error as Error).message }, 400);
      }
      const status = await coordinator.status();
      const agent = status.agents.find(
        (candidate) => candidate.forkName === event.fork || candidate.forkRemote === event.fork,
      );
      if (!agent) {
        return json({ accepted: false, reason: `no agent owns fork ${event.fork}` }, 202);
      }
      const result = await coordinator.recordPush({
        agent: agent.agentId,
        fork: agent.forkName,
        ref: event.ref,
        sha: event.sha,
      });
      return json(result);
    }

    if (method === "POST" && path === "/checks") {
      const denied = await requireBearer(request, services, services.tokens.runner, "RUNNER_TOKEN");
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
      const outcome = await coordinator.submitChecks(parsed);
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
      return json(await coordinator.status());
    }

    const taskMatch = /^\/tasks\/([^/]+)$/.exec(path);
    if (method === "GET" && taskMatch) {
      try {
        return json(await coordinator.getTask(decodeURIComponent(taskMatch[1])));
      } catch (error) {
        if ((error as Error).message.startsWith("unknown task")) {
          return json({ error: (error as Error).message }, 404);
        }
        throw error;
      }
    }

    const taskTestsMatch = /^\/tasks\/([^/]+)\/tests$/.exec(path);
    if (method === "POST" && taskTestsMatch) {
      const taskId = decodeURIComponent(taskTestsMatch[1]);
      // muse-r46 AUTH (evidence forgery, review §a.2): only the owning
      // agent's task token or ADMIN_TOKEN may attach test provenance.
      const owner = await coordinator.taskOwner(taskId);
      if (owner === null) {
        return json({ error: `unknown task: ${taskId}` }, 404);
      }
      const denied = await requireMutatingAuth(request, services, { agent: owner });
      if (denied) {
        return denied;
      }
      const body = await readJson(request);
      if (typeof body.command !== "string" || typeof body.exit !== "number" || typeof body.head_sha !== "string") {
        return json({ error: "command (string), exit (number) and head_sha (string) are required" }, 400);
      }
      const result = await coordinator.recordTestProvenance(taskId, {
        command: body.command,
        exit: body.exit,
        head_sha: body.head_sha,
      });
      return json(result, 201);
    }

    const ackMatch = /^\/warnings\/([^/]+)\/ack$/.exec(path);
    if (method === "POST" && ackMatch) {
      const body = await readJson(request);
      if (typeof body.agent !== "string" || body.agent.length === 0) {
        return json({ error: "agent is a required string" }, 400);
      }
      // muse-r46 AUTH: the acking agent authenticates with its own task
      // token (or ADMIN_TOKEN) — agent A cannot ack as agent B. The ack is
      // attestational, so the sidecar bearer is NOT accepted here.
      const denied = await requireMutatingAuth(request, services, { agent: body.agent });
      if (denied) {
        return denied;
      }
      const result = await coordinator.ackWarning(decodeURIComponent(ackMatch[1]), {
        agent: body.agent,
        note: typeof body.note === "string" ? body.note : undefined,
      });
      return json(result);
    }

    const taskRevokeMatch = /^\/tasks\/([^/]+)\/revoke$/.exec(path);
    if (method === "POST" && taskRevokeMatch) {
      // C-1425: token revocation is an admin control — ADMIN_TOKEN only
      // (auth first, so task-id probing is not available to unauthenticated
      // callers), then the task must exist.
      const denied = await requireBearer(request, services, services.tokens.admin, "ADMIN_TOKEN");
      if (denied) {
        return denied;
      }
      const taskId = decodeURIComponent(taskRevokeMatch[1]);
      const owner = await coordinator.taskOwner(taskId);
      if (owner === null) {
        return json({ error: `unknown task: ${taskId}` }, 404);
      }
      const revoked = await coordinator.revokeAgentToken(owner);
      return json({ taskId, agentId: owner, revoked });
    }

    return json({ error: `no route for ${method} ${path}` }, 404);
  } catch (error) {
    return errorResponse(error);
  }
}
