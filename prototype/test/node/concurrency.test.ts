/**
 * Concurrency & Race Condition Resilience unit tests under plain node --test.
 * Verifies exact-SHA receipts, idempotent push deduping, stale-head refusal,
 * and main advancement receipt invalidation against provider-neutral fakes.
 */

import { test } from "node:test";
import { ok, strictEqual } from "node:assert";
import type { CoordinatorModel } from "../../src/core/model.js";
import { makeRig } from "./fakes.js";

test("concurrency: recordPush generates exact-SHA receipt on new commit", async () => {
  const rig = makeRig();
  await rig.core.setup();
  const created = await rig.core.createTask({ agent: "worker-concurrency" });
  const commit1 = rig.git.commit(created.fork.name, "first commit on fork");

  const pushResult = await rig.core.recordPush({
    agent: created.agentId,
    fork: created.fork.name,
    sha: commit1,
    ref: "refs/heads/main",
  });

  strictEqual(pushResult.accepted, true, "push must be accepted");
  strictEqual(pushResult.deduped, false, "first push of commit must not be deduped");
  strictEqual(pushResult.agent, created.agentId);
  strictEqual(pushResult.heads[created.agentId], commit1, "head must advance to commit1");

  // Receipt verification
  ok(pushResult.receipt, "receipt must be returned in push result");
  strictEqual(pushResult.receipt.id, `receipt-${created.agentId}-${commit1}`);
  strictEqual(pushResult.receipt.sha, commit1);
  strictEqual(pushResult.receipt.status, "valid");

  // Verify receipt is persisted in the model
  const stored = await rig.store.get<CoordinatorModel>("model");
  ok(stored && stored.receipts[pushResult.receipt.id], "receipt must be stored in model.receipts");
  strictEqual(stored.receipts[pushResult.receipt.id].status, "valid");
  strictEqual(stored.receipts[pushResult.receipt.id].agentId, created.agentId);
  strictEqual(stored.receipts[pushResult.receipt.id].sha, commit1);
});

test("concurrency: idempotent push returns deduped=true and existing valid receipt", async () => {
  const rig = makeRig();
  await rig.core.setup();
  const created = await rig.core.createTask({ agent: "worker-dedup" });
  const commit1 = rig.git.commit(created.fork.name, "commit to dedup");

  const firstPush = await rig.core.recordPush({
    agent: created.agentId,
    fork: created.fork.name,
    sha: commit1,
  });
  strictEqual(firstPush.accepted, true);
  strictEqual(firstPush.deduped, false);
  ok(firstPush.receipt);

  // Re-push exact same commit (webhook redelivery or retry)
  const secondPush = await rig.core.recordPush({
    agent: created.agentId,
    fork: created.fork.name,
    sha: commit1,
  });

  strictEqual(secondPush.accepted, true, "deduped push must still be accepted");
  strictEqual(secondPush.deduped, true, "re-push must report deduped=true");
  strictEqual(secondPush.agent, created.agentId);
  ok(secondPush.receipt, "receipt must be returned on deduped push");
  strictEqual(secondPush.receipt.id, firstPush.receipt.id, "receipt ID must match original");
  strictEqual(secondPush.receipt.status, "valid");
});

test("concurrency: stale-head refusal rejects out-of-order ancestor push", async () => {
  const rig = makeRig();
  await rig.core.setup();
  const created = await rig.core.createTask({ agent: "worker-stale" });

  // Create commit 1, then commit 2 (child of commit 1)
  const commit1 = rig.git.commit(created.fork.name, "commit 1 (ancestor)");
  const commit2 = rig.git.commit(created.fork.name, "commit 2 (child)");

  // Delivery arrives out of order: commit 2 arrives first!
  const pushCommit2 = await rig.core.recordPush({
    agent: created.agentId,
    fork: created.fork.name,
    sha: commit2,
  });
  strictEqual(pushCommit2.accepted, true, "commit 2 push accepted first");
  strictEqual(pushCommit2.deduped, false);
  strictEqual(pushCommit2.heads[created.agentId], commit2);

  // Now delayed delivery of commit 1 arrives: commit 1 is an ancestor of the current head (commit 2).
  // Because commit 1 was never seen by this coordinator, it is not deduped, but must be refused as stale!
  const pushCommit1 = await rig.core.recordPush({
    agent: created.agentId,
    fork: created.fork.name,
    sha: commit1,
  });

  strictEqual(pushCommit1.accepted, false, "stale ancestor push must be REFUSED");
  strictEqual(pushCommit1.deduped, false, "stale ancestor push is not deduped");
  strictEqual(pushCommit1.agent, created.agentId);
  strictEqual(pushCommit1.heads[created.agentId], commit2, "head must remain commit 2, not rewound to commit 1");

  // Verify model head was NOT rewound
  const stored = await rig.store.get<CoordinatorModel>("model");
  ok(stored);
  strictEqual(stored.heads[created.agentId], commit2, "model head must stay at commit 2");
  strictEqual(stored.agents[created.agentId].head, commit2);
});

test("concurrency: canonical main advancement invalidates all existing receipts", async () => {
  const rig = makeRig();
  const setup = await rig.core.setup();
  const canonicalName = setup.canonical.name;

  // Agent 1 pushes commit
  const agent1 = await rig.core.createTask({ agent: "agent-1" });
  const a1Commit = rig.git.commit(agent1.fork.name, "agent 1 commit");
  const a1Push = await rig.core.recordPush({ agent: agent1.agentId, fork: agent1.fork.name, sha: a1Commit });
  strictEqual(a1Push.accepted, true);
  strictEqual(a1Push.receipt?.status, "valid");

  // Agent 2 pushes commit
  const agent2 = await rig.core.createTask({ agent: "agent-2" });
  const a2Commit = rig.git.commit(agent2.fork.name, "agent 2 commit");
  const a2Push = await rig.core.recordPush({ agent: agent2.agentId, fork: agent2.fork.name, sha: a2Commit });
  strictEqual(a2Push.accepted, true);
  strictEqual(a2Push.receipt?.status, "valid");

  // Check stored receipts are valid
  let stored = await rig.store.get<CoordinatorModel>("model");
  ok(stored);
  strictEqual(stored.receipts[`receipt-${agent1.agentId}-${a1Commit}`].status, "valid");
  strictEqual(stored.receipts[`receipt-${agent2.agentId}-${a2Commit}`].status, "valid");

  // Now canonical main advances (new commit merged/pushed to canonical repo)
  const canonicalCommit = rig.git.commit(canonicalName, "canonical main merge");
  const mainAdvanceResult = await rig.core.recordPush({
    fork: canonicalName,
    sha: canonicalCommit,
  });

  strictEqual(mainAdvanceResult.accepted, true, "canonical push must be accepted");
  strictEqual(mainAdvanceResult.agent, "canonical");

  // Inspect persisted receipts: all existing receipts must be marked invalidated
  stored = await rig.store.get<CoordinatorModel>("model");
  ok(stored);
  strictEqual(stored.receipts[`receipt-${agent1.agentId}-${a1Commit}`].status, "invalidated", "agent 1 receipt must be invalidated");
  strictEqual(stored.receipts[`receipt-${agent2.agentId}-${a2Commit}`].status, "invalidated", "agent 2 receipt must be invalidated");
});
