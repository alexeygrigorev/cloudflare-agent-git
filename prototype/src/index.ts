import type { ArtifactsNamespaceBinding } from "./artifacts/real.js";
import { Coordinator } from "./coordinator.js";
import { parseArtifactsPushedEvent } from "./types.js";

export { Coordinator } from "./coordinator.js";

declare global {
  interface Env {
    ARTIFACTS?: ArtifactsNamespaceBinding;
    RADAR_IMPL?: string;
    ADMIN_TOKEN?: string;
    RUNNER_TOKEN?: string;
  }
}

declare module "cloudflare:workers" {
  namespace Cloudflare {
    interface Env {
      ARTIFACTS?: ArtifactsNamespaceBinding;
      RADAR_IMPL?: string;
      ADMIN_TOKEN?: string;
      RUNNER_TOKEN?: string;
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

/** Constant-time string compare (avoids timing oracles; never logs either side). */
function tokensMatch(presented: string, expected: string): boolean {
  if (presented.length !== expected.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < presented.length; i++) {
    diff |= presented.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return diff === 0;
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
): Response | null {
  if (!expected) {
    return json({ error: `${envName} is not configured; refusing authenticated request (fail closed)` }, 503);
  }
  const presented = bearerToken(request);
  if (presented === null || !tokensMatch(presented, expected)) {
    return json({ error: `unauthorized: valid bearer token required (${envName})` }, 401);
  }
  return null;
}

const handler: FetchHandler = {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    try {
      if (method === "POST" && path === "/setup") {
        const denied = requireBearer(request, env.ADMIN_TOKEN, "ADMIN_TOKEN");
        if (denied) {
          return denied;
        }
        return json(await coordinator(env).setup(), 201);
      }

      if (method === "POST" && path === "/tasks") {
        const denied = requireBearer(request, env.ADMIN_TOKEN, "ADMIN_TOKEN");
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
        if (typeof body.agent !== "string" || typeof body.sha !== "string") {
          return json({ error: "agent and sha are required strings" }, 400);
        }
        const result = await coordinator(env).recordPush({
          agent: body.agent,
          fork: typeof body.fork === "string" ? body.fork : undefined,
          ref: typeof body.ref === "string" ? body.ref : undefined,
          sha: body.sha,
        });
        return json(result);
      }

      if (method === "POST" && path === "/events/artifacts") {
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
        const denied = requireBearer(request, env.RUNNER_TOKEN, "RUNNER_TOKEN");
        if (denied) {
          return denied;
        }
        const body = await readJson(request);
        if (!Array.isArray(body.results)) {
          return json({ error: "results must be an array" }, 400);
        }
        const result = await coordinator(env).applyCheckResults({
          policy: typeof body.policy === "string" ? body.policy : "unknown-policy",
          results: body.results as { pair: [string, string]; status: string; kind?: string; evidence?: string }[],
        });
        return json(result);
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
        const body = await readJson(request);
        if (typeof body.command !== "string" || typeof body.exit !== "number" || typeof body.head_sha !== "string") {
          return json({ error: "command (string), exit (number) and head_sha (string) are required" }, 400);
        }
        const result = await coordinator(env).recordTestProvenance(decodeURIComponent(taskTestsMatch[1]), {
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
      const status = /^(unknown agent|fork |commit |repo already|request body|unsupported event|missing artifacts|pushed payload|invalid radar status|check result requires|runner results must|results must|base_sha|test provenance|command \(string\))/.test(
        message,
      )
        ? 400
        : 500;
      return json({ error: message }, status);
    }
  },
};

export default handler;
