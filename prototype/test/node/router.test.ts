/**
 * Wire parity of the provider-neutral router under plain node --test
 * (facade extraction, 2026-10-03): same statuses, error bodies and auth
 * decisions as the CONTRACT (0.1.x) — produced by handleRoute without any
 * HTTP platform, exercised here over neutral request objects.
 */

import { test } from "node:test";
import { deepStrictEqual, ok, strictEqual } from "node:assert";
import { handleRoute } from "../../src/core/router.js";
import { makeRig, neutralRequest, rejectionMessage, type TestRig } from "./fakes.js";

async function call(rig: TestRig, method: string, path: string, body?: unknown, token?: string) {
  return handleRoute(rig.services, neutralRequest(method, path, body, token));
}

test("routing: unknown routes and unauthenticated setup", async () => {
  const rig = makeRig();
  const missing = await call(rig, "GET", "/definitely/not/a/route");
  strictEqual(missing.status, 404);
  deepStrictEqual(missing.body, { error: "no route for GET /definitely/not/a/route" });

  const anon = await call(rig, "POST", "/setup", {});
  strictEqual(anon.status, 401);

  const wrong = await call(rig, "POST", "/setup", {}, "not-the-admin");
  strictEqual(wrong.status, 401);
  deepStrictEqual(wrong.body, { error: "unauthorized: valid bearer token required (ADMIN_TOKEN)" });

  const ok_ = await call(rig, "POST", "/setup", {}, "admin-t");
  strictEqual(ok_.status, 201);
});

test("fail-closed: unconfigured admin token refuses authenticated routes", async () => {
  const rig = makeRig({});
  const denied = await call(rig, "POST", "/setup", {}, "anything");
  strictEqual(denied.status, 503);
  ok((denied.body as { error: string }).error.includes("not configured; refusing authenticated request"));
});

test("/tasks and /status over the neutral router", async () => {
  const rig = makeRig();
  const anon = await call(rig, "POST", "/tasks", { agent: "x" });
  strictEqual(anon.status, 401);

  const created = await call(rig, "POST", "/tasks", { agent: "via-router", intent: "router" }, "admin-t");
  strictEqual(created.status, 201);
  const task = created.body as { taskId: string; agentId: string; intent: string | null };
  strictEqual(task.agentId, "via-router-0001");
  strictEqual(task.intent, "router");

  const status = await call(rig, "GET", "/status");
  strictEqual(status.status, 200);
  ok((status.body as { agents: unknown[] }).agents.length === 1);
});

test("/events/push: validation, auth ladder, cross-agent 403, dedup", async () => {
  const rig = makeRig();
  const created = (await call(rig, "POST", "/tasks", { agent: "eve" }, "admin-t")).body as {
    agentId: string;
    fork: { name: string };
    token: { plaintext: string };
  };
  const other = (await call(rig, "POST", "/tasks", { agent: "malory" }, "admin-t")).body as {
    agentId: string;
    token: { plaintext: string };
  };
  const sha = rig.git.commit(created.fork.name, "wip: via route");

  // Malformed body: no sha.
  const bad = await call(rig, "POST", "/events/push", { agent: created.agentId }, "admin-t");
  strictEqual(bad.status, 400);
  deepStrictEqual(bad.body, { error: "agent or fork, and sha are required strings" });

  // Anonymous push rejected.
  strictEqual((await call(rig, "POST", "/events/push", { agent: created.agentId, sha })).status, 401);

  // Another agent's token is 403, with neither token echoed.
  const cross = await call(rig, "POST", "/events/push", { agent: created.agentId, sha }, other.token.plaintext);
  strictEqual(cross.status, 403);
  deepStrictEqual(cross.body, { error: `forbidden: this token belongs to ${other.agentId}, not ${created.agentId}` });

  // Own token accepted.
  const own = await call(rig, "POST", "/events/push", { agent: created.agentId, sha }, created.token.plaintext);
  strictEqual(own.status, 200);
  strictEqual((own.body as { accepted: boolean }).accepted, true);

  // Sidecar webhook shape: fork identifies the pusher, sidecar bearer accepted.
  const sha2 = rig.git.commit(created.fork.name, "wip: webhook");
  const hook = await call(
    rig,
    "POST",
    "/events/push",
    { fork: created.fork.name, ref: "refs/heads/main", sha: sha2 },
    "sidecar-t",
  );
  strictEqual(hook.status, 200);
  strictEqual((hook.body as { agent: string }).agent, created.agentId);

  // Redelivery dedupes.
  const redelivery = await call(rig, "POST", "/events/push", { agent: created.agentId, sha: sha2 }, "admin-t");
  strictEqual((redelivery.body as { deduped: boolean }).deduped, true);
});

test("/events/artifacts: envelope accepted, unknown fork 202, bad envelope 400", async () => {
  const rig = makeRig();
  const created = (await call(rig, "POST", "/tasks", { agent: "env" }, "admin-t")).body as {
    agentId: string;
    fork: { name: string };
    head: string | null;
  };
  const sha = rig.git.commit(created.fork.name, "wip: envelope");
  const envelope = {
    type: "cf.artifacts.repo.pushed",
    source: { type: "artifacts.repo", namespace: "local", repoName: created.fork.name },
    payload: { ref: "refs/heads/main", before: created.head, after: sha, commits: [], totalCommitsCount: 1, commitsTruncated: false },
    metadata: { accountId: "local", eventSubscriptionId: "t", eventSchemaVersion: 1, eventTimestamp: "2026-10-03T12:00:00.000Z" },
  };

  const anon = await call(rig, "POST", "/events/artifacts", envelope);
  strictEqual(anon.status, 401);

  const accepted = await call(rig, "POST", "/events/artifacts", envelope, "sidecar-t");
  strictEqual(accepted.status, 200);
  strictEqual((accepted.body as { heads: Record<string, string> }).heads[created.agentId], sha);

  const stranger = await call(
    rig,
    "POST",
    "/events/artifacts",
    { ...envelope, source: { type: "artifacts.repo", namespace: "local", repoName: "who-knows" } },
    "sidecar-t",
  );
  strictEqual(stranger.status, 202);
  deepStrictEqual(stranger.body, { accepted: false, reason: "no agent owns fork who-knows" });

  const malformed = await call(
    rig,
    "POST",
    "/events/artifacts",
    { type: "something.else" },
    "sidecar-t",
  );
  strictEqual(malformed.status, 400);
  ok((malformed.body as { error: string }).error.includes("unsupported event type"));
});

test("/checks: runner auth, parse errors, stale 409, success shape", async () => {
  const rig = makeRig();
  const a = (await call(rig, "POST", "/tasks", { agent: "a" }, "admin-t")).body as { agentId: string; fork: { name: string } };
  const b = (await call(rig, "POST", "/tasks", { agent: "b" }, "admin-t")).body as { agentId: string };
  const vector = ((await call(rig, "GET", "/status")).body as { heads: Record<string, string> }).heads;

  strictEqual((await call(rig, "POST", "/checks", { contract: "0.0", vector, policy: "p", results: [] })).status, 401);
  strictEqual((await call(rig, "POST", "/checks", { contract: "0.0", vector, policy: "p", results: [] }, "admin-t")).status, 401,
    "admin is not the runner");
  strictEqual(
    (await call(rig, "POST", "/checks", { vector, policy: "p", results: [] }, "runner-t")).status,
    400,
    "missing contract declaration",
  );

  const stale = await call(
    rig,
    "POST",
    "/checks",
    {
      contract: "0.0",
      vector: { ...vector, [a.agentId]: "0".repeat(40) },
      policy: "p",
      results: [{ pair: [a.agentId, b.agentId], status: "clean" }],
    },
    "runner-t",
  );
  strictEqual(stale.status, 409);
  ok((stale.body as { error: string }).error.startsWith("stale vector:"));
  deepStrictEqual((stale.body as { currentHeads: Record<string, string> }).currentHeads, vector);

  const good = await call(
    rig,
    "POST",
    "/checks",
    {
      contract: "0.0",
      vector,
      policy: "runner-policy",
      results: [{ pair: [a.agentId, b.agentId], status: "conflict", kind: "merge-conflict" }],
    },
    "runner-t",
  );
  strictEqual(good.status, 200);
  const body = good.body as { accepted: number; createdWarnings: { id: string }[]; pairs: { status: string }[] };
  strictEqual(body.accepted, 1);
  strictEqual(body.createdWarnings.length, 1);
  ok(body.pairs[0].status === "conflict");
});

test("/tasks/:id and /tasks/:id/tests: 404s and owner-only provenance", async () => {
  const rig = makeRig();
  const created = (await call(rig, "POST", "/tasks", { agent: "own" }, "admin-t")).body as {
    taskId: string;
    agentId: string;
    fork: { name: string };
    token: { plaintext: string };
  };
  const stranger = (await call(rig, "POST", "/tasks", { agent: "str" }, "admin-t")).body as {
    agentId: string;
    token: { plaintext: string };
  };

  const found = await call(rig, "GET", `/tasks/${created.taskId}`);
  strictEqual(found.status, 200);
  strictEqual((found.body as { agentId: string }).agentId, created.agentId);
  const missing = await call(rig, "GET", "/tasks/task-9999");
  strictEqual(missing.status, 404);
  ok((missing.body as { error: string }).error.startsWith("unknown task"));

  const sha = rig.git.commit(created.fork.name, "wip: provenance");
  const anon = await call(rig, "POST", `/tasks/${created.taskId}/tests`, { command: "npm test", exit: 0, head_sha: sha });
  strictEqual(anon.status, 401);
  const cross = await call(
    rig, "POST", `/tasks/${created.taskId}/tests`,
    { command: "npm test", exit: 0, head_sha: sha },
    stranger.token.plaintext,
  );
  strictEqual(cross.status, 403);
  const badShape = await call(
    rig, "POST", `/tasks/${created.taskId}/tests`, { command: "npm test" }, created.token.plaintext,
  );
  strictEqual(badShape.status, 400);
  const good = await call(
    rig, "POST", `/tasks/${created.taskId}/tests`,
    { command: "npm test", exit: 0, head_sha: sha },
    created.token.plaintext,
  );
  strictEqual(good.status, 201);
  const unknownTask = await call(
    rig, "POST", "/tasks/task-9999/tests", { command: "npm test", exit: 0, head_sha: sha }, "admin-t",
  );
  strictEqual(unknownTask.status, 404);
});

test("/warnings/:id/ack: body validated before auth, owner-only acks", async () => {
  const rig = makeRig();
  const a = (await call(rig, "POST", "/tasks", { agent: "a" }, "admin-t")).body as {
    agentId: string; token: { plaintext: string };
  };
  const b = (await call(rig, "POST", "/tasks", { agent: "b" }, "admin-t")).body as {
    agentId: string; token: { plaintext: string };
  };
  const vector = ((await call(rig, "GET", "/status")).body as { heads: Record<string, string> }).heads;
  const warningId = ((await call(
    rig, "POST", "/checks",
    { contract: "0.0", vector, policy: "p", results: [{ pair: [a.agentId, b.agentId], status: "conflict" }] },
    "runner-t",
  )).body as { createdWarnings: { id: string }[] }).createdWarnings[0].id;

  const noAgent = await call(rig, "POST", `/warnings/${warningId}/ack`, {}, "admin-t");
  strictEqual(noAgent.status, 400);
  deepStrictEqual(noAgent.body, { error: "agent is a required string" });

  const cross = await call(rig, "POST", `/warnings/${warningId}/ack`, { agent: a.agentId }, b.token.plaintext);
  strictEqual(cross.status, 403);

  const ok_ = await call(rig, "POST", `/warnings/${warningId}/ack`, { agent: a.agentId, note: "seen" }, a.token.plaintext);
  strictEqual(ok_.status, 200);
  strictEqual(((ok_.body as { warning: { acks: { note?: string }[] } }).warning.acks[0])?.note, "seen");

  const unknown = await call(rig, "POST", "/warnings/warn-9999/ack", { agent: a.agentId }, "admin-t");
  strictEqual(unknown.status, 404);
});

test("malformed JSON bodies map to the contract 400", async () => {
  const rig = makeRig();
  const response = await handleRoute(rig.services, {
    method: "POST",
    path: "/tasks",
    header: () => "Bearer admin-t",
    json: async () => {
      throw new SyntaxError("unexpected token");
    },
  });
  strictEqual(response.status, 400);
  deepStrictEqual(response.body, { error: "request body must be valid JSON" });
});

test("rejectionMessage helper stays honest (guards the suite itself)", async () => {
  const rig = makeRig();
  await rejectionMessage(rig.core.getTask("task-9999"), /^unknown task:/);
});

test("invalid-bearer flood: 5x401 then 429 with Retry-After; valid auth clears (C-1441)", async () => {
  const rig = makeRig();
  const attempt = (token?: string) => call(rig, "POST", "/setup", {}, token);

  for (let i = 0; i < 5; i++) {
    strictEqual((await attempt("not-the-admin")).status, 401, `invalid attempt ${i + 1} stays 401`);
  }
  const blocked = await attempt("not-the-admin");
  strictEqual(blocked.status, 429, "6th consecutive invalid bearer is rate limited");
  deepStrictEqual(blocked.body, {
    error: "rate_limited",
    message: "Too many failed authentication attempts. Please retry later.",
  });
  strictEqual(blocked.headers?.["retry-after"], "60");

  // While blocked, the SAME client with a VALID credential still succeeds
  // (valid authentication is never rate limited) and clears the count.
  strictEqual((await attempt("admin-t")).status, 201);
  strictEqual((await attempt("not-the-admin")).status, 401, "count restarted after the success");

  // A different client key is tracked independently.
  const other = await handleRoute(rig.services, neutralRequest("POST", "/setup", {}, "not-the-admin", "198.51.100.9"));
  strictEqual(other.status, 401);
});

test("invalid-bearer counting: 403/503 outcomes are not counted (C-1441)", async () => {
  // 503 fail-closed (ADMIN_TOKEN unconfigured) is a server state, not a
  // client failure. If it were counted, the runner probe below would 429.
  const halfConfigured = makeRig({ admin: undefined, runner: "runner-t", sidecar: undefined });
  for (let i = 0; i < 8; i++) {
    strictEqual((await call(halfConfigured, "POST", "/setup", {}, "anything")).status, 503);
  }
  const runnerProbe = await call(
    halfConfigured,
    "POST",
    "/checks",
    { contract: "0.0", vector: {}, policy: "p", results: [] },
    "wrong-runner",
  );
  strictEqual(runnerProbe.status, 401, "503 outcomes must not count toward the block");

  // 403 cross-agent is an authenticated rejection (valid stranger token on
  // someone else's task): eight of them must not arm the block either.
  const rig = makeRig();
  const owner = (await call(rig, "POST", "/tasks", { agent: "own" }, "admin-t")).body as { taskId: string };
  const stranger = (await call(rig, "POST", "/tasks", { agent: "str" }, "admin-t")).body as {
    token: { plaintext: string };
  };
  for (let i = 0; i < 8; i++) {
    const cross = await call(
      rig,
      "POST",
      `/tasks/${owner.taskId}/tests`,
      { command: "npm test", exit: 0, head_sha: "0".repeat(40) },
      stranger.token.plaintext,
    );
    strictEqual(cross.status, 403);
  }
  const probe = await call(rig, "POST", "/setup", {}, "not-the-admin");
  strictEqual(probe.status, 401, "403 outcomes must not count toward the block");

  const stillOk = await call(rig, "POST", "/tasks", { agent: "after-flood" }, "admin-t");
  strictEqual(stillOk.status, 201, "valid admin auth unaffected throughout");
});
