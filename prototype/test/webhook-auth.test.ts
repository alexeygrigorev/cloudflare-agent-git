import { env, SELF } from "cloudflare:test";
import { afterAll, describe, expect, it } from "vitest";
import { signWebhookPayload, WEBHOOK_REPLAY_WINDOW_SECONDS } from "../src/webhook.js";
import { SIDECAR_TOKEN } from "./helpers.js";

const SECRET = "test-events-webhook-secret-0123456789abcdef";
const EVENT = {
  type: "cf.artifacts.repo.pushed",
  source: { type: "artifacts.repo", namespace: "local", repoName: "who-knows" },
  payload: { ref: "refs/heads/main", after: "a".repeat(40) },
};

interface PostOpts {
  token?: string;
  timestamp?: string;
  signature?: string;
}

async function postEvents(path: string, raw: string, opts: PostOpts = {}): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (opts.token) {
    headers.authorization = `Bearer ${opts.token}`;
  }
  if (opts.timestamp !== undefined) {
    headers["x-webhook-timestamp"] = opts.timestamp;
  }
  if (opts.signature !== undefined) {
    headers["x-webhook-signature"] = opts.signature;
  }
  return SELF.fetch(`http://localhost${path}`, { method: "POST", headers, body: raw });
}

async function postSigned(
  path: string,
  payload: unknown,
  secret: string,
  opts: PostOpts & { timestampValue?: string } = {},
): Promise<Response> {
  const raw = JSON.stringify(payload);
  const timestamp = opts.timestampValue ?? String(Math.floor(Date.now() / 1000));
  const signature = await signWebhookPayload(secret, timestamp, raw);
  return postEvents(path, raw, { ...opts, timestamp, signature });
}

describe("/events/* webhook authenticity (PLAN-L1-REAL §5.1)", () => {
  afterAll(() => {
    delete (env as unknown as Record<string, unknown>).EVENTS_WEBHOOK_SECRET;
    delete (env as unknown as Record<string, unknown>).ARTIFACTS_NAMESPACE;
  });

  it("with EVENTS_WEBHOOK_SECRET set: unsigned, wrong-secret and stale deliveries are 401; a valid signed one passes", async () => {
    (env as unknown as Record<string, unknown>).EVENTS_WEBHOOK_SECRET = SECRET;

    // The shared bearer ALONE is no longer sufficient while the secret is set.
    const unsigned = await postEvents("/events/artifacts", JSON.stringify(EVENT), { token: SIDECAR_TOKEN });
    expect(unsigned.status).toBe(401);

    const wrongSecret = await postSigned("/events/artifacts", EVENT, "not-the-secret", { token: SIDECAR_TOKEN });
    expect(wrongSecret.status).toBe(401);

    const replayed = await postSigned("/events/artifacts", EVENT, SECRET, {
      token: SIDECAR_TOKEN,
      timestampValue: String(Math.floor(Date.now() / 1000) - WEBHOOK_REPLAY_WINDOW_SECONDS - 30),
    });
    expect(replayed.status).toBe(401);

    const future = await postSigned("/events/artifacts", EVENT, SECRET, {
      token: SIDECAR_TOKEN,
      timestampValue: String(Math.floor(Date.now() / 1000) + WEBHOOK_REPLAY_WINDOW_SECONDS + 30),
    });
    expect(future.status).toBe(401);

    // Valid signature + valid bearer: authenticated, unknown fork → 202 accepted:false.
    const ok = await postSigned("/events/artifacts", EVENT, SECRET, { token: SIDECAR_TOKEN });
    expect(ok.status).toBe(202);
    expect(((await ok.json()) as { accepted: boolean }).accepted).toBe(false);

    // The same gate guards /events/push.
    const pushUnsigned = await postEvents(
      "/events/push",
      JSON.stringify({ fork: "no-such-fork", sha: "b".repeat(40) }),
      { token: SIDECAR_TOKEN },
    );
    expect(pushUnsigned.status).toBe(401);
    const pushOk = await postSigned(
      "/events/push",
      { fork: "no-such-fork", sha: "b".repeat(40) },
      SECRET,
      { token: SIDECAR_TOKEN },
    );
    // Signature accepted; the unknown fork itself fails downstream (unknown agent → 404/400).
    expect(pushOk.status).not.toBe(401);
  });

  it("without EVENTS_WEBHOOK_SECRET the routes keep the CONTRACT bearer-only posture", async () => {
    delete (env as unknown as Record<string, unknown>).EVENTS_WEBHOOK_SECRET;
    const res = await postEvents("/events/artifacts", JSON.stringify(EVENT), { token: SIDECAR_TOKEN });
    expect(res.status).toBe(202);
  });

  it("§5.8 source allowlist: events from a foreign namespace are 403 even when authenticated", async () => {
    (env as unknown as Record<string, unknown>).ARTIFACTS_NAMESPACE = "agent-branches-prod";
    const wrong = await postEvents("/events/artifacts", JSON.stringify(EVENT), { token: SIDECAR_TOKEN });
    expect(wrong.status).toBe(403);

    const right = await postEvents(
      "/events/artifacts",
      JSON.stringify({ ...EVENT, source: { ...EVENT.source, namespace: "agent-branches-prod" } }),
      { token: SIDECAR_TOKEN },
    );
    expect(right.status).toBe(202);
  });
});
