/**
 * Cloudflare Worker fetch handler (facade extraction, 2026-10-03): maps
 * the platform Request/Response onto the provider-neutral HttpRequest /
 * HttpResponse and delegates ALL routing decisions to src/core/router.ts.
 * Route behavior, statuses and bodies are byte-identical to pre-facade.
 */

import type { CoordinatorAccess } from "../core/coordinator.js";
import { BearerRateLimiter, handleRoute, type HttpRequest, type RouterServices } from "../core/router.js";
import { artifactsPushEvents, directPushEvents } from "./push-events.js";

// C-1441: module scope so the tracked-client table persists across
// requests within this isolate (clean defaults: 500 entries, 5 failures
// per 60s). Isolate eviction resets it — bounded memory by construction.
const bearerRateLimiter = new BearerRateLimiter();

export interface FetchHandler {
  fetch(request: Request, env: Env): Promise<Response>;
}

function coordinatorAccess(env: Env): CoordinatorAccess {
  // The typed RPC stub's TYPE mapping over-approximates: tuple results
  // ([string, string] pair tuples) are widened to string[] and results pick
  // up RPC bookkeeping intersections, though structured clone preserves the
  // real values at runtime. Assert through this one adapter boundary instead
  // of widening the core's CoordinatorAccess types everywhere.
  return env.COORDINATOR.get(env.COORDINATOR.idFromName("global")) as unknown as CoordinatorAccess;
}

function toHttpRequest(request: Request): HttpRequest {
  return {
    method: request.method,
    path: new URL(request.url).pathname,
    header: (name) => request.headers.get(name),
    json: () => request.json(),
    // C-1441: the edge always provides the real client IP.
    clientKey: request.headers.get("cf-connecting-ip"),
  };
}

function toResponse(response: {
  status: number;
  body: unknown;
  headers?: Record<string, string>;
}): Response {
  // 204 must not carry a body; Workers rejects new Response(text, {status: 204}).
  const body = response.status === 204 ? null : JSON.stringify(response.body, null, 2);
  return new Response(body, {
    status: response.status,
    headers: { "content-type": "application/json", ...response.headers },
  });
}

const handler: FetchHandler = {
  async fetch(request: Request, env: Env): Promise<Response> {
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
    return toResponse(await handleRoute(services, toHttpRequest(request)));
  },
};

export default handler;
