import type { CoordinatorAccess } from "../core/coordinator.js";
import { BearerRateLimiter, handleRoute, type HttpRequest, type RouterServices } from "../core/router.js";
import { artifactsPushEvents, directPushEvents } from "./push-events.js";
import { HARD_CEILINGS, parseConfigLimit } from "./budget.js";

const bearerRateLimiter = new BearerRateLimiter();

export interface FetchHandler {
  fetch(request: Request, env: Env): Promise<Response>;
}

function getCoordinatorDO(env: Env) {
  return env.COORDINATOR.get(env.COORDINATOR.idFromName("global"));
}

function coordinatorAccess(env: Env): CoordinatorAccess {
  return getCoordinatorDO(env) as unknown as CoordinatorAccess;
}

function toHttpRequest(request: Request, env: Env): HttpRequest {
  return {
    method: request.method,
    path: new URL(request.url).pathname,
    header: (name) => request.headers.get(name),
    json: async () => {
      const limit = parseConfigLimit(env.MAX_BODY_BYTES !== undefined ? env.MAX_BODY_BYTES : env.BUDGET_MAX_BODY_BYTES, "MAX_BODY_BYTES", HARD_CEILINGS.maxBodyBytes);
      const bytes = await readBoundedRequestBody(request, limit);
      if (bytes === null) throw Object.assign(new Error("request body exceeded bounds"), { status: 413 });
      return JSON.parse(new TextDecoder().decode(bytes));
    },
    clientKey: request.headers.get("cf-connecting-ip"),
  };
}

function toResponse(response: {
  status: number;
  body: unknown;
  headers?: Record<string, string>;
}): Response {
  const body = response.status === 204 ? null : JSON.stringify(response.body, null, 2);
  return new Response(body, {
    status: response.status,
    headers: { "content-type": "application/json", ...response.headers },
  });
}

function isValidUpstreamRemote(remote: string, repo: string, allowLocal: boolean): boolean {
  try {
    const u = new URL(remote);
    if (u.username || u.password || u.search || u.hash) return false;
    if (u.protocol === "https:" && !u.port) {
      // Must match exact pattern:
      // hostname: [account].artifacts.cloudflare.net
      // pathname: /git/agent-branches-dev/<repo>.git
      const hostParts = u.hostname.split(".");
      if (
        hostParts.length === 4 &&
        hostParts[1] === "artifacts" &&
        hostParts[2] === "cloudflare" &&
        hostParts[3] === "net" &&
        /^[a-zA-Z0-9-]+$/.test(hostParts[0])
      ) {
        const expectedPath = `/git/agent-branches-dev/${repo}.git`;
        return u.pathname === expectedPath;
      }
      return false;
    }
    // Allow local sidecar in test/dev: http://127.0.0.1:<port> or http://localhost:<port>
    if (allowLocal && u.protocol === "http:" && (u.hostname === "127.0.0.1" || u.hostname === "localhost")) {
      return u.pathname === `/git/${repo}.git`;
    }
    return false;
  } catch {
    return false;
  }
}

async function readBoundedRequestBody(request: Request | Response, maxBytes: number): Promise<Uint8Array | null> {
  const clHeader = request.headers.get("content-length");
  if (clHeader) {
    const cl = Number(clHeader);
    if (Number.isFinite(cl) && cl > maxBytes) {
      return null;
    }
  }

  if (!request.body) {
    return new Uint8Array(0);
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let totalBytes = 0;

  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error("Body deadline exceeded")), 30000);
  });
  try {
    while (true) {
      const { done, value } = await Promise.race([reader.read(), deadline]);
      if (done) break;
      if (value) {
        totalBytes += value.byteLength;
        if (totalBytes > maxBytes) {
          try {
            void reader.cancel("Payload too large").catch(() => {});
          } catch {}
          return null;
        }
        chunks.push(value);
      }
    }
  } catch {
    void reader.cancel("Body read failed").catch(() => {});
    return null;
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }

  const result = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}

function filterUpstreamRequestHeaders(headers: Headers): Headers {
  const allowed = ["accept", "accept-encoding", "content-type", "user-agent", "git-protocol"];
  const out = new Headers();
  for (const [key, value] of headers.entries()) {
    if (allowed.includes(key.toLowerCase())) {
      out.set(key, value);
    }
  }
  return out;
}

function filterUpstreamResponseHeaders(headers: Headers): Headers {
  const allowed = ["content-type", "cache-control", "expires", "pragma"];
  const out = new Headers();
  for (const [key, value] of headers.entries()) {
    if (allowed.includes(key.toLowerCase())) {
      out.set(key, value);
    }
  }
  return out;
}

const handler: FetchHandler = {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    const getBearer = () => {
      const auth = request.headers.get("Authorization");
      if (auth && auth.toLowerCase().startsWith("bearer ")) {
        return auth.substring(7).trim();
      }
      return null;
    };

    if (method === "GET" && path === "/cloud/budget") {
      const token = getBearer();
      if (!token || !env.ADMIN_TOKEN || token !== env.ADMIN_TOKEN) {
        return new Response("Unauthorized", { status: 401 });
      }
      const doStub = getCoordinatorDO(env) as any;
      const stats = await doStub.getBudgetStats();
      return new Response(JSON.stringify(stats), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (method === "DELETE" && path === "/cloud/demo-repos") {
      const token = getBearer();
      if (!token || !env.ADMIN_TOKEN || token !== env.ADMIN_TOKEN) {
        return new Response("Unauthorized", { status: 401 });
      }
      const doStub = getCoordinatorDO(env) as any;
      const count = await doStub.deleteDemoRepos();
      return new Response(JSON.stringify({ deleted: count }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (path === "/public/status") {
      if (method !== "GET") {
        return new Response("Method not allowed", { status: 405 });
      }
      const doStub = getCoordinatorDO(env) as unknown as CoordinatorAccess;
      const status = await doStub.snapshot();
      if (status.canonical && status.canonical.remote && status.canonical.remote.startsWith("/")) {
        status.canonical.remote = url.origin + status.canonical.remote;
      }
      return new Response(
        JSON.stringify({
          status: "ok",
          sanitizedSnapshot: true,
          canonical: status.canonical,
          agents: status.agents.map((agent: any) => ({ agentId: agent.agentId, taskId: agent.taskId, baseSha: agent.baseSha })),
          heads: status.heads,
          pairs: status.pairs.map((pair: any) => ({ pair: pair.pair, heads: pair.heads, status: pair.status, kind: pair.kind, coverage: pair.coverage, checkedAt: pair.checkedAt, stale: pair.stale, activeWarningIds: pair.activeWarningIds })),
          warnings: status.warnings.map((warning: any) => ({ id: warning.id, pair: warning.pair, status: warning.status, createdAt: warning.createdAt })),
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    const gitMatch = /^\/git\/([a-zA-Z0-9_.-]+)\.git\/(info\/refs|git-upload-pack|git-receive-pack)$/.exec(path);
    if (gitMatch) {
      const repo = gitMatch[1];
      const action = gitMatch[2];
      const token = getBearer();
      if (!token) return new Response("Unauthorized", { status: 401 });

      const doStub = getCoordinatorDO(env) as any;
      const tokenInfo = await doStub.resolveGatewayToken(token, repo);
      if (!tokenInfo) return new Response("Forbidden", { status: 403 });
      if (tokenInfo.repo !== repo) return new Response("Cross-repo access forbidden", { status: 403 });

      if (!isValidUpstreamRemote(tokenInfo.upstreamRemote, repo, !env.ARTIFACTS && !!env.LOCAL_ARTIFACTS_URL)) {
        return new Response("Invalid upstream remote", { status: 502 });
      }

      if (method === "GET" && action === "info/refs") {
        const service = url.searchParams.get("service");
        if (service !== "git-upload-pack" && service !== "git-receive-pack") {
          return new Response("Invalid service", { status: 400 });
        }
        if (service === "git-receive-pack" && tokenInfo.scope !== "write") {
          return new Response("Write scope required", { status: 403 });
        }
        try {
          await doStub.reserveGitOperation();
        } catch (err: any) {
          const status = err.status || (err.message?.includes("exceeded") ? 429 : 503);
          return new Response(err.message, { status });
        }

        const upstreamUrl = `${tokenInfo.upstreamRemote}/info/refs?service=${service}`;
        const proxyHeaders = filterUpstreamRequestHeaders(request.headers);
        proxyHeaders.set("Authorization", `Bearer ${tokenInfo.realToken}`);

        let resp: Response;
        try {
          resp = await fetch(upstreamUrl, {
            method: "GET",
            headers: proxyHeaders,
            redirect: "manual",
            signal: AbortSignal.timeout(30000),
          });
        } catch {
          return new Response("Upstream gateway error", { status: 502 });
        }

        if (resp.status >= 300 && resp.status < 400) {
          return new Response("Redirect not allowed", { status: 502 });
        }
        if (!resp.ok) {
          void resp.body?.cancel().catch(() => {});
          return new Response("Upstream gateway error", { status: 502 });
        }
        const responseBytes = await readBoundedRequestBody(resp, HARD_CEILINGS.maxTotalBytes);
        if (responseBytes === null) return new Response("Upstream response exceeded bounds", { status: 502 });
        const respHeaders = filterUpstreamResponseHeaders(resp.headers);
        return new Response(responseBytes, { status: resp.status, headers: respHeaders });
      }

      if (method === "POST" && action === "git-receive-pack") {
        if (tokenInfo.scope !== "write") {
          return new Response("Write scope required", { status: 403 });
        }

        try {
          await doStub.reserveGitOperation();
        } catch (err: any) {
          const status = err.status || (err.message?.includes("exceeded") ? 429 : 503);
          return new Response(err.message, { status });
        }

        const maxBodyBytes = parseConfigLimit(
          env.MAX_BODY_BYTES !== undefined ? env.MAX_BODY_BYTES : env.BUDGET_MAX_BODY_BYTES,
          "MAX_BODY_BYTES",
          HARD_CEILINGS.maxBodyBytes,
        );
        const bodyBytes = await readBoundedRequestBody(request, maxBodyBytes);
        if (bodyBytes === null) {
          return new Response("Payload too large", { status: 413 });
        }

        if (bodyBytes.byteLength > 0) {
          try {
            await doStub.reserveGitBytes(bodyBytes.byteLength);
          } catch (err: any) {
            const status = err.status || (err.message?.includes("exceeded") ? 429 : 503);
            return new Response(err.message, { status });
          }
        }

        const upstreamUrl = `${tokenInfo.upstreamRemote}/git-receive-pack`;
        const proxyHeaders = filterUpstreamRequestHeaders(request.headers);
        proxyHeaders.set("Authorization", `Bearer ${tokenInfo.realToken}`);

        let resp: Response;
        try {
          resp = await fetch(upstreamUrl, {
            method: "POST",
            headers: proxyHeaders,
            body: bodyBytes,
            redirect: "manual",
            signal: AbortSignal.timeout(30000),
          });
        } catch {
          return new Response("Upstream gateway error", { status: 502 });
        }

        if (resp.status >= 300 && resp.status < 400) {
          return new Response("Redirect not allowed", { status: 502 });
        }
        if (!resp.ok) {
          void resp.body?.cancel().catch(() => {});
          return new Response("Upstream gateway error", { status: 502 });
        }
        const responseBytes = await readBoundedRequestBody(resp, HARD_CEILINGS.maxTotalBytes);
        if (responseBytes === null) return new Response("Upstream response exceeded bounds", { status: 502 });
        const respHeaders = filterUpstreamResponseHeaders(resp.headers);
        return new Response(responseBytes, { status: resp.status, headers: respHeaders });
      }

      if (method === "POST" && action === "git-upload-pack") {
        try {
          await doStub.reserveGitOperation();
        } catch (err: any) {
          const status = err.status || (err.message?.includes("exceeded") ? 429 : 503);
          return new Response(err.message, { status });
        }

        const maxBodyBytes = parseConfigLimit(
          env.MAX_BODY_BYTES !== undefined ? env.MAX_BODY_BYTES : env.BUDGET_MAX_BODY_BYTES,
          "MAX_BODY_BYTES",
          HARD_CEILINGS.maxBodyBytes,
        );
        const bodyBytes = await readBoundedRequestBody(request, maxBodyBytes);
        if (bodyBytes === null) {
          return new Response("Payload too large", { status: 413 });
        }

        const upstreamUrl = `${tokenInfo.upstreamRemote}/git-upload-pack`;
        const proxyHeaders = filterUpstreamRequestHeaders(request.headers);
        proxyHeaders.set("Authorization", `Bearer ${tokenInfo.realToken}`);

        let resp: Response;
        try {
          resp = await fetch(upstreamUrl, {
            method: "POST",
            headers: proxyHeaders,
            body: bodyBytes,
            redirect: "manual",
            signal: AbortSignal.timeout(30000),
          });
        } catch {
          return new Response("Upstream gateway error", { status: 502 });
        }

        if (resp.status >= 300 && resp.status < 400) {
          return new Response("Redirect not allowed", { status: 502 });
        }
        if (!resp.ok) {
          void resp.body?.cancel().catch(() => {});
          return new Response("Upstream gateway error", { status: 502 });
        }
        const responseBytes = await readBoundedRequestBody(resp, HARD_CEILINGS.maxTotalBytes);
        if (responseBytes === null) return new Response("Upstream response exceeded bounds", { status: 502 });
        const respHeaders = filterUpstreamResponseHeaders(resp.headers);
        return new Response(responseBytes, { status: resp.status, headers: respHeaders });
      }

      return new Response("Method not allowed", { status: 405 });
    }

    const services: RouterServices = {
      coordinator: coordinatorAccess(env),
      tokens: {
        admin: env.ADMIN_TOKEN,
        runner: env.RUNNER_TOKEN,
        sidecar: env.LOCAL_ARTIFACTS_TOKEN,
      },
      pushes: directPushEvents,
      artifactsEvents: artifactsPushEvents,
      rateLimiter: bearerRateLimiter,
    };

    const routerResponse = await handleRoute(services, toHttpRequest(request, env));
    if (routerResponse.status === 200 || routerResponse.status === 201) {
      if (typeof routerResponse.body === "object" && routerResponse.body !== null) {
        const bodyObj = routerResponse.body as any;
        if (bodyObj.fork && bodyObj.fork.remote && bodyObj.fork.remote.startsWith("/")) {
          bodyObj.fork.remote = url.origin + bodyObj.fork.remote;
        }
        if (bodyObj.canonical && bodyObj.canonical.remote && bodyObj.canonical.remote.startsWith("/")) {
          bodyObj.canonical.remote = url.origin + bodyObj.canonical.remote;
        }
      }
    }

    return toResponse(routerResponse);
  },
};

export default handler;
