// ChannelDO — one durable, serialized conversation log per channel.
// Storage layout (KV-style over SQLite):
//   seq                -> current max sequence number
//   msg:<zero-padded seq> -> envelope (ordered lexical scan)
//   seen:<message id>  -> {seq} dedup set for idempotent POSTs
//   ack:<machine>      -> last cursor acked by that machine
//   rl:<machine>:<window> -> fixed-window rate counter

const PAD = 12;
const SCAN_BATCH = 500;
const POLL_STEP_MS = 300;

const padSeq = (n) => String(n).padStart(PAD, "0");

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

export class ChannelDO {
  constructor(state, env) {
    this.state = state;
    this.env = env;
  }

  async fetch(request) {
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean); // [op, machine]
    const op = parts[0];
    const machine = decodeURIComponent(parts[1] || "");
    try {
      if (op === "post" && request.method === "POST") return await this.post(machine, request);
      if (op === "get" && request.method === "GET") return await this.get(machine, url);
      if (op === "ack" && request.method === "POST") return await this.ack(machine, request);
      return json({ error: "not found" }, 404);
    } catch (err) {
      return json({ error: "internal", detail: String(err) }, 500);
    }
  }

  async rateLimited(machine) {
    const limit = Number(this.env.RATE_LIMIT_PER_MINUTE || 60);
    if (!Number.isFinite(limit) || limit <= 0) return false;
    const window = Math.floor(Date.now() / 60_000);
    const key = `rl:${machine}:${window}`;
    const count = ((await this.state.storage.get(key)) || 0) + 1;
    await this.state.storage.put(key, count);
    return count > limit;
  }

  async post(machine, request) {
    if (await this.rateLimited(machine)) return json({ error: "rate limited" }, 429);

    const text = await request.text();
    if (text.length > 64 * 1024) return json({ error: "message too large" }, 413);
    let input;
    try {
      input = JSON.parse(text);
    } catch {
      return json({ error: "bad json" }, 400);
    }

    const body = input?.body;
    if (typeof body !== "string" || body.length === 0) return json({ error: "body required" }, 400);
    const kind = input.kind ?? "note";
    if (!["note", "question", "status", "event"].includes(kind)) return json({ error: "bad kind" }, 400);

    // to.machine absent/null = broadcast; tag is required for targeted display addressing.
    const to = input.to ?? {};
    if (to !== null && typeof to !== "object") return json({ error: "bad to" }, 400);
    const toMachine = to?.machine ?? null;
    if (toMachine !== null && typeof toMachine !== "string") return json({ error: "bad to.machine" }, 400);
    if (!toMachine && typeof to?.tag !== "string") return json({ error: "to.tag required" }, 400);

    // Identity: machine always comes from the token; client "from" is display metadata only.
    const from = {
      machine,
      tag: typeof input.from?.tag === "string" ? input.from.tag : null,
      session_id: typeof input.from?.session_id === "string" ? input.from.session_id : null,
    };

    // Idempotent resend: same client id returns the stored envelope untouched.
    const id = typeof input.id === "string" && input.id.length > 0 ? input.id : crypto.randomUUID();
    const seenKey = `seen:${id}`;
    const existing = await this.state.storage.get(seenKey);
    if (existing) {
      const prior = await this.state.storage.get(`msg:${padSeq(existing.seq)}`);
      if (prior) return json({ message: prior, duplicate: true }, 200);
      return json({ error: "id collision with pruned record" }, 409);
    }

    const seq = ((await this.state.storage.get("seq")) || 0) + 1;
    const message = {
      id,
      seq,
      channel: this.env.CHANNEL_ID || "global",
      from,
      to: { machine: toMachine, tag: to?.tag ?? null },
      kind,
      body,
      reply_to: typeof input.reply_to === "string" ? input.reply_to : null,
      created_at: new Date().toISOString(),
    };
    await this.state.storage.put({
      seq,
      [`msg:${padSeq(seq)}`]: message,
      [seenKey]: { seq },
    });
    return json({ message }, 201);
  }

  async readMatches(machine, after) {
    // All messages with seq > after that name this machine (or broadcast to everyone).
    // "msg;" is just past "msg:" in ASCII order, so [start, "msg;") is the whole log tail.
    const matches = [];
    let latest = after;
    let start = `msg:${padSeq(after + 1)}`;
    for (;;) {
      const page = await this.state.storage.list({ start, end: "msg;", limit: SCAN_BATCH });
      if (page.size === 0) break;
      for (const [key, value] of page) {
        const seq = Number(key.slice(4));
        latest = Math.max(latest, seq);
        const dest = value?.to?.machine ?? null;
        if (dest === null || dest === machine) matches.push(value);
      }
      if (page.size < SCAN_BATCH) break;
      const lastKey = [...page.keys()][page.size - 1];
      start = `msg:${padSeq(Number(lastKey.slice(4)) + 1)}`;
    }
    return { matches, latest };
  }

  async get(machine, url) {
    const after = Number(url.searchParams.get("after") || "0");
    const waitMs = Math.min(Number(url.searchParams.get("wait") || "0") || 0, 30_000);
    const deadline = Date.now() + waitMs;
    for (;;) {
      const { matches, latest } = await this.readMatches(machine, after);
      if (matches.length > 0) return json({ messages: matches, cursor: Math.max(latest, after) }, 200);
      if (Date.now() >= deadline) return json({ messages: [], cursor: after }, 200);
      await new Promise((resolve) => setTimeout(resolve, POLL_STEP_MS));
    }
  }

  async ack(machine, request) {
    let input;
    try {
      input = await request.json();
    } catch {
      return json({ error: "bad json" }, 400);
    }
    const cursor = Number(input?.cursor);
    if (!Number.isInteger(cursor) || cursor < 0) return json({ error: "bad cursor" }, 400);
    await this.state.storage.put(`ack:${machine}`, cursor);
    return json({ ok: true, machine, cursor }, 200);
  }
}

export { padSeq };
