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

async function requireBearer(
  request: HttpRequest,
  expected: string | undefined,
  envName: "ADMIN_TOKEN" | "RUNNER_TOKEN",
): Promise<HttpResponse | null> {
  return deniedOrOk(await decideBearer(bearerFrom(request.header("authorization")), expected, envName));
}

async function requireMutatingAuth(
  request: HttpRequest,
  services: RouterServices,
  opts: { agent?: string | null; allowSidecar?: boolean } = {},
): Promise<HttpResponse | null> {
  return deniedOrOk(
    await decideMutatingAuth(
      bearerFrom(request.header("authorization")),
      services.tokens,
      opts,
      (presented) => services.coordinator.credentialAgent(presented),
    ),
  );
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
      const denied = await requireBearer(request, services.tokens.admin, "ADMIN_TOKEN");
      if (denied) {
        return denied;
      }
      return json(await coordinator.setup(), 201);
    }

    if (method === "POST" && path === "/tasks") {
      const denied = await requireBearer(request, services.tokens.admin, "ADMIN_TOKEN");
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
      const denied = await requireBearer(request, services.tokens.runner, "RUNNER_TOKEN");
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

    return json({ error: `no route for ${method} ${path}` }, 404);
  } catch (error) {
    return errorResponse(error);
  }
}
