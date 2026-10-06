import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { ADMIN_TOKEN, RUNNER_TOKEN, sidecarCommit } from "./helpers.js";

/**
 * C1474 real fork adoption loop, automated for CI (live counterpart:
 * research/antigravity/adoption/REAL-FORK-ADOPTION-REPORT.md, run of
 * 2026-10-04 against src/local on this checkout). The full agent
 * workflow a real executor performs: create tasks -> hold fork +
 * per-task write token -> advance the fork -> push report under the
 * agent's own token -> trusted runner re-fetches status and submits a
 * canonical 0.1 check -> pair goes clean. Within the workerd lane the
 * "ordinary git push" leg is the sidecar's real-git commit API plus the
 * agent-token push report; ordinary-git-client behavior itself is proven
 * by local-artifacts/*.test.mjs and by the live report. Known CI lane
 * limits (disclosed in the report's coverage section): commits are
 * tree-identical (sidecar commit API has no content input), the
 * sidecar->coordinator webhook forward is replaced by direct agent push
 * reports, and policy.tests.command is runner-self-attested by design —
 * the coordinator stores claims, it does not execute tests.
 */

interface CreatedTask {
  taskId: string;
  agentId: string;
  fork: { name: string; remote: string };
  ref: string;
  base_sha: string;
  intent: string | null;
  head: string | null;
  token: { scope: string; expiresAt: string; plaintext: string };
}

async function post(path: string, body: unknown, token?: string): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  return SELF.fetch(`http://localhost${path}`, { method: "POST", headers, body: JSON.stringify(body) });
}

async function get(path: string): Promise<Response> {
  return SELF.fetch(`http://localhost${path}`, { headers: { authorization: `Bearer ${ADMIN_TOKEN}` } });
}

describe("C1474 real fork adoption loop", () => {
  it("runs setup -> tasks -> fork edits -> agent push -> runner check -> clean pair", async () => {
    // 1. Canonical repo (idempotent once created).
    const setup = await post("/setup", {}, ADMIN_TOKEN);
    expect(setup.status).toBe(201);

    // 2. Two agent tasks: fork remote + per-task write token per agent.
    const createdA = await post(
      "/tasks",
      { agent: "adopt-e2e-a", intent: "C1474 adoption: agent A edit" },
      ADMIN_TOKEN,
    );
    expect(createdA.status).toBe(201);
    const taskA = (await createdA.json()) as CreatedTask;
    const createdB = await post(
      "/tasks",
      { agent: "adopt-e2e-b", intent: "C1474 adoption: agent B edit" },
      ADMIN_TOKEN,
    );
    expect(createdB.status).toBe(201);
    const taskB = (await createdB.json()) as CreatedTask;

    // Payload integrity: fork, ref, base head, write-scope token.
    for (const task of [taskA, taskB]) {
      expect(task.fork.remote).toMatch(/^http:\/\/.+\.git$/);
      expect(task.ref).toBe("refs/heads/main");
      expect(task.base_sha).toMatch(/^[0-9a-f]{40}$/);
      expect(task.head).toBe(task.base_sha);
      expect(task.token.scope).toBe("write");
      expect(task.token.plaintext).toMatch(/^art_v1_/);
    }
    expect(taskA.agentId).not.toBe(taskB.agentId);

    // 3. Each agent advances its fork with a REAL commit in a REAL bare
    // repo (sidecar git plumbing = the durable effect of a git push).
    const shaA = await sidecarCommit(taskA.fork.name, "docs: adoption edit A (C1474 CI)");
    const shaB = await sidecarCommit(taskB.fork.name, "docs: adoption edit B (C1474 CI)");
    expect(shaA).toMatch(/^[0-9a-f]{40}$/);
    expect(shaB).toMatch(/^[0-9a-f]{40}$/);

    // 4. Push reports under each agent's OWN per-task token. Cross-agent
    // use is rejected first (403), then both legit reports land (200).
    const crossAgent = await post(
      "/events/push",
      { agent: taskA.agentId, sha: shaA },
      taskB.token.plaintext,
    );
    expect(crossAgent.status).toBe(403);
    for (const [task, sha] of [
      [taskA, shaA],
      [taskB, shaB],
    ] as const) {
      const push = await post("/events/push", { agent: task.agentId, sha }, task.token.plaintext);
      expect(push.status).toBe(200);
      const body = (await push.json()) as { accepted: boolean; deduped: boolean; agent: string };
      expect(body.accepted).toBe(true);
      expect(body.agent).toBe(task.agentId);
    }

    // 5. Coordinator recorded both heads and the push provenance.
    const status = (await (await get("/status")).json()) as {
      heads: Record<string, string>;
      unprocessedPushes: unknown[];
    };
    expect(status.heads[taskA.agentId]).toBe(shaA);
    expect(status.heads[taskB.agentId]).toBe(shaB);
    expect(status.unprocessedPushes).toEqual([]);
    const detailB = await get(`/tasks/${taskB.taskId}`);
    expect(detailB.status).toBe(200);
    expect(((await detailB.json()) as { pushes: number }).pushes).toBe(1);

    // 6. Trusted runner: first submit with a PARTIAL top-level vector
    // (only agent A's head) — the stale gate demands the entire heads
    // map, so this is 409 with currentHeads for recovery (live run T12);
    // per-result heads still cover the pair (wire shape requirement) —
    // then re-fetch and submit the FULL vector, which is accepted.
    const pairHeads = { [taskA.agentId]: shaA, [taskB.agentId]: shaB };
    const staleChecks = await post(
      "/checks",
      {
        contract: "0.1",
        vector: { [taskA.agentId]: shaA },
        policy: { merge: "git-merge-tree", tests: { command: null, budget_s: 15.0 } },
        coverage: { pairs_checked: 1, tests_collected: 2 },
        results: [
          {
            pair: [taskA.agentId, taskB.agentId],
            heads: pairHeads,
            status: "clean",
            kind: "test",
            evidence: { summary: "partial vector must be rejected by the full-map stale gate" },
          },
        ],
      },
      RUNNER_TOKEN,
    );
    expect(staleChecks.status).toBe(409);
    const staleBody = (await staleChecks.json()) as {
      error?: string;
      currentHeads?: Record<string, string>;
    };
    expect(staleBody.error).toMatch(/stale vector/);
    expect(staleBody.currentHeads?.[taskA.agentId]).toBe(shaA);
    expect(staleBody.currentHeads?.[taskB.agentId]).toBe(shaB);

    const freshStatus = (await (await get("/status")).json()) as { heads: Record<string, string> };
    const runnerChecks = await post(
      "/checks",
      {
        contract: "0.1",
        vector: { ...status.heads },
        policy: { merge: "git-merge-tree", tests: { command: null, budget_s: 15.0 } },
        coverage: { pairs_checked: 1, tests_collected: 2 },
        results: [
          {
            pair: [taskA.agentId, taskB.agentId],
            heads: { [taskA.agentId]: shaA, [taskB.agentId]: shaB },
            status: "clean",
            kind: "test",
            evidence: {
              summary: "C1474 CI adoption pair: disjoint-file edits merge clean",
              files: ["README.md"],
              test_output_tail: "ok 1 - edit A present\nok 2 - edit B present",
              tests_collected: 2,
            },
          },
        ],
      },
      RUNNER_TOKEN,
    );
    expect(runnerChecks.status).toBe(200);
    const checksBody = (await runnerChecks.json()) as {
      stale: boolean;
      accepted: number;
      pairs: { pair: string[]; status: string; coverage?: { tests_collected: number } }[];
    };
    expect(checksBody.stale).toBe(false);
    expect(checksBody.accepted).toBe(1);
    const adoptedPair = checksBody.pairs.find((p) => p.pair.includes(taskA.agentId) && p.pair.includes(taskB.agentId));
    expect(adoptedPair?.status).toBe("clean");
    expect(adoptedPair?.coverage?.tests_collected).toBe(2);

    // 7. Negative gate: POST /checks requires the dedicated RUNNER_TOKEN.
    const badRunner = await post("/checks", { contract: "0.1", vector: {}, policy: {}, coverage: {}, results: [] }, "not-the-runner-token");
    expect(badRunner.status).toBe(401);
  });
});
