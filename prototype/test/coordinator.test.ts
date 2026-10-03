import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

const SHA_ALPHA_1 = "1".repeat(40);
const SHA_BETA_1 = "2".repeat(40);
const SHA_ALPHA_2 = "3".repeat(40);

async function post(path: string, body: unknown): Promise<Response> {
  return SELF.fetch(`http://localhost${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function get(path: string): Promise<Response> {
  return SELF.fetch(`http://localhost${path}`);
}

interface CreatedTask {
  taskId: string;
  agentId: string;
  fork: { name: string; remote: string };
  token: { scope: string; plaintext: string; expiresAt: string };
  head: string | null;
}

interface PushResult {
  accepted: boolean;
  deduped: boolean;
  heads: Record<string, string>;
  invalidatedWarnings: string[];
  newWarnings: { id: string; status: string; reason: string; pair: string[]; headsAtIssue: { a: string; b: string } }[];
  radarChecks: number;
}

interface StatusSnapshot {
  canonical: { name: string | null; remote: string | null };
  agents: { agentId: string; forkName: string; forkRemote: string; head: string | null; pushes: number }[];
  heads: Record<string, string>;
  warnings: { id: string; status: string; reason: string; invalidatedAt: string | null }[];
  radarLog: { pair: string[]; heads: { a: string; b: string } }[];
}

async function json<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

describe("Agent Branches coordinator flow", () => {
  it("sets up the canonical repo", async () => {
    const response = await post("/setup", {});
    expect(response.status).toBe(201);
    const body = await json<{ canonical: { name: string }; created: boolean; seedCommit: string | null }>(response);
    expect(body.canonical.name).toBe("agent-branches-canonical");
    expect(body.created).toBe(true);
    expect(body.seedCommit).toMatch(/^[0-9a-f]{40}$/);
  });

  it("creates two agent tasks as forks of canonical", async () => {
    const alpha = await post("/tasks", { agent: "alpha" });
    expect(alpha.status).toBe(201);
    const alphaBody = await json<CreatedTask>(alpha);
    expect(alphaBody.agentId).toBe("alpha-0001");
    expect(alphaBody.taskId).toBe("task-0001");
    expect(alphaBody.fork.name).toBe("agent-branches-canonical-alpha-0001");
    expect(alphaBody.fork.remote).toBe(
      "https://local.artifacts-stub.test/git/agent-branches-local/agent-branches-canonical-alpha-0001.git",
    );
    expect(alphaBody.token.scope).toBe("write");
    expect(alphaBody.token.plaintext).toMatch(/^art_v1_[0-9a-f]{40}\?expires=\d+$/);

    const beta = await post("/tasks", { agent: "beta" });
    expect(beta.status).toBe(201);
    const betaBody = await json<CreatedTask>(beta);
    expect(betaBody.agentId).toBe("beta-0002");
    expect(betaBody.head).toBe(alphaBody.head);
    expect(alphaBody.head).toMatch(/^[0-9a-f]{40}$/);
  });

  it("accepts a WIP head, updates the head vector and raises a radar warning", async () => {
    const before = await json<StatusSnapshot>(await get("/status"));
    expect(before.heads["alpha-0001"]).toBe(before.heads["beta-0002"]);

    const push = await post("/events/push", { agent: "alpha-0001", sha: SHA_ALPHA_1 });
    expect(push.status).toBe(200);
    const body = await json<PushResult>(push);
    expect(body.accepted).toBe(true);
    expect(body.deduped).toBe(false);
    expect(body.heads["alpha-0001"]).toBe(SHA_ALPHA_1);
    expect(body.radarChecks).toBe(1);
    expect(body.newWarnings).toHaveLength(1);
    expect(body.newWarnings[0].reason).toBe("heads-diverged");
    expect(body.newWarnings[0].pair).toContain("alpha-0001");

    const status = await json<StatusSnapshot>(await get("/status"));
    expect(status.heads["alpha-0001"]).toBe(SHA_ALPHA_1);
    expect(status.warnings).toHaveLength(1);
    expect(status.warnings[0].status).toBe("active");
    expect(status.radarLog[0].pair).toEqual(["alpha-0001", "beta-0002"]);
    expect(status.radarLog[0].heads).toEqual({ a: SHA_ALPHA_1, b: expect.any(String) });
  });

  it("dedups repeated pushes per (agent, sha)", async () => {
    const push = await post("/events/push", { agent: "alpha-0001", sha: SHA_ALPHA_1 });
    const body = await json<PushResult>(push);
    expect(body.accepted).toBe(true);
    expect(body.deduped).toBe(true);
    expect(body.radarChecks).toBe(0);

    const status = await json<StatusSnapshot>(await get("/status"));
    expect(status.warnings).toHaveLength(1);
    expect(status.radarLog).toHaveLength(2);
    expect(status.radarLog[0].pair).toEqual(["alpha-0001", "beta-0002"]);
    expect(status.radarLog[1].pair).toEqual(["beta-0002", "alpha-0001"]);
  });

  it("invalidates the warning when the sibling advances, then re-warns at new heads", async () => {
    const push = await post("/events/push", { agent: "beta-0002", sha: SHA_BETA_1 });
    const body = await json<PushResult>(push);
    expect(body.deduped).toBe(false);
    expect(body.heads["beta-0002"]).toBe(SHA_BETA_1);
    expect(body.invalidatedWarnings).toEqual(["warn-1"]);
    expect(body.newWarnings).toHaveLength(1);
    expect(body.newWarnings[0].id).toBe("warn-2");
    expect(body.newWarnings[0].status).toBe("active");
    expect(body.newWarnings[0].headsAtIssue).toEqual({ a: SHA_BETA_1, b: SHA_ALPHA_1 });

    const status = await json<StatusSnapshot>(await get("/status"));
    const warn1 = status.warnings.find((w) => w.id === "warn-1");
    const warn2 = status.warnings.find((w) => w.id === "warn-2");
    expect(warn1?.status).toBe("invalidated");
    expect(warn1?.invalidatedAt).toBeTruthy();
    expect(warn2?.status).toBe("active");
  });

  it("serves task details and 404s unknown tasks", async () => {
    const found = await get("/tasks/task-0001");
    expect(found.status).toBe(200);
    const body = await json<{ agentId: string; agent: { head: string | null; pushes: number } | null }>(found);
    expect(body.agentId).toBe("alpha-0001");
    expect(body.agent?.head).toBe(SHA_ALPHA_1);
    expect(body.agent?.pushes).toBe(1);

    const missing = await get("/tasks/task-9999");
    expect(missing.status).toBe(404);
  });

  it("accepts the documented cf.artifacts.repo.pushed envelope", async () => {
    const status = await json<StatusSnapshot>(await get("/status"));
    const alphaFork = status.agents.find((a) => a.forkName.includes("alpha"))!.forkName;
    const event = {
      type: "cf.artifacts.repo.pushed",
      source: { type: "artifacts.repo", namespace: "agent-branches-local", repoName: alphaFork },
      payload: {
        ref: "refs/heads/main",
        before: SHA_ALPHA_1,
        after: SHA_ALPHA_2,
        commits: [
          {
            id: SHA_ALPHA_2,
            message: "wip: more work",
            messageTruncated: false,
            timestamp: "2026-10-03T12:00:00.000Z",
            parents: [SHA_ALPHA_1],
          },
        ],
        totalCommitsCount: 1,
        commitsTruncated: false,
      },
      metadata: {
        accountId: "local",
        eventSubscriptionId: "test",
        eventSchemaVersion: 1,
        eventTimestamp: "2026-10-03T12:00:00.132Z",
      },
    };
    const response = await post("/events/artifacts", event);
    expect(response.status).toBe(200);
    const body = await json<{ accepted: boolean; deduped: boolean; heads: Record<string, string> }>(response);
    expect(body.accepted).toBe(true);
    expect(body.deduped).toBe(false);
    expect(body.heads["alpha-0001"]).toBe(SHA_ALPHA_2);

    const ignored = await post("/events/artifacts", {
      ...event,
      source: { type: "artifacts.repo", namespace: "agent-branches-local", repoName: "who-knows" },
    });
    expect(ignored.status).toBe(202);
    const ignoredBody = await json<{ accepted: boolean }>(ignored);
    expect(ignoredBody.accepted).toBe(false);
  });

  it("rejects unknown agents, wrong forks and bad bodies", async () => {
    const unknownAgent = await post("/events/push", { agent: "ghost-9999", sha: "f".repeat(40) });
    expect(unknownAgent.status).toBe(400);

    const wrongFork = await post("/events/push", {
      agent: "alpha-0001",
      fork: "somebody-elses-fork",
      sha: "e".repeat(40),
    });
    expect(wrongFork.status).toBe(400);

    const missingSha = await post("/events/push", { agent: "alpha-0001" });
    expect(missingSha.status).toBe(400);

    const noRoute = await get("/definitely/not/a/route");
    expect(noRoute.status).toBe(404);
  });
});
