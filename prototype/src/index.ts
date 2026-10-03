import type { ArtifactsNamespaceBinding } from "./artifacts/real.js";
import { Coordinator, sha256Hex, timingSafeEqual } from "./coordinator.js";
import { parseChecksPayload, type NormalizedChecksPayload } from "./checks-wire.js";
import { parseArtifactsPushedEvent } from "./types.js";

export { Coordinator } from "./coordinator.js";

declare global {
  interface Env {
    ARTIFACTS?: ArtifactsNamespaceBinding;
    RADAR_IMPL?: string;
    ADMIN_TOKEN?: string;
    RUNNER_TOKEN?: string;
    LOCAL_ARTIFACTS_URL?: string;
    LOCAL_ARTIFACTS_TOKEN?: string;
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
    }
  }
}

export interface FetchHandler {
  fetch(request: Request, env: Env): Promise<Response>;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function readJson(request: Request): Promise<Record<string, unknown>> {
  try {
    return (await request.json()) as Record<string, unknown>;
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

const handler: FetchHandler = {
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
        const body = await readJson(request);
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
        // muse-r46 AUTH: event-subscription ingest is webhook-only — admin
        // or the sidecar/shared subscription bearer (no agent credential).
        const denied = await requireMutatingAuth(request, env, { allowSidecar: true });
        if (denied) {
          return denied;
        }
        const body = await readJson(request);
        let event;
        try {
          event = parseArtifactsPushedEvent(body);
        } catch (error) {
          return json({ error: (error as Error).message }, 400);
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

export default handler;
