import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { ADMIN_TOKEN, RUNNER_TOKEN, sidecarCommit } from "./helpers.js";

/**
 * Trusted-runner checks via POST /checks (RUNNER_TOKEN). The vector must
 * match the current head vector exactly (stale -> 409); warnings exist only
 * for status "conflict" (codex C-1305 #1 + C-1309 #7b).
 */
async function post(path: string, body: unknown, token?: string): Promise<Response> {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) {
    headers.authorization = `Bearer ${token}`;
  }
  return SELF.fetch(`http://localhost${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
}

async function get(path: string): Promise<Response> {
  return SELF.fetch(`http://localhost${path}`);
}

async function json<T>(response: Response): Promise<T> {
  return (await response.json()) as T;
}

interface PairView {
  pair: string[];
  heads: { a: string; b: string };
  status: string;
  kind?: string;
  evidence?: string;
  checkedAt: string | null;
  stale: boolean;
  activeWarningIds: string[];
}

interface ChecksResponse {
  accepted: number;
  pairs: PairView[];
  createdWarnings: { id: string; status: string; reason: string; kind?: string; evidence?: string }[];
  lastRunnerReport?: unknown;
}

interface StatusSnapshot {
  heads: Record<string, string>;
  pairs: PairView[];
  warnings: { id: string; status: string; pair: string[]; resolvedBy?: string }[];
  lastRunnerReport: { policy: string; coverage: string[]; accepted: number; vector: Record<string, string> } | null;
}

let tagCounter = 0;

async function primedPair(): Promise<{ alpha: string; beta: string; alphaSha: string; betaSha: string }> {
  const tag = `t${String(++tagCounter).padStart(2, "0")}`;
  const alphaBody = await json<{ agentId: string; fork: { name: string } }>(
    await post("/tasks", { agent: `alpha-${tag}` }, ADMIN_TOKEN),
  );
  const betaBody = await json<{ agentId: string; fork: { name: string } }>(
    await post("/tasks", { agent: `beta-${tag}` }, ADMIN_TOKEN),
  );
  const alphaSha = await sidecarCommit(alphaBody.fork.name, "wip: alpha diverges");
  const betaSha = await sidecarCommit(betaBody.fork.name, "wip: beta diverges");
  await post("/events/push", { agent: alphaBody.agentId, sha: alphaSha });
  await post("/events/push", { agent: betaBody.agentId, sha: betaSha });
  return { alpha: alphaBody.agentId, beta: betaBody.agentId, alphaSha, betaSha };
}

async function currentVector(): Promise<Record<string, string>> {
  const status = await json<StatusSnapshot>(await get("/status"));
  return status.heads;
}

function pairFor<T extends { pair: string[] }>(items: T[], alpha: string, beta: string): T {
  const found = items.find((item) => item.pair.includes(alpha) && item.pair.includes(beta));
  if (!found) {
    throw new Error(`no pair for ${alpha}|${beta}`);
  }
  return found;
}

async function checks(payload: Record<string, unknown>): Promise<Response> {
  return post("/checks", payload, RUNNER_TOKEN);
}

describe("trusted runner checks (vector-gated, conflict-only warnings)", () => {
  it("a conflict result at the current vector creates one active warning", async () => {
    const { alpha, beta } = await primedPair();
    const response = await checks({
      vector: await currentVector(),
      policy: "merge-tree-v1",
      coverage: [`${alpha}|${beta}`],
      results: [{ pair: [alpha, beta], status: "conflict", kind: "merge-conflict", evidence: "git merge-tree exit 1" }],
    });
    expect(response.status).toBe(200);
    const body = await json<ChecksResponse>(response);
    expect(body.createdWarnings).toHaveLength(1);
    expect(body.createdWarnings[0].status).toBe("active");
    expect(body.createdWarnings[0].reason).toBe("merge-conflict");
    const view = pairFor(body.pairs, alpha, beta);
    expect(view.status).toBe("conflict");
    expect(view.kind).toBe("merge-conflict");
    expect(view.activeWarningIds).toHaveLength(1);
  });

  it("rejects a stale vector with 409 and returns the current heads", async () => {
    const { alpha } = await primedPair();
    const vector = await currentVector();
    const stale = { ...vector, [alpha]: "f".repeat(40) };
    const response = await checks({ vector: stale, policy: "p", results: [] });
    expect(response.status).toBe(409);
    const body = await json<{ error: string; currentHeads: Record<string, string> }>(response);
    expect(body.error).toContain("stale vector");
    expect(body.currentHeads[alpha]).toBe(vector[alpha]);

    const missing = await checks({ vector: {}, policy: "p", results: [] });
    expect(missing.status).toBe(409);
  });

  it("clean and unknown are recorded; clean resolves an active warning at the same heads", async () => {
    const { alpha, beta } = await primedPair();
    await checks({
      vector: await currentVector(),
      policy: "p",
      results: [{ pair: [alpha, beta], status: "conflict" }],
    });
    const cleaned = await checks({
      vector: await currentVector(),
      policy: "p",
      results: [{ pair: [alpha, beta], status: "clean", evidence: "merge-tree exit 0" }],
    });
    expect((await json<ChecksResponse>(cleaned)).createdWarnings).toHaveLength(0);

    const unknown = await checks({
      vector: await currentVector(),
      policy: "p",
      results: [{ pair: [alpha, beta], status: "unknown", evidence: "worktree error" }],
    });
    const unknownBody = await json<ChecksResponse>(unknown);
    expect(pairFor(unknownBody.pairs, alpha, beta).status).toBe("unknown");

    const status = await json<StatusSnapshot>(await get("/status"));
    const resolved = status.warnings.find(
      (w) => w.pair.includes(alpha) && w.pair.includes(beta) && w.status === "invalidated",
    );
    expect(resolved?.resolvedBy).toContain("clean check");
  });

  it("records the last runner report (policy, coverage, accepted)", async () => {
    const { alpha, beta } = await primedPair();
    await checks({
      vector: await currentVector(),
      policy: "merge-tree-v1",
      coverage: [`${alpha}|${beta}`],
      results: [{ pair: [alpha, beta], status: "clean" }],
    });
    const status = await json<StatusSnapshot>(await get("/status"));
    expect(status.lastRunnerReport?.policy).toBe("merge-tree-v1");
    expect(status.lastRunnerReport?.coverage).toEqual([`${alpha}|${beta}`]);
    expect(status.lastRunnerReport?.accepted).toBe(1);
    expect(status.lastRunnerReport?.vector[alpha]).toBeTruthy();
  });

  it("advancing a head makes the pair not_checked (stale) again and invalidates the warning", async () => {
    const { alpha, beta, alphaSha } = await primedPair();
    await checks({
      vector: await currentVector(),
      policy: "p",
      results: [{ pair: [alpha, beta], status: "conflict" }],
    });
    // beta pushes a new real commit -> warning invalidated, stored check stale
    const status0 = await json<StatusSnapshot>(await get("/status"));
    const betaFork = (await json<{ agents: { agentId: string; forkName: string }[] }>(await get("/status")))
      .agents.find((a) => a.agentId === beta)!;
    const betaNext = await sidecarCommit(betaFork.forkName, "wip: beta moves on");
    const push = await json<{ invalidatedWarnings: string[]; newWarnings: unknown[] }>(
      await post("/events/push", { agent: beta, sha: betaNext }),
    );
    expect(push.invalidatedWarnings).toHaveLength(1);
    expect(push.newWarnings).toHaveLength(0);

    const status = await json<StatusSnapshot>(await get("/status"));
    const view = pairFor(status.pairs, alpha, beta);
    expect(view.status).toBe("not_checked");
    expect(view.stale).toBe(true);
    expect(view.checkedAt).toBeTruthy();
    expect(view.activeWarningIds).toEqual([]);
    expect(view.heads.a === alphaSha || view.heads.b === alphaSha).toBe(true);
  });

  it("rejects malformed results with 400 and missing vector with 400", async () => {
    const { alpha, beta } = await primedPair();
    const badAgent = await checks({
      vector: await currentVector(),
      policy: "p",
      results: [{ pair: [alpha, "ghost"], status: "clean" }],
    });
    expect(badAgent.status).toBe(400);
    const badStatus = await checks({
      vector: await currentVector(),
      policy: "p",
      results: [{ pair: [alpha, beta], status: "bogus" }],
    });
    expect(badStatus.status).toBe(400);
    const notChecked = await checks({
      vector: await currentVector(),
      policy: "p",
      results: [{ pair: [alpha, beta], status: "not_checked" }],
    });
    expect(notChecked.status).toBe(400);
    const noVector = await checks({ policy: "p", results: [] });
    expect(noVector.status).toBe(400);
    const noResults = await checks({ vector: await currentVector(), policy: "p" });
    expect(noResults.status).toBe(400);
  });
});
