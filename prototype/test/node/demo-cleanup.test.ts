import { test } from "node:test";
import { deepStrictEqual, rejects, strictEqual } from "node:assert";
import { handleRoute } from "../../src/core/router.js";
import { makeRig, neutralRequest } from "./fakes.js";

const runId = "a".repeat(32);

test("run cleanup is exact, authenticated, repeatable and removes scoped credentials", async () => {
  const rig = makeRig();
  for (const token of [undefined, "runner-t", "bad"]) {
    strictEqual((await handleRoute(rig.services, neutralRequest("POST", "/demo-runs/cleanup", { runId }, token))).status, 401);
  }
  strictEqual((await handleRoute(rig.services, neutralRequest("POST", "/demo-runs/cleanup", {}, "admin-t"))).status, 400);
  strictEqual((await handleRoute(rig.services, neutralRequest("GET", "/demo-runs/cleanup", {}, "admin-t"))).status, 405);
  strictEqual((await handleRoute(rig.services, neutralRequest("POST", "/demo-runs/cleanup", { runId }, "admin-t"))).status, 404);
  const setup = await handleRoute(rig.services, neutralRequest("POST", "/setup", { runId }, "admin-t"));
  strictEqual(setup.status, 201);
  const task = await rig.core.createTask({ agent: "owned", runId });
  const result = await rig.core.cleanupDemoRun(runId);
  strictEqual(result.deleted, 2);
  strictEqual(result.complete, true);
  deepStrictEqual(result.remaining, []);
  deepStrictEqual(await rig.git.listRepos(), []);
  strictEqual(await rig.core.credentialAgent(task.token.plaintext), null);
  strictEqual((await rig.core.status()).canonical.name, null);
  strictEqual((await rig.core.cleanupDemoRun(runId)).deleted, 0);
  await rejects(rig.core.setup({ runId }), /cleanup before reuse/);
});

test("concurrent peer task creation remains intact; canonical is retained", async () => {
  const rig = makeRig();
  const setup = await rig.core.setup({ runId });
  const owned = await rig.core.createTask({ agent: "owned", runId });
  // Queue the peer first: cleanup shares the same mutex across its provider I/O.
  const [peer, result] = await Promise.all([
    rig.core.createTask({ agent: "peer" }), rig.core.cleanupDemoRun(runId),
  ]);
  strictEqual(result.complete, false);
  deepStrictEqual(result.remaining, [setup.canonical.name]);
  deepStrictEqual((await rig.git.listRepos()).map((repo) => repo.name).sort(), [setup.canonical.name, peer.fork.name].sort());
  strictEqual(await rig.core.credentialAgent(peer.token.plaintext), peer.agentId);
  strictEqual(await rig.core.credentialAgent(owned.token.plaintext), null);
  deepStrictEqual((await rig.core.status()).agents.map((agent) => agent.agentId), [peer.agentId]);
});

test("cleanup waits for adapter credential linkage before deleting owned task", async () => {
  const rig = makeRig();
  await rig.core.setup({ runId });
  let release!: () => void;
  let started!: () => void;
  const linking = new Promise<void>((resolve) => { started = resolve; });
  const hold = new Promise<void>((resolve) => { release = resolve; });
  const order: string[] = [];
  const task = rig.core.createTask({ agent: "owned", runId }, async () => {
    started();
    await hold;
    order.push("linked");
  });
  await linking;
  const cleanup = rig.core.cleanupDemoRun(runId).then((result) => { order.push("cleaned"); return result; });
  await Promise.resolve();
  deepStrictEqual(order, []);
  release();
  await task;
  strictEqual((await cleanup).complete, true);
  deepStrictEqual(order, ["linked", "cleaned"]);
});

test("unregistered dependent fork inventory is preserved and holds canonical cleanup", async () => {
  const rig = makeRig();
  const setup = await rig.core.setup({ runId });
  await rig.git.createRepo(setup.canonical.name + "-peer-pending");
  const result = await rig.core.cleanupDemoRun(runId);
  strictEqual(result.deleted, 0);
  strictEqual(result.complete, false);
  strictEqual((await rig.git.listRepos()).length, 2);
});

test("unrelated independent repository is preserved while owned cleanup completes", async () => {
  const rig = makeRig();
  await rig.core.setup({ runId });
  await rig.git.createRepo("unrelated");
  strictEqual((await rig.core.cleanupDemoRun(runId)).complete, true);
  deepStrictEqual((await rig.git.listRepos()).map((repo) => repo.name), ["unrelated"]);
});

test("lost setup response is recoverable after reload using only runId", async () => {
  const rig = makeRig();
  const original = rig.git.createRepo.bind(rig.git);
  rig.git.createRepo = async (...args) => {
    await original(...args);
    throw new Error("provider response lost");
  };
  await rejects(rig.core.setup({ runId }), /response lost/);
  rig.core.clearModel();
  strictEqual((await rig.core.cleanupDemoRun(runId)).complete, true);
  deepStrictEqual(await rig.git.listRepos(), []);
});

test("lost fork response and partial delete failure remain retryable after reload", async () => {
  const rig = makeRig();
  const setup = await rig.core.setup({ runId });
  const original = rig.git.fork.bind(rig.git);
  rig.git.fork = async (...args) => {
    await original(...args);
    throw new Error("fork response lost");
  };
  await rejects(rig.core.createTask({ agent: "owned", runId }), /response lost/);
  rig.core.clearModel();
  const remove = rig.git.deleteRepo.bind(rig.git);
  rig.git.deleteRepo = async (name) => {
    if (name === setup.canonical.name) throw new Error("Budget exceeded");
    return remove(name);
  };
  await rejects(rig.core.cleanupDemoRun(runId), /Budget exceeded/);
  strictEqual((await rig.git.listRepos()).length, 1);
  rig.core.clearModel();
  rig.git.deleteRepo = remove;
  const retry = await rig.core.cleanupDemoRun(runId);
  strictEqual(retry.deleted, 1);
  strictEqual(retry.complete, true);
});

test("run cannot adopt existing canonical, invalid runId or an occupied name", async () => {
  const rig = makeRig();
  await rejects(rig.core.setup({ runId: "invalid" }), /runId/);
  await rig.core.setup();
  await rejects(rig.core.setup({ runId }), /other work/);
  await rejects(rig.core.createTask({ runId }), /does not own/);
  const other = makeRig();
  await other.git.createRepo("agent-branches-canonical-cafe1234");
  await rejects(other.core.setup({ runId }), /already exists/);
  await rejects(other.core.cleanupDemoRun(runId), /unknown demo run/);
  strictEqual((await other.git.listRepos()).length, 1);
});
