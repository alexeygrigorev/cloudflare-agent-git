import type { ArtifactsNamespaceBinding } from "./artifacts/real.js";
import { Coordinator } from "./coordinator.js";
import { parseArtifactsPushedEvent } from "./types.js";

export { Coordinator } from "./coordinator.js";

declare global {
  interface Env {
    ARTIFACTS?: ArtifactsNamespaceBinding;
    RADAR_IMPL?: string;
    ARTIFACTS_IMPL?: string;
    SIDECAR_URL?: string;
    SIDECAR_TOKEN?: string;
  }
}

declare module "cloudflare:workers" {
  namespace Cloudflare {
    interface Env {
      ARTIFACTS?: ArtifactsNamespaceBinding;
      RADAR_IMPL?: string;
      ARTIFACTS_IMPL?: string;
      SIDECAR_URL?: string;
      SIDECAR_TOKEN?: string;
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

const handler: FetchHandler = {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    try {
      if (method === "POST" && path === "/setup") {
        return json(await coordinator(env).setup(), 201);
      }

      if (method === "POST" && path === "/tasks") {
        const body = await readJson(request);
        const created = await coordinator(env).createTask({
          agent: typeof body.agent === "string" ? body.agent : undefined,
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
        const body = await readJson(request);
        const result = await coordinator(env).submitChecks(
          body as unknown as Parameters<Coordinator["submitChecks"]>[0],
        );
        if (result.stale) {
          return json({ error: "stale head vector", ...result }, 409);
        }
        return json(result, 201);
      }

      if (method === "GET" && path === "/checks") {
        return json(await coordinator(env).checksReceipt());
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

      return json({ error: `no route for ${method} ${path}` }, 404);
    } catch (error) {
      const message = (error as Error).message ?? "internal error";
      const status = /^(unknown agent|fork |commit |repo already|request body|unsupported event|missing artifacts|pushed payload)/.test(
        message,
      )
        ? 400
        : 500;
      return json({ error: message }, status);
    }
  },
};

export default handler;
