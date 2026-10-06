// aplexer global bus — Worker entry.
// Auth (machine token -> machine id), routing to the channel DO, coarse limits.
// The bus stamps `from.machine` from the token; client claims are never trusted.

const MAX_BODY_BYTES = 64 * 1024;
const KINDS = new Set(["note", "question", "status", "event"]);
const LONG_POLL_MS = 25_000;

function machineRegistry(env) {
  // BUS_MACHINES: JSON object mapping machine id -> bearer token.
  // In production this belongs in a secret; wrangler.jsonc carries demo values only.
  if (!env.BUS_MACHINES) return {};
  try {
    const parsed = JSON.parse(env.BUS_MACHINES);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function authMachine(request, env) {
  const header = request.headers.get("Authorization") || "";
  const match = /^Bearer\s+(\S+)$/.exec(header);
  if (!match) return null;
  const token = match[1];
  for (const [machine, expected] of Object.entries(machineRegistry(env))) {
    if (typeof expected === "string" && expected.length > 0 && token === expected) return machine;
  }
  return null;
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function channelStub(env) {
  const name = env.CHANNEL_ID || "global";
  return env.CHANNEL.get(env.CHANNEL.idFromName(name));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const machine = authMachine(request, env);
    if (!machine) return json({ error: "unauthorized" }, 401);
    const stub = channelStub(env);

    if (request.method === "POST" && url.pathname === "/v1/messages") {
      const length = Number(request.headers.get("content-length") || "0");
      if (length > MAX_BODY_BYTES) return json({ error: "message too large" }, 413);
      return stub.fetch(`https://do/post/${encodeURIComponent(machine)}`, request);
    }

    if (request.method === "GET" && url.pathname === "/v1/messages") {
      const after = url.searchParams.get("after") || "0";
      if (!/^\d+$/.test(after)) return json({ error: "bad cursor" }, 400);
      const claimed = url.searchParams.get("machine");
      if (claimed && claimed !== machine) return json({ error: "machine mismatch" }, 403);
      const waitMs = Math.min(Number(url.searchParams.get("wait") || LONG_POLL_MS) || 0, 30_000);
      return stub.fetch(
        `https://do/get/${encodeURIComponent(machine)}?after=${after}&wait=${waitMs}`,
        request,
      );
    }

    if (request.method === "POST" && url.pathname === "/v1/ack") {
      return stub.fetch(`https://do/ack/${encodeURIComponent(machine)}`, request);
    }

    return json({ error: "not found" }, 404);
  },
};

// ChannelDO must be exported from the entry wrangler points at.
// Only the default handler and DO classes may be exported: workerd treats every
// other named export as an (invalid) handler binding.
export { ChannelDO } from "./channel.js";
