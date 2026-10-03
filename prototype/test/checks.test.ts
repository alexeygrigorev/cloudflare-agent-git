import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

/**
 * Radar/runner check results arrive via POST /checks; warnings exist only for
 * status "conflict" (codex C-1305 #1). Vector freshness enforcement and
 * RUNNER_TOKEN auth arrive with the deployment-boundary fix (C-1309).
 *
 * The DO keeps state across tests within this file, so every test uses its
 * own agent-name tag and scopes assertions to its own pair.
 */
const SHA_A1 = "1".repeat(40);
const SHA_B1 = "2".repeat(40);
const SHA_B2 = "3".repeat(40);

async function post(path: string, body: unknown, token?: string): Promise<Response> {
  const effective = token ?? (path === "/checks" ? "test-runner-token" : path === "/tasks" ? "test-admin-token" : undefined);
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (effective) {
    headers.authorization = `Bearer ${effective}`;
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
}

interface StatusSnapshot {
  heads: Record<string, string>;
  pairs: PairView[];
  warnings: { id: string; status: string; reason: string; pair: string[]; resolvedBy?: string }[];
}

let tagCounter = 0;

async function primedPair(): Promise<{ alpha: string; beta: string }> {
  const tag = `t${String(++tagCounter).padStart(2, "0")}`;
  const alpha = (
    await json<{ agentId: string }>(await post("/tasks", { agent: `alpha-${tag}` }, "test-admin-token"))
  ).agentId;
  const beta = (
    await json<{ agentId: string }>(await post("/tasks", { agent: `beta-${tag}` }, "test-admin-token"))
  ).agentId;
  await post("/events/push", { agent: alpha, sha: SHA_A1 });
  await post("/events/push", { agent: beta, sha: SHA_B1 });
  return { alpha, beta };
}

function pairFor<T extends { pair: string[] }>(items: T[], alpha: string, beta: string): T {
  const found = items.find((item) => item.pair.includes(alpha) && item.pair.includes(beta));
  if (!found) {
    throw new Error(`no pair for ${alpha}|${beta}`);
  }
  return found;
}

describe("check-result application (warnings only for conflict)", () => {
  it("a conflict result creates exactly one active warning with kind and evidence", async () => {
    const { alpha, beta } = await primedPair();
    const response = await post("/checks", {
      policy: "merge-tree-v1",
      results: [{ pair: [alpha, beta], status: "conflict", kind: "merge-conflict", evidence: "git merge-tree exit 1" }],
    });
    expect(response.status).toBe(200);
    const body = await json<ChecksResponse>(response);
    expect(body.createdWarnings).toHaveLength(1);
    expect(body.createdWarnings[0].status).toBe("active");
    expect(body.createdWarnings[0].reason).toBe("merge-conflict");
    expect(body.createdWarnings[0].evidence).toBe("git merge-tree exit 1");
    const view = pairFor(body.pairs, alpha, beta);
    expect(view.status).toBe("conflict");
    expect(view.kind).toBe("merge-conflict");
    expect(view.checkedAt).toBeTruthy();
  });

  it("repeated conflict at the same heads does not duplicate the warning", async () => {
    const { alpha, beta } = await primedPair();
    await post("/checks", { policy: "p", results: [{ pair: [alpha, beta], status: "conflict" }] });
    const again = await json<ChecksResponse>(
      await post("/checks", { policy: "p", results: [{ pair: [alpha, beta], status: "conflict" }] }),
    );
    expect(again.createdWarnings).toHaveLength(0);
    const status = await json<StatusSnapshot>(await get("/status"));
    const mine = status.warnings.filter(
      (w) => w.pair.includes(alpha) && w.pair.includes(beta) && w.status === "active",
    );
    expect(mine).toHaveLength(1);
  });

  it("a clean result at the same heads resolves the active warning; pairs show clean", async () => {
    const { alpha, beta } = await primedPair();
    await post("/checks", { policy: "p", results: [{ pair: [alpha, beta], status: "conflict" }] });
    const cleaned = await json<ChecksResponse>(
      await post("/checks", { policy: "p", results: [{ pair: [alpha, beta], status: "clean", evidence: "exit 0" }] }),
    );
    expect(cleaned.createdWarnings).toHaveLength(0);
    expect(pairFor(cleaned.pairs, alpha, beta).status).toBe("clean");
    const status = await json<StatusSnapshot>(await get("/status"));
    const resolved = status.warnings.find(
      (w) => w.pair.includes(alpha) && w.pair.includes(beta) && w.status === "invalidated",
    );
    expect(resolved?.resolvedBy).toContain("clean check");
    expect(pairFor(status.pairs, alpha, beta).activeWarningIds).toEqual([]);
  });

  it("unknown is recorded distinctly — never clean, never a warning", async () => {
    const { alpha, beta } = await primedPair();
    const applied = await json<ChecksResponse>(
      await post("/checks", { policy: "p", results: [{ pair: [alpha, beta], status: "unknown" }] }),
    );
    expect(pairFor(applied.pairs, alpha, beta).status).toBe("unknown");
    const status = await json<StatusSnapshot>(await get("/status"));
    expect(status.warnings.filter((w) => w.pair.includes(alpha) && w.pair.includes(beta))).toEqual([]);
  });

  it("advancing a head invalidates the warning and makes the stored check stale (not_checked)", async () => {
    const { alpha, beta } = await primedPair();
    await post("/checks", { policy: "p", results: [{ pair: [alpha, beta], status: "conflict" }] });
    const push = await json<{ invalidatedWarnings: string[]; newWarnings: unknown[] }>(
      await post("/events/push", { agent: beta, sha: SHA_B2 }),
    );
    expect(push.invalidatedWarnings).toHaveLength(1);
    expect(push.newWarnings).toHaveLength(0);

    const status = await json<StatusSnapshot>(await get("/status"));
    const view = pairFor(status.pairs, alpha, beta);
    expect(view.status).toBe("not_checked");
    expect(view.stale).toBe(true);
    expect(view.checkedAt).toBeTruthy();
    expect(view.activeWarningIds).toEqual([]);
  });

  it("rejects malformed results with 400", async () => {
    const { alpha, beta } = await primedPair();
    const badAgent = await post("/checks", { policy: "p", results: [{ pair: [alpha, "ghost"], status: "clean" }] });
    expect(badAgent.status).toBe(400);
    const badStatus = await post("/checks", { policy: "p", results: [{ pair: [alpha, beta], status: "bogus" }] });
    expect(badStatus.status).toBe(400);
    const notChecked = await post("/checks", { policy: "p", results: [{ pair: [alpha, beta], status: "not_checked" }] });
    expect(notChecked.status).toBe(400);
    const noResults = await post("/checks", { policy: "p" });
    expect(noResults.status).toBe(400);
  });
});
