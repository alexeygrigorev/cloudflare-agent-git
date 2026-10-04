import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { ADMIN_TOKEN, RUNNER_TOKEN, SIDECAR_TOKEN, sidecarCommit } from "./helpers.js";

const ADMIN = "test-admin-token";
const RUNNER = "test-runner-token";

interface CreatedTask {
  taskId: string;
  agentId: string;
  fork: { name: string };
  token: { plaintext: string; expiresAt: string };
  head: string | null;
}

async function createTask(agent: string): Promise<CreatedTask> {
  const response = await post("/tasks", { agent }, ADMIN);
  expect(response.status).toBe(201);
  return (await response.json()) as CreatedTask;
}

/** ttlSeconds flows to the sidecar unvalidated, so a NEGATIVE ttl mints an
 * already-expired token — the deterministic way to exercise the expiry gate. */
async function createTaskWithTtl(agent: string, ttlSeconds: number): Promise<CreatedTask> {
  const response = await post("/tasks", { agent, ttlSeconds }, ADMIN);
  expect(response.status).toBe(201);
  return (await response.json()) as CreatedTask;
}

function post(path: string, body: unknown, token?: string): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) {
    headers.authorization = `Bearer ${token}`;
  }
  return SELF.fetch(`http://localhost${path}`, { method: "POST", headers, body: JSON.stringify(body) });
}

async function bodyText(response: Response): Promise<string> {
  return await response.text();
}

describe("auth (codex C-1305 #3)", () => {
  it("POST /tasks requires the admin bearer token", async () => {
    const noToken = await post("/tasks", { agent: "authless" });
    expect(noToken.status).toBe(401);

    const wrongToken = await post("/tasks", { agent: "authless" }, "definitely-not-the-admin-token");
    expect(wrongToken.status).toBe(401);

    // Never echo the presented token in the error body.
    const text = await bodyText(wrongToken);
    expect(text).not.toContain("definitely-not-the-admin-token");

    const rightToken = await post("/tasks", { agent: "authok" }, ADMIN);
    expect(rightToken.status).toBe(201);
  });

  it("POST /setup requires the admin bearer token", async () => {
    const denied = await post("/setup", {});
    expect(denied.status).toBe(401);
    const allowed = await post("/setup", {}, ADMIN);
    expect(allowed.status).toBe(201);
  });

  it("the admin token does not grant the runner route and vice versa", async () => {
    const adminOnRunner = await post("/checks", { policy: "p", results: [] }, ADMIN);
    expect(adminOnRunner.status).toBe(401);

    const noToken = await post("/checks", { policy: "p", results: [] });
    expect(noToken.status).toBe(401);

    // Correct runner token passes auth (then fails on the empty body shape).
    const runnerOk = await post("/checks", { policy: "p" }, RUNNER);
    expect(runnerOk.status).toBe(400);
  });

  it("401 bodies never contain the presented token", async () => {
    const secretAttempt = "art_v1_leaked_attempt_0000000000000000000000";
    const response = await post("/tasks", { agent: "x" }, secretAttempt);
    expect(response.status).toBe(401);
    const text = await bodyText(response);
    expect(text).not.toContain(secretAttempt);
  });

  it("read routes stay open", async () => {
    const status = await SELF.fetch("http://localhost/status");
    expect(status.status).toBe(200);
  });
});

describe("auth on mutating routes (muse-r46 AUTH, CONTRACT 0.1.1)", () => {
  it("POST /events/push requires the pushing agent's task token, admin or the sidecar webhook bearer", async () => {
    const alice = await createTask("auth-push-a");
    const bob = await createTask("auth-push-b");
    const sha = await sidecarCommit(alice.fork.name, "wip: authed push");

    const noToken = await post("/events/push", { agent: alice.agentId, sha });
    expect(noToken.status).toBe(401);

    const crossAgent = await post("/events/push", { agent: alice.agentId, sha }, bob.token.plaintext);
    expect(crossAgent.status).toBe(403);

    const ownToken = await post("/events/push", { agent: alice.agentId, sha }, alice.token.plaintext);
    expect(ownToken.status).toBe(200);

    // The sidecar post-receive webhook posts the fork shape with the shared bearer.
    const sha2 = await sidecarCommit(bob.fork.name, "wip: webhook push");
    const webhook = await post(
      "/events/push",
      { fork: bob.fork.name, ref: "refs/heads/main", sha: sha2 },
      SIDECAR_TOKEN,
    );
    expect(webhook.status).toBe(200);
    const webhookBody = (await webhook.json()) as { agent: string };
    expect(webhookBody.agent).toBe(bob.agentId);

    const webhookNoToken = await post("/events/push", { fork: bob.fork.name, sha });
    expect(webhookNoToken.status).toBe(401);
  });

  it("POST /tasks/:id/tests rejects evidence forgery: another agent's token is 403 (muse-r46 a.2)", async () => {
    const owner = await createTask("auth-tests-owner");
    const attacker = await createTask("auth-tests-attacker");

    const noToken = await post(`/tasks/${owner.taskId}/tests`, {
      command: "npm test",
      exit: 0,
      head_sha: owner.head!,
    });
    expect(noToken.status).toBe(401);

    const forged = await post(
      `/tasks/${owner.taskId}/tests`,
      { command: "npm test", exit: 0, head_sha: owner.head! },
      attacker.token.plaintext,
    );
    expect(forged.status).toBe(403);
    // Nothing was recorded by the rejected attempts.
    const detail = await (await SELF.fetch(`http://localhost/tasks/${owner.taskId}`)).json() as {
      testProvenance: unknown;
    };
    expect(detail.testProvenance).toBeNull();

    const own = await post(
      `/tasks/${owner.taskId}/tests`,
      { command: "npm test", exit: 0, head_sha: owner.head! },
      owner.token.plaintext,
    );
    expect(own.status).toBe(201);
    const viaAdmin = await post(
      `/tasks/${owner.taskId}/tests`,
      { command: "npm test", exit: 1, head_sha: owner.head! },
      ADMIN,
    );
    expect(viaAdmin.status).toBe(201);
  });

  it("POST /warnings/:id/ack rejects cross-agent acks (agent A cannot ack as agent B)", async () => {
    const alice = await createTask("auth-ack-a");
    const bob = await createTask("auth-ack-b");
    const aliceSha = await sidecarCommit(alice.fork.name, "wip: alice conflict");
    const bobSha = await sidecarCommit(bob.fork.name, "wip: bob conflict");
    await post("/events/push", { agent: alice.agentId, sha: aliceSha }, alice.token.plaintext);
    await post("/events/push", { agent: bob.agentId, sha: bobSha }, bob.token.plaintext);
    const status = (await (await SELF.fetch("http://localhost/status")).json()) as { heads: Record<string, string> };
    const checked = await post(
      "/checks",
      {
        contract: "0.0",
        vector: status.heads,
        policy: "p",
        results: [{ pair: [alice.agentId, bob.agentId], status: "conflict", kind: "merge-conflict" }],
      },
      RUNNER,
    );
    const warningId = ((await checked.json()) as { createdWarnings: { id: string }[] }).createdWarnings[0].id;

    const noToken = await post(`/warnings/${warningId}/ack`, { agent: alice.agentId });
    expect(noToken.status).toBe(401);

    const crossAgent = await post(`/warnings/${warningId}/ack`, { agent: bob.agentId }, alice.token.plaintext);
    expect(crossAgent.status).toBe(403);

    const own = await post(`/warnings/${warningId}/ack`, { agent: alice.agentId }, alice.token.plaintext);
    expect(own.status).toBe(200);

    const asAdmin = await post(`/warnings/${warningId}/ack`, { agent: bob.agentId, note: "triaged by admin" }, ADMIN);
    expect(asAdmin.status).toBe(200);
  });

  it("POST /events/artifacts requires admin or the sidecar webhook bearer", async () => {
    const event = {
      type: "cf.artifacts.repo.pushed",
      source: { type: "artifacts.repo", namespace: "local", repoName: "who-knows" },
      payload: { ref: "refs/heads/main", after: "a".repeat(40) },
    };
    const noToken = await post("/events/artifacts", event);
    expect(noToken.status).toBe(401);
    const sidecar = await post("/events/artifacts", event, SIDECAR_TOKEN);
    expect(sidecar.status).toBe(202);
    const admin = await post("/events/artifacts", event, ADMIN);
    expect(admin.status).toBe(202);
  });
});

describe("token expiry & revocation gate (C-1422/C-1425)", () => {
  it("an expired task token is rejected on POST /events/push with 401", async () => {
    const expired = await createTaskWithTtl("cred-gate-expired", -10);
    expect(Date.parse(expired.token.expiresAt)).toBeLessThan(Date.now());

    // An unexpired valid token still succeeds (gate does not over-reject).
    const valid = await createTask("cred-gate-valid");
    const validSha = await sidecarCommit(valid.fork.name, "wip: unexpired token push");
    const validPush = await post("/events/push", { agent: valid.agentId, sha: validSha }, valid.token.plaintext);
    expect(validPush.status).toBe(200);

    const expiredSha = await sidecarCommit(expired.fork.name, "wip: expired token push");
    const denied = await post("/events/push", { agent: expired.agentId, sha: expiredSha }, expired.token.plaintext);
    expect(denied.status).toBe(401);
    const text = await bodyText(denied);
    expect(text).not.toContain(expired.token.plaintext);

    // The admin override is unaffected by the agent token's expiry.
    const adminPush = await post("/events/push", { agent: expired.agentId, sha: expiredSha }, ADMIN);
    expect(adminPush.status).toBe(200);
  });

  it("POST /tasks/:id/revoke (ADMIN_TOKEN only) revokes the agent token; later pushes are 401", async () => {
    const agent = await createTask("cred-gate-revoke");
    const shaBefore = await sidecarCommit(agent.fork.name, "wip: before revoke");
    const before = await post("/events/push", { agent: agent.agentId, sha: shaBefore }, agent.token.plaintext);
    expect(before.status).toBe(200);

    // Revocation is an admin control: no token and the agent's own token are 401.
    const noToken = await post(`/tasks/${agent.taskId}/revoke`, {});
    expect(noToken.status).toBe(401);
    const selfRevoked = await post(`/tasks/${agent.taskId}/revoke`, {}, agent.token.plaintext);
    expect(selfRevoked.status).toBe(401);

    const revoked = await post(`/tasks/${agent.taskId}/revoke`, {}, ADMIN);
    expect(revoked.status).toBe(200);
    const revokedBody = (await revoked.json()) as { taskId: string; agentId: string; revoked: boolean };
    expect(revokedBody).toMatchObject({ taskId: agent.taskId, agentId: agent.agentId, revoked: true });

    const unknown = await post("/tasks/task-9999/revoke", {}, ADMIN);
    expect(unknown.status).toBe(404);

    // The SAME plaintext now fails: revocation is recorded against the
    // agent's token record, not the presented credential.
    const shaAfter = await sidecarCommit(agent.fork.name, "wip: after revoke");
    const after = await post("/events/push", { agent: agent.agentId, sha: shaAfter }, agent.token.plaintext);
    expect(after.status).toBe(401);

    // Revocation is idempotent and the admin path still works.
    const again = await post(`/tasks/${agent.taskId}/revoke`, {}, ADMIN);
    expect(again.status).toBe(200);
  });

  it("expired and revoked tokens are rejected on POST /warnings/:id/ack with 401", async () => {
    const alice = await createTask("cred-gate-ack-a");
    const bob = await createTask("cred-gate-ack-b");
    const aliceSha = await sidecarCommit(alice.fork.name, "wip: cred gate conflict a");
    const bobSha = await sidecarCommit(bob.fork.name, "wip: cred gate conflict b");
    await post("/events/push", { agent: alice.agentId, sha: aliceSha }, alice.token.plaintext);
    await post("/events/push", { agent: bob.agentId, sha: bobSha }, bob.token.plaintext);
    const status = (await (await SELF.fetch("http://localhost/status")).json()) as { heads: Record<string, string> };
    const checked = await post(
      "/checks",
      {
        contract: "0.0",
        vector: status.heads,
        policy: "p",
        results: [{ pair: [alice.agentId, bob.agentId], status: "conflict", kind: "merge-conflict" }],
      },
      RUNNER,
    );
    const warningId = ((await checked.json()) as { createdWarnings: { id: string }[] }).createdWarnings[0].id;

    const expired = await createTaskWithTtl("cred-gate-ack-expired", -10);
    const expiredAck = await post(`/warnings/${warningId}/ack`, { agent: expired.agentId }, expired.token.plaintext);
    expect(expiredAck.status).toBe(401);

    const revokedAgent = await createTask("cred-gate-ack-revoked");
    const revoke = await post(`/tasks/${revokedAgent.taskId}/revoke`, {}, ADMIN);
    expect(revoke.status).toBe(200);
    const revokedAck = await post(
      `/warnings/${warningId}/ack`,
      { agent: revokedAgent.agentId },
      revokedAgent.token.plaintext,
    );
    expect(revokedAck.status).toBe(401);

    // A valid unexpired token for the acking agent still succeeds.
    const own = await post(`/warnings/${warningId}/ack`, { agent: alice.agentId }, alice.token.plaintext);
    expect(own.status).toBe(200);
  });
});

describe("bounded invalid-bearer rate limiter (C-1441)", () => {
  it("returns 429 with Retry-After on the 6th consecutive invalid bearer; valid tokens pass", async () => {
    // Reset this isolate's failure count: a successful admin auth clears
    // any 401s earlier tests in this file accumulated for our client key.
    const reset = await post("/tasks", { agent: "limiter-reset" }, ADMIN);
    expect(reset.status).toBe(201);

    for (let i = 0; i < 5; i++) {
      const response = await post("/tasks", { agent: "limiter-abuse" }, `limiter-wrong-token-${i}`);
      expect(response.status).toBe(401);
    }
    const blocked = await post("/tasks", { agent: "limiter-abuse" }, "limiter-wrong-token-5");
    expect(blocked.status).toBe(429);
    expect(blocked.headers.get("retry-after")).toBe("60");
    const blockedText = await blocked.text();
    expect(JSON.parse(blockedText)).toEqual({
      error: "rate_limited",
      message: "Too many failed authentication attempts. Please retry later.",
    });
    // The 429 body never echoes the presented (wrong) token.
    expect(blockedText).not.toContain("limiter-wrong-token-5");

    // A valid credential is never rate limited — and clears the count.
    const valid = await post("/tasks", { agent: "limiter-legit" }, ADMIN);
    expect(valid.status).toBe(201);

    // After the success, an invalid bearer is a plain 401 again.
    const after = await post("/tasks", { agent: "limiter-abuse" }, "limiter-wrong-token-6");
    expect(after.status).toBe(401);
  });

  it("spoofed forwarding headers do not bypass the limiter (C-1441 B1, REV-LIMITER M10)", async () => {
    const postAs = (ip: string | null, xff: string | null, token: string): Promise<Response> => {
      const headers: Record<string, string> = { "content-type": "application/json" };
      if (ip) {
        headers["cf-connecting-ip"] = ip;
      }
      if (xff) {
        headers["x-forwarded-for"] = xff;
      }
      headers.authorization = `Bearer ${token}`;
      return SELF.fetch("http://localhost/setup", { method: "POST", headers, body: "{}" });
    };

    // (a) One edge-identified client rotating X-Forwarded-For per attempt:
    // XFF must NOT be the key, so the 6th attempt is 429. A mutant keying
    // the limiter on XFF would spread these over six buckets and answer
    // 401 forever — the silent full bypass.
    for (let i = 0; i < 5; i++) {
      const response = await postAs("203.0.113.50", `203.0.113.${100 + i}`, "wrong-token");
      expect(response.status).toBe(401);
    }
    const blocked = await postAs("203.0.113.50", "203.0.113.199", "wrong-token");
    expect(blocked.status).toBe(429);

    // (b) Distinct edge-identified clients are isolated buckets: all stay
    // 401. A mutant keying on XFF — absent here — would collapse them into
    // the shared unknown bucket and 429 the 6th instead.
    for (let i = 0; i < 6; i++) {
      const isolated = await postAs(`203.0.113.${60 + i}`, null, "wrong-token");
      expect(isolated.status).toBe(401);
    }

    // (c) The flood on .50 does not lock out a different edge-identified
    // client: bucket isolation is real in both directions.
    const otherClient = await postAs("203.0.113.71", null, "wrong-token");
    expect(otherClient.status).toBe(401);
  });
});
