import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { ADMIN_TOKEN, RUNNER_TOKEN, SIDECAR_TOKEN, sidecarCommit } from "./helpers.js";

const ADMIN = "test-admin-token";
const RUNNER = "test-runner-token";

interface CreatedTask {
  taskId: string;
  agentId: string;
  fork: { name: string };
  token: { plaintext: string };
  head: string | null;
}

async function createTask(agent: string): Promise<CreatedTask> {
  const response = await post("/tasks", { agent }, ADMIN);
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
