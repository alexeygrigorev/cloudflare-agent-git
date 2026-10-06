import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

const ALPHA = "t-alpha";
const BETA = "t-beta";

function req(method, path, { token, body } = {}) {
  const headers = { "content-type": "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  return new Request(`http://localhost${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function post(token, to, bodyText, extra = {}) {
  const res = await SELF.fetch(
    req("POST", "/v1/messages", {
      token,
      body: { to, body: bodyText, kind: extra.kind, reply_to: extra.reply_to, id: extra.id, from: extra.from },
    }),
  );
  return res;
}

async function read(token, after, wait = 0) {
  const res = await SELF.fetch(req("GET", `/v1/messages?after=${after}&wait=${wait}`, { token }));
  expect(res.status).toBe(200);
  return res.json();
}

describe("auth", () => {
  it("rejects missing and unknown tokens", async () => {
    expect((await SELF.fetch(req("GET", "/v1/messages?after=0"))).status).toBe(401);
    expect((await SELF.fetch(req("GET", "/v1/messages?after=0", { token: "nope" }))).status).toBe(401);
    expect((await SELF.fetch(req("POST", "/v1/ack", { token: "nope", body: { cursor: 0 } }))).status).toBe(401);
  });

  it("rejects reading another machine's stream by name", async () => {
    const res = await SELF.fetch(req("GET", "/v1/messages?after=0&machine=beta", { token: ALPHA }));
    expect(res.status).toBe(403);
  });
});

describe("delivery", () => {
  it("delivers A->B, stamps from.machine from the token, filters per machine", async () => {
    const res = await post(ALPHA, { machine: "beta", tag: "zc-bus-design" }, "hello from alpha", {
      from: { machine: "spoofed", tag: "zc-bus-design" },
    });
    expect(res.status).toBe(201);
    const { message } = await res.json();
    expect(message.from.machine).toBe("alpha"); // token wins over the client claim
    expect(message.seq).toBeGreaterThan(0);

    const betaView = await read(BETA, 0);
    const seen = betaView.messages.find((m) => m.id === message.id);
    expect(seen.body).toBe("hello from alpha");
    expect(betaView.cursor).toBeGreaterThanOrEqual(message.seq);

    const alphaView = await read(ALPHA, 0);
    expect(alphaView.messages.find((m) => m.id === message.id)).toBeUndefined();
  });

  it("broadcasts to every machine when to.machine is absent", async () => {
    const res = await post(ALPHA, { tag: "everyone" }, "standup in 5");
    const { message } = await res.json();
    for (const token of [ALPHA, BETA]) {
      const view = await read(token, 0);
      expect(view.messages.find((m) => m.id === message.id)).toBeDefined();
    }
  });

  it("advances the cursor past messages for other machines", async () => {
    await post(ALPHA, { machine: "beta", tag: "b" }, "only for beta");
    const alphaView = await read(ALPHA, 0);
    // Targeted traffic for beta never reaches alpha; a broadcast earlier in this
    // shared channel legitimately does, so assert on the specific message.
    expect(alphaView.messages.find((m) => m.body === "only for beta")).toBeUndefined();
    expect(alphaView.cursor).toBeGreaterThan(0); // skipped, not re-scanned forever
  });
});

describe("dedup and validation", () => {
  it("returns the stored envelope for a resent client id", async () => {
    const id = "b-test-dedup-1";
    const first = await (await post(ALPHA, { machine: "beta", tag: "b" }, "once", { id })).json();
    const second = await (await post(ALPHA, { machine: "beta", tag: "b" }, "once", { id })).json();
    expect(second.duplicate).toBe(true);
    expect(second.message.seq).toBe(first.message.seq);

    const betaView = await read(BETA, 0);
    expect(betaView.messages.filter((m) => m.id === id)).toHaveLength(1);
  });

  it("validates kind, body, and size", async () => {
    expect((await post(ALPHA, { machine: "beta", tag: "b" }, "x", { kind: "gossip" })).status).toBe(400);
    expect((await post(ALPHA, { machine: "beta", tag: "b" }, "")).status).toBe(400);
    const big = "x".repeat(64 * 1024 + 1);
    const res = await SELF.fetch(
      req("POST", "/v1/messages", { token: ALPHA, body: { to: { machine: "beta" }, body: big } }),
    );
    expect(res.status).toBe(413);
  });
});

describe("stored-then-lost reply (codex C-1327)", () => {
  it("dedups a blind resend after a lost 200 to the same seq", async () => {
    const id = "b-test-lost-200-1";
    // The bus stores the message, but the client never observes the 200
    // (connection cut after commit): it resends blind with the SAME id.
    const first = await post(ALPHA, { machine: "beta", tag: "b" }, "lost-200 ping", { id });
    expect(first.status).toBe(201);
    const resend = await (await post(ALPHA, { machine: "beta", tag: "b" }, "lost-200 ping", { id })).json();
    expect(resend.duplicate).toBe(true);
    expect(resend.message.id).toBe(id);
    expect(resend.message.seq).toBe((await first.json()).message.seq);

    // Exactly one copy reaches the target machine, under the original seq.
    const betaView = await read(BETA, 0);
    const copies = betaView.messages.filter((m) => m.id === id);
    expect(copies).toHaveLength(1);
    expect(copies[0].seq).toBe(resend.message.seq);
  });
});

describe("acl: machine identity (codex C-1327)", () => {
  it("re-stamps a forged from.machine with the token's machine", async () => {
    const res = await post(ALPHA, { machine: "beta", tag: "zc-bus-design" }, "spoof attempt", {
      from: { machine: "beta", tag: "claude-principal" },
    });
    expect(res.status).toBe(201); // accepted, but stamped — never rejected silently
    const { message } = await res.json();
    expect(message.from.machine).toBe("alpha");
    expect(message.from.tag).toBe("claude-principal"); // display tag may pass; machine may not

    const betaView = await read(BETA, 0);
    const seen = betaView.messages.find((m) => m.id === message.id);
    expect(seen.from.machine).toBe("alpha");
  });

  it("binds ack to the token's machine, ignoring a client machine claim", async () => {
    const res = await SELF.fetch(
      req("POST", "/v1/ack", { token: ALPHA, body: { cursor: 3, machine: "beta" } }),
    );
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ ok: true, machine: "alpha", cursor: 3 });
  });
});

describe("ack", () => {
  it("records a per-machine cursor", async () => {
    const res = await SELF.fetch(req("POST", "/v1/ack", { token: BETA, body: { cursor: 7 } }));
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ ok: true, machine: "beta", cursor: 7 });
    const bad = await SELF.fetch(req("POST", "/v1/ack", { token: BETA, body: { cursor: -1 } }));
    expect(bad.status).toBe(400);
  });
});

describe("ordering", () => {
  it("delivers queued messages in bus seq order", async () => {
    const a = await (await post(ALPHA, { machine: "beta", tag: "b" }, "first")).json();
    const b = await (await post(ALPHA, { machine: "beta", tag: "b" }, "second")).json();
    expect(b.message.seq).toBe(a.message.seq + 1);
    const betaView = await read(BETA, 0);
    const texts = betaView.messages.filter((m) => m.body === "first" || m.body === "second").map((m) => m.body);
    expect(texts).toEqual(["first", "second"]);
  });
});
