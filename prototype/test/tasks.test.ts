import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

/** Contract additions needed by L2/L4 (codex C-1306). */
const ADMIN = "test-admin-token";
const RUNNER = "test-runner-token";

async function post(path: string, body: unknown, token?: string): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) {
    headers.authorization = `Bearer ${token}`;
  }
  return SELF.fetch(`http://localhost${path}`, { method: "POST", headers, body: JSON.stringify(body) });
}

async function get(path: string): Promise<Response> {
  return SELF.fetch(`http://localhost${path}`);
}

async function json<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

interface CreatedTask {
  taskId: string;
  agentId: string;
  head: string | null;
  base_sha: string;
  intent: string | null;
}

describe("task contract additions (codex C-1306)", () => {
  it("records base_sha (canonical head) and intent on task creation", async () => {
    const response = await post("/tasks", { agent: "story", intent: "fix login redirect loop" }, ADMIN);
    expect(response.status).toBe(201);
    const created = await json<CreatedTask>(response);
    expect(created.intent).toBe("fix login redirect loop");
    expect(created.base_sha).toMatch(/^[0-9a-f]{40}$/);
    expect(created.base_sha).toBe(created.head);
  });

  it("accepts an explicit base_sha that exists in canonical history", async () => {
    const first = await json<CreatedTask>(await post("/tasks", { agent: "based" }, ADMIN));
    const second = await json<CreatedTask>(
      await post("/tasks", { agent: "based2", base_sha: first.base_sha }, ADMIN),
    );
    expect(second.base_sha).toBe(first.base_sha);
    expect(second.head).toBe(first.base_sha);

    const bogus = await post("/tasks", { agent: "based3", base_sha: "f".repeat(40) }, ADMIN);
    expect(bogus.status).toBe(400);
    const malformed = await post("/tasks", { agent: "based4", base_sha: "not-a-sha" }, ADMIN);
    expect(malformed.status).toBe(400);
  });

  it("GET /tasks/:id returns base_sha, intent, head, pushes, warnings+acks, testProvenance", async () => {
    const created = await json<CreatedTask>(
      await post("/tasks", { agent: "detail", intent: "ship the review screen" }, ADMIN),
    );
    const detail = await json<{
      taskId: string;
      agentId: string;
      base_sha: string;
      intent: string | null;
      head: string | null;
      pushes: number;
      warnings: { id: string; status: string; acks: { agent: string; head: string | null; note?: string; at: string }[] }[];
      testProvenance: { command: string; exit: number; head_sha: string; at: string } | null;
    }>(await get(`/tasks/${created.taskId}`));
    expect(detail.base_sha).toBe(created.base_sha);
    expect(detail.intent).toBe("ship the review screen");
    expect(detail.head).toBe(created.head);
    expect(detail.pushes).toBe(0);
    expect(detail.warnings).toEqual([]);
    expect(detail.testProvenance).toBeNull();
  });

  it("POST /tasks/:id/tests records test provenance against a real fork head", async () => {
    const created = await json<CreatedTask>(await post("/tasks", { agent: "provenance" }, ADMIN));
    const head = created.head!;

    const bad = await post(`/tasks/${created.taskId}/tests`, { command: "npm test", exit: 0, head_sha: "zz" });
    expect(bad.status).toBe(400);
    const missing = await post("/tasks/task-9999/tests", { command: "npm test", exit: 0, head_sha: head });
    expect(missing.status).toBe(404);

    const ok = await post(`/tasks/${created.taskId}/tests`, {
      command: "npm test",
      exit: 0,
      head_sha: head,
    });
    expect(ok.status).toBe(201);
    const stored = await json<{ testProvenance: { command: string; exit: number; head_sha: string; at: string } }>(ok);
    expect(stored.testProvenance.command).toBe("npm test");
    expect(stored.testProvenance.exit).toBe(0);
    expect(stored.testProvenance.head_sha).toBe(head);
    expect(stored.testProvenance.at).toBeTruthy();

    const detail = await json<{ testProvenance: { command: string } | null }>(
      await get(`/tasks/${created.taskId}`),
    );
    expect(detail.testProvenance?.command).toBe("npm test");
  });

  it("POST /warnings/:id/ack records who acknowledged which warning at which head", async () => {
    const alpha = await json<CreatedTask>(await post("/tasks", { agent: "ack-a" }, ADMIN));
    const beta = await json<CreatedTask>(await post("/tasks", { agent: "ack-b" }, ADMIN));
    await post("/events/push", { agent: alpha.agentId, sha: "4".repeat(40) });
    await post("/events/push", { agent: beta.agentId, sha: "5".repeat(40) });

    const checked = await json<{ createdWarnings: { id: string }[] }>(
      await post(
        "/checks",
        { policy: "p", results: [{ pair: [alpha.agentId, beta.agentId], status: "conflict", kind: "merge-conflict" }] },
        RUNNER,
      ),
    );
    const warningId = checked.createdWarnings[0].id;

    const badAgent = await post(`/warnings/${warningId}/ack`, { agent: "nobody" });
    expect(badAgent.status).toBe(400);
    const badWarning = await post("/warnings/warn-999999/ack", { agent: alpha.agentId });
    expect(badWarning.status).toBe(404);

    const acked = await json<{ warning: { acks: { agent: string; head: string | null; note?: string }[] } }>(
      await post(`/warnings/${warningId}/ack`, { agent: alpha.agentId, note: "rebase in progress" }),
    );
    expect(acked.warning.acks).toHaveLength(1);
    expect(acked.warning.acks[0].agent).toBe(alpha.agentId);
    expect(acked.warning.acks[0].head).toBe("4".repeat(40));
    expect(acked.warning.acks[0].note).toBe("rebase in progress");

    const betaDetail = await json<{ warnings: { id: string; acks: { agent: string }[] }[] }>(
      await get(`/tasks/${beta.taskId}`),
    );
    const mine = betaDetail.warnings.find((w) => w.id === warningId);
    expect(mine?.acks.map((a) => a.agent)).toEqual([alpha.agentId]);
  });
});
