/* Tests for the pair-safety decision (codex C-1334). Run with:
     cd prototype/ui && node --test        (or: npm test)
   No dependencies: node:test + assert only. The test loads the exact module
   the browser uses (pair-status.js). Passing the tests/ directory as an
   argument does not work on Node >= 24: --test positional args are glob
   patterns, and a bare directory name matches the directory itself. */
"use strict";

var test = require("node:test");
var assert = require("node:assert/strict");
var logic = require("../pair-status.js");

var HA = "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a";
var HB = "b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2";
var HC = "c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3";
var OLD_A = "0ld0ld0ld0ld0ld0ld0ld0ld0ld0ld0ld0ld0ld";

/* Every agent gets perfect individual test evidence on purpose: the point of
   C-1334 is that this must never promote a pair on its own. */
function greenAgent(id, head) {
  return { agentId: id, testEvidence: { command: "npm test", exitCode: 0, head: head, at: "2026-10-03T14:00:00.000Z" } };
}

function statusWith(pairs, heads) {
  return { heads: heads, pairs: pairs, warnings: [], radarLog: [] };
}

function pairView(a, b, ha, hb, status, extra) {
  var view = {
    pair: [a, b].sort(),
    heads: {},
    status: status,
    checkedAt: "2026-10-03T14:05:00.000Z",
    stale: false,
    activeWarningIds: [],
  };
  view.heads[a] = ha;
  view.heads[b] = hb;
  return Object.assign(view, extra || {});
}

var A = "agent-a";
var B = "agent-b";

test("conflict(kind test): both agents individually green still renders Conflict", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var status = statusWith(
    [pairView(A, B, HA, HB, "conflict", { kind: "test", evidence: { tests_collected: 8, tests_failed: 2 } })],
    heads
  );
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), status);
  assert.equal(st.type, "conflict");
  assert.ok(st.why.length > 0);
});

test("unknown pair result renders Unknown — not safe, not clean, despite green agents", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var status = statusWith(
    [pairView(A, B, HA, HB, "unknown", { evidence: "combined test run timed out" })],
    heads
  );
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), status);
  assert.equal(st.type, "unknown");
  assert.ok(st.why.length > 0);
});

test("clean at current heads with collected tests renders Clean", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var status = statusWith(
    [pairView(A, B, HA, HB, "clean", { coverage: { tests_collected: 3, tests_failed: 0 } })],
    heads
  );
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), status);
  assert.equal(st.type, "clean");
  assert.ok(/3 tests collected/.test(st.why));
});

test("clean WITHOUT recorded combined tests stays Not checked — individual evidence never promotes", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var status = statusWith(
    [pairView(A, B, HA, HB, "clean", { evidence: "merge-tree clean; no tests were run" })],
    heads
  );
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), status);
  assert.equal(st.type, "not_checked");
});

test("clean with tests_collected 0 stays Not checked (zero tests is not a pass)", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var status = statusWith(
    [pairView(A, B, HA, HB, "clean", { coverage: { tests_collected: 0 } })],
    heads
  );
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), status);
  assert.equal(st.type, "not_checked");
});

test("result recorded at older heads (stale) is Not checked, even when status was clean", function () {
  var heads = {};
  heads[A] = HA; // agent A has moved on since the check
  heads[B] = HB;
  var status = statusWith(
    [pairView(A, B, OLD_A, HB, "clean", { coverage: { tests_collected: 5 } })],
    heads
  );
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), status);
  assert.equal(st.type, "not_checked");
});

test("explicit stale flag forces Not checked even with matching heads", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var status = statusWith(
    [pairView(A, B, HA, HB, "clean", { stale: true, coverage: { tests_collected: 5 } })],
    heads
  );
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), status);
  assert.equal(st.type, "not_checked");
});

test("no pair view at all is Not checked, even with both agents green", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var status = statusWith([], heads);
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), status);
  assert.equal(st.type, "not_checked");
});

test("not_checked pair result is Not checked", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var status = statusWith([pairView(A, B, HA, HB, "not_checked")], heads);
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), status);
  assert.equal(st.type, "not_checked");
});

test("a missing head means nothing to compare: Not checked", function () {
  var heads = {};
  heads[A] = HA; // B has not pushed
  var status = statusWith([], heads);
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, null), status);
  assert.equal(st.type, "not_checked");
});

test("positional heads.a / heads.b from older data are tolerated (contract order)", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var view = {
    pair: [A, B],
    heads: { a: HA, b: HB },
    status: "clean",
    coverage: { tests_collected: 2 },
    checkedAt: "2026-10-03T14:05:00.000Z",
    stale: false,
    activeWarningIds: [],
  };
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), statusWith([view], heads));
  assert.equal(st.type, "clean");

  /* reversed pair order must still map positional heads correctly */
  var reversed = Object.assign({}, view, { pair: [B, A], heads: { a: HB, b: HA } });
  var st2 = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), statusWith([reversed], heads));
  assert.equal(st2.type, "clean");

  /* positional heads that contradict the current heads are stale */
  var wrong = Object.assign({}, view, { heads: { a: OLD_A, b: HB } });
  var st3 = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), statusWith([wrong], heads));
  assert.equal(st3.type, "not_checked");
});

test("keyed heads win over positional heads when both are present", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var view = {
    pair: [A, B],
    heads: {},
    status: "clean",
    coverage: { tests_collected: 2 },
    checkedAt: "2026-10-03T14:05:00.000Z",
    stale: false,
    activeWarningIds: [],
  };
  view.heads.a = OLD_A;
  view.heads.b = OLD_A;
  view.heads[A] = HA;
  view.heads[B] = HB;
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), statusWith([view], heads));
  assert.equal(st.type, "clean");
});

test("pair match works regardless of pair element order", function () {
  var heads = {};
  heads[A] = HA;
  heads[B] = HB;
  var view = pairView(B, A, HB, HA, "conflict", { kind: "textual" });
  var st = logic.pairStatus(greenAgent(A, HA), greenAgent(B, HB), statusWith([view], heads));
  assert.equal(st.type, "conflict");
});
