import { test } from "node:test";
import { deepStrictEqual, rejects, strictEqual } from "node:assert";
import { handleRoute } from "../../src/core/router.js";
import { makeRig, neutralRequest } from "./fakes.js";

test("plans persist and detect overlap before any push without changing check results or heads", async () => {
  const rig = makeRig();
  const a = await rig.core.createTask({ agent: "a" });
  const b = await rig.core.createTask({ agent: "b" });
  const before = await rig.core.status();
  deepStrictEqual(before.plannedOverlaps, []);
  strictEqual(before.agents.every((agent) => agent.plannedPaths === null), true);
  await rig.core.updateTaskPlan(a.taskId, ["rate.py", "rate.py"]);
  await rig.core.updateTaskPlan(b.taskId, ["region.py"]);
  deepStrictEqual((await rig.core.status()).plannedOverlaps, []);
  const result = await rig.core.updateTaskPlan(a.taskId, ["shared.txt", "rate.py", "shared.txt"]);
  deepStrictEqual(result.plannedPaths, ["rate.py", "shared.txt"]);
  await rig.core.updateTaskPlan(b.taskId, ["shared.txt"]);
  const early = await rig.core.status();
  deepStrictEqual(early.plannedOverlaps, [{ agents: [a.agentId, b.agentId], tasks: [a.taskId, b.taskId],
    paths: ["shared.txt"], kind: "planned_overlap" }]);
  deepStrictEqual(early.heads, before.heads);
  deepStrictEqual(early.pairs, before.pairs);
  deepStrictEqual(early.warnings, []);
  strictEqual(early.agents.every((agent) => agent.pushes === 0), true);
  rig.core.clearModel();
  deepStrictEqual((await rig.core.status()).plannedOverlaps, early.plannedOverlaps);
  const detail = await rig.core.getTask(a.taskId);
  detail.plannedPaths!.push("not-a-real-plan.txt");
  deepStrictEqual((await rig.core.getTask(a.taskId)).plannedPaths, ["rate.py", "shared.txt"]);
  await rig.core.updateTaskPlan(b.taskId, []);
  deepStrictEqual((await rig.core.status()).plannedOverlaps, []);
  deepStrictEqual((await rig.core.status()).agents.find((agent) => agent.agentId === b.agentId)?.plannedPaths, []);
});

test("plan validation rejects unsafe/ambiguous paths atomically; exact-path matching is case-sensitive", async () => {
  const rig = makeRig();
  const a = await rig.core.createTask({ agent: "a" });
  const b = await rig.core.createTask({ agent: "b" });
  await rig.core.updateTaskPlan(a.taskId, ["src/file.ts"]);
  const invalid: unknown[] = [null, {}, "a", [3], [""], ["/absolute"], ["../up"], ["a/../b"],
    ["./file"], ["a//b"], ["a/"], ["C:/file"], ["a\\b"], ["*.ts"], ["file?.ts"], ["[ab].ts"],
    ["a\n.txt"], [" leading"], ["src/ trailing "], ["%2e%2e/file"], ["x".repeat(513)], Array(129).fill("x")];
  for (const paths of invalid) {
    await rejects(rig.core.updateTaskPlan(a.taskId, paths), /plannedPaths/);
    deepStrictEqual((await rig.core.getTask(a.taskId)).plannedPaths, ["src/file.ts"]);
  }
  await rig.core.updateTaskPlan(b.taskId, ["src/File.ts"]);
  deepStrictEqual((await rig.core.status()).plannedOverlaps, []);
  await rejects(rig.core.updateTaskPlan("missing", []), /unknown task/);
});

test("plan route accepts owner/admin and rejects anonymous, cross-agent, runner, sidecar and revoked tokens", async () => {
  const rig = makeRig();
  const a = await rig.core.createTask({ agent: "a" });
  const b = await rig.core.createTask({ agent: "b" });
  const path = `/tasks/${a.taskId}/plan`;
  const call = (token?: string, body: unknown = { plannedPaths: ["shared.txt"] }, route = path) =>
    handleRoute(rig.services, neutralRequest("POST", route, body, token));
  strictEqual((await call()).status, 401);
  strictEqual((await call(undefined, {}, "/tasks/missing/plan")).status, 401);
  strictEqual((await call(b.token.plaintext)).status, 403);
  strictEqual((await call("runner-t")).status, 401);
  strictEqual((await call("sidecar-t")).status, 401);
  strictEqual((await call(a.token.plaintext)).status, 200);
  strictEqual((await call("admin-t", { plannedPaths: ["rate.py"] })).status, 200);
  strictEqual((await call("admin-t", { plannedPaths: ["../bad"] })).status, 400);
  strictEqual((await call("admin-t", null)).status, 400);
  strictEqual((await call("admin-t", {}, "/tasks/missing/plan")).status, 404);
  await rig.core.revokeAgentToken(a.agentId);
  strictEqual((await call(a.token.plaintext)).status, 401);
  deepStrictEqual((await rig.core.getTask(a.taskId)).plannedPaths, ["rate.py"]);
});
