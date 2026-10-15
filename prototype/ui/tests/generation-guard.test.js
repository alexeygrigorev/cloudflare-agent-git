/* Tests for request-guard.js (C-1385): the single-flight generation guard —
   an older response that resolves after a newer one never overwrites newer
   state — and /status freshness — a failed status fetch is surfaced as a
   stale error and is never read as clean. Run with:
     cd prototype/ui && node --test        (or: npm test)
   No dependencies: node:test + assert only; the test loads the exact module
   the browser uses. The last test is a tripwire on ui.js itself: the
   swallowed `loadStatus().catch(... -> null)` this guard replaces must stay
   gone. */
"use strict";

var test = require("node:test");
var assert = require("node:assert/strict");
var fs = require("node:fs");
var path = require("node:path");
var Guard = require("../request-guard.js");

/* Use the real UI render/poll path; actual browser geometry is checked too. */
function planUiHarness(initial, task) {
  var vm = require("node:vm");
  var nodes = {};
  function node(id) {
    if (!nodes[id]) nodes[id] = { innerHTML: "", textContent: "", hidden: true, value: "",
      attrs: {}, addEventListener: function () {},
      getAttribute: function (key) { return this.attrs[key]; },
      setAttribute: function (key, value) { this.attrs[key] = value; },
      querySelectorAll: function () { return []; } };
    return nodes[id];
  }
  var status = initial;
  var failed = false;
  var poll;
  var context = { URLSearchParams: URLSearchParams, Date: Date, Promise: Promise,
    setTimeout: function () { return 1; }, clearTimeout: function () {},
    setInterval: function (fn) { poll = fn; return 1; }, clearInterval: function () {},
    document: { hidden: false, addEventListener: function () {}, getElementById: node,
      querySelectorAll: function () { return []; } },
    fetch: function (url) { var isStatus = /\/status$/.test(url); return Promise.resolve(failed && isStatus ? { ok: false, status: 503 } :
      { ok: true, json: function () { return Promise.resolve(isStatus ? status : task); } }); },
    window: { location: { search: task ? "?id=" + task.taskId : "", protocol: "http:" },
      localStorage: { getItem: function () { return null; } },
      AgentBranchesViewLogic: require("../view-logic.js"), AgentBranchesRequestGuard: Guard,
      AgentBranchesPairStatus: require("../pair-status.js"), AgentBranchesAuth: require("../auth.js") } };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "ui.js"), "utf8"), context);
  return { nodes: nodes, boot: function () { if (task) context.window.AgentBranchesUI.bootTask(); else context.window.AgentBranchesUI.bootIndex(); },
    poll: function () { poll(); }, fail: function () { failed = true; },
    setStatus: function (value) { status = value; failed = false; } };
}

test("real overview renders pre-push plans, escapes paths, clears overlaps, and labels stale plans", async function () {
  var dangerous = "<img src=x onerror=alert(1)>";
  var status = { agents: [{ agentId: "a", taskId: "ta", head: "h", plannedPaths: [dangerous] },
    { agentId: "b", taskId: "tb", head: "h", plannedPaths: [] },
    { agentId: "c", taskId: "tc", head: "h", plannedPaths: null }],
    heads: { a: "h", b: "h", c: "h" }, warnings: [], pairs: [],
    plannedOverlaps: [{ agents: ["a", "b"], paths: [dangerous] }] };
  var ui = planUiHarness(status);
  var settled = function () { return new Promise(function (resolve) { setImmediate(resolve); }); };
  ui.boot(); await settled();
  assert.match(ui.nodes["planned-work"].innerHTML, /Planned overlap — agree ownership/);
  assert.match(ui.nodes["planned-work"].innerHTML, /not a proven Git conflict/);
  assert.match(ui.nodes["planned-work"].innerHTML, /&lt;img/);
  assert.doesNotMatch(ui.nodes["planned-work"].innerHTML, /<img/);
  assert.match(ui.nodes.agents.innerHTML, /no files currently declared/);
  assert.match(ui.nodes.agents.innerHTML, /not declared\. File ownership is unknown/);
  assert.doesNotMatch(ui.nodes.pairs.innerHTML, /badge clean/);
  ui.fail(); ui.poll(); await settled();
  assert.match(ui.nodes["planned-work"].innerHTML, /Last reported planned overlap/);
  assert.match(ui.nodes["planned-work"].innerHTML, /Current plans are unknown/);
  status = JSON.parse(JSON.stringify(status)); status.plannedOverlaps = [];
  ui.setStatus(status); ui.poll(); await settled();
  assert.doesNotMatch(ui.nodes["planned-work"].innerHTML, /Planned overlap — agree ownership/);
  assert.match(ui.nodes["planned-work"].innerHTML, /No shared planned files reported/);
});

test("malformed overlap records stay unknown in the real overview", async function () {
  var ui = planUiHarness({ agents: [], heads: {}, pairs: [], warnings: [],
    plannedOverlaps: [{ agents: ["a", "b", "c"], paths: ["x"] }] });
  ui.boot(); await new Promise(setImmediate);
  assert.match(ui.nodes["planned-work"].innerHTML, /unknown: 1 planned-overlap record/);
  assert.doesNotMatch(ui.nodes["planned-work"].innerHTML, /No shared planned files reported/);
});

test("task plans are scoped, preserve safety evidence and become historical on failure", async function () {
  var status = { agents: [{ agentId: "a", plannedPaths: ["own.txt"] },
    { agentId: "b", plannedPaths: [] }, { agentId: "c", plannedPaths: null }], heads: {}, pairs: [], warnings: [],
    plannedOverlaps: [{ agents: ["a", "b"], paths: ["own.txt"] }, { agents: ["b", "c"], paths: ["other.txt"] }] };
  var task = { taskId: "ta", agentId: "a", agent: { agentId: "a", head: null, pushes: 0 }, intent: "coordinate" };
  var ui = planUiHarness(status, task);
  var tick = function () { return new Promise(setImmediate); };
  ui.boot(); await tick();
  assert.match(ui.nodes["planned-work"].innerHTML, /Planned files:.*own.txt/);
  assert.match(ui.nodes["planned-work"].innerHTML, /Planned overlap/);
  assert.doesNotMatch(ui.nodes["planned-work"].innerHTML, /other.txt/);
  var verdict = ui.nodes["task-verdict"].innerHTML;
  var evidence = ui.nodes.evidence.innerHTML;
  var noPlans = JSON.parse(JSON.stringify(status)); delete noPlans.plannedOverlaps;
  noPlans.agents.forEach(function (agent) { delete agent.plannedPaths; });
  ui.setStatus(noPlans); ui.poll(); await tick();
  assert.equal(ui.nodes["task-verdict"].innerHTML, verdict);
  assert.equal(ui.nodes.evidence.innerHTML, evidence);
  status.agents[0].plannedPaths = [];
  ui.setStatus(status); ui.poll(); await tick();
  assert.match(ui.nodes["planned-work"].innerHTML, /no files currently declared/);
  status.agents[0].plannedPaths = null;
  ui.setStatus(status); ui.poll(); await tick();
  assert.match(ui.nodes["planned-work"].innerHTML, /not declared\. File ownership is unknown/);
  status.agents[0].plannedPaths = ["own.txt"];
  ui.setStatus(status); ui.poll(); await tick();
  ui.fail(); ui.poll(); await tick();
  assert.match(ui.nodes["planned-work"].innerHTML, /Last reported planned files/);
  assert.match(ui.nodes["planned-work"].innerHTML, /Last reported planned overlap/);
  assert.match(ui.nodes["planned-work"].innerHTML, /Current plans are unknown/);
});

test("first status failure asserts no historical plan on either page", async function () {
  var task = { taskId: "ta", agentId: "a", agent: { agentId: "a" } };
  for (var detail of [undefined, task]) {
    var ui = planUiHarness({}, detail); ui.fail(); ui.boot(); await new Promise(setImmediate);
    assert.match(ui.nodes["planned-work"].innerHTML, /unknown.*status has not loaded/);
    assert.doesNotMatch(ui.nodes["planned-work"].innerHTML, /Last reported|not declared|last successful load/);
  }
});

function delay(ms) {
  return new Promise(function (resolve) {
    setTimeout(resolve, ms);
  });
}

/* ---------- generation tracker: units ---------- */

test("begin hands out generations in launch order", function () {
  var t = Guard.createGenTracker();
  assert.equal(t.begin(), 1);
  assert.equal(t.begin(), 2);
  assert.equal(t.begin(), 3);
});

test("in-order responses both apply — the latest one wins", function () {
  var t = Guard.createGenTracker();
  var a = t.begin();
  var b = t.begin();
  assert.equal(t.settle(a), true); /* A arrives first and applies */
  assert.equal(t.settle(b), true); /* B arrives later and applies over it */
  assert.equal(t.isStale(b), false);
});

test("settle marks completion even when it reports stale", function () {
  var t = Guard.createGenTracker();
  var a = t.begin();
  var b = t.begin();
  t.settle(b); /* B (launched later) completes first */
  assert.equal(t.isStale(a), true); /* A is now out of order */
  assert.equal(t.settle(a), false); /* and is dropped */
  assert.equal(t.isStale(a), true); /* the drop is recorded as a completion */
});

test("complete is monotonic — an older completion never lowers the bar", function () {
  var t = Guard.createGenTracker();
  var a = t.begin();
  var b = t.begin();
  t.complete(b);
  t.complete(a); /* late, out of order */
  assert.equal(t.isStale(b), false);
  assert.equal(t.isStale(a), true);
  assert.equal(t.isStale(t.begin()), false); /* a fresh request is never stale */
});

/* ---------- generation guard: the out-of-order scenario (C-1385 a) ---------- */

test("out-of-order: request A (launched t=0, arrives t=200) is ignored; state reflects request B (launched t=50, arrives t=100)", async function () {
  var t = Guard.createGenTracker();
  var state = null;
  /* The apply rule ui.js uses: settle first, drop when out of order. */
  function launch(arrivesAfterMs, payload) {
    var gen = t.begin();
    return delay(arrivesAfterMs).then(function () {
      if (!t.settle(gen)) return "ignored";
      state = payload;
      return "applied";
    });
  }

  var a = launch(200, "response-A"); /* launched at t=0, arrives t=200 */
  await delay(50);
  var b = launch(50, "response-B"); /* launched at t=50, arrives t=100 */

  var outcomes = await Promise.all([a, b]);
  assert.deepEqual(outcomes, ["ignored", "applied"]);
  assert.equal(state, "response-B"); /* A's late resolution never overwrote B */
});

test("a late FAILURE from an older request is ignored after a newer one settled", function () {
  var t = Guard.createGenTracker();
  var lastError = null;
  var a = t.begin();
  var b = t.begin();
  t.settle(b); /* newer request completed successfully */
  /* ui.js re-records lastError only when settle(gen) is true: */
  if (t.settle(a)) lastError = new Error("stale request failed");
  assert.equal(lastError, null); /* A's late failure was dropped */
  assert.equal(t.isStale(a), true);
});

/* ---------- status freshness: units (C-1385 b) ---------- */

var ERR = new Error("request failed: HTTP 503 for /status");

test("a failed status fetch marks the view stale and never clean", function () {
  var f = Guard.createStatusFreshness();
  assert.equal(f.isStale(), false); /* starts fresh */
  assert.equal(f.describe(), null);
  f.markStale(ERR, 1234);
  assert.equal(f.isStale(), true);
  var d = f.describe();
  assert.notEqual(d, null); /* there is always an explicit stale-error */
  assert.equal(d.error, ERR);
  assert.equal(d.atMs, 1234);
});

test("only a later successful fetch clears the stale error", function () {
  var f = Guard.createStatusFreshness();
  f.markStale(ERR, 1);
  f.markFresh();
  assert.equal(f.isStale(), false);
  assert.equal(f.describe(), null);
  f.markFresh(); /* idempotent */
  assert.equal(f.describe(), null);
});

test("repeated failures keep the latest error and time", function () {
  var f = Guard.createStatusFreshness();
  var first = new Error("request failed: HTTP 503 for /status");
  var second = new Error("request failed: HTTP 502 for /status");
  f.markStale(first, 1000);
  f.markStale(second, 2000);
  var d = f.describe();
  assert.equal(d.error, second);
  assert.equal(d.atMs, 2000);
});

test("markStale tolerates a missing error and time", function () {
  var f = Guard.createStatusFreshness();
  f.markStale();
  var d = f.describe();
  assert.equal(f.isStale(), true);
  assert.match(d.error.message, /status fetch failed/);
  assert.equal(typeof d.atMs, "number");
});

/* ---------- the refresh rule ui.js implements: failure is never clean ---------- */

test("refresh rule: status failure records lastError, marks the view stale-error; a later success clears it", async function () {
  var t = Guard.createGenTracker();
  var fresh = Guard.createStatusFreshness();
  var ui = { lastError: null, rendered: null };

  function refresh(p) {
    var gen = t.begin();
    return p.then(
      function (statusResult) {
        if (!t.settle(gen)) return "ignored";
        if (!statusResult.ok) {
          fresh.markStale(statusResult.error, 1);
          ui.lastError = statusResult.error;
          ui.rendered = { stale: fresh.describe() }; /* never a clean render */
          return "stale-error";
        }
        fresh.markFresh();
        ui.lastError = null;
        ui.rendered = { clean: true, status: statusResult.status };
        return "ok";
      },
      function (e) {
        if (!t.settle(gen)) return "ignored";
        ui.lastError = e;
        return "failed";
      }
    );
  }

  function statusServes(doc) {
    return Promise.resolve({ ok: true, status: doc });
  }
  function statusFails() {
    return Promise.resolve({ ok: false, error: ERR });
  }

  /* 1st poll succeeds: clean render, no error. */
  assert.equal(await refresh(statusServes({ agents: [{ agentId: "a" }] })), "ok");
  assert.equal(ui.lastError, null);
  assert.deepEqual(ui.rendered.clean, true);

  /* 2nd poll fails: explicit stale-error state, never clean. */
  assert.equal(await refresh(statusFails()), "stale-error");
  assert.equal(fresh.isStale(), true);
  assert.notEqual(fresh.describe(), null); /* the stale error is surfaced */
  assert.match(ui.lastError.message, /HTTP 503/);
  assert.equal(ui.rendered.clean, undefined); /* no clean render happened */
  assert.match(ui.rendered.stale.error.message, /HTTP 503/);

  /* 3rd poll succeeds: freshness and the clean view return. */
  assert.equal(await refresh(statusServes({ agents: [{ agentId: "a" }, { agentId: "b" }] })), "ok");
  assert.equal(fresh.isStale(), false);
  assert.equal(ui.lastError, null);
  assert.equal(ui.rendered.clean, true);
});

/* ---------- tripwire on ui.js itself (C-1385 & C-1399) ---------- */

test("ui.js keeps the guard wired, old swallow-to-null gone, and index stale downgrade active (C-1399)", function () {
  var src = fs.readFileSync(path.join(__dirname, "..", "ui.js"), "utf8");
  /* the exact swallow C-1385 forbids — status failures hidden as null: */
  assert.equal(src.indexOf("loadStatus().catch"), -1);
  assert.equal(src.indexOf("return null; })]"), -1);
  /* the guard and freshness are actually used by the refresh path: */
  assert.match(src, /Guard\.createGenTracker\(\)/);
  assert.match(src, /Guard\.createStatusFreshness\(\)/);
  assert.match(src, /genTracker\.settle\(gen\)/);
  assert.match(src, /statusFresh\.markStale\(/);
  assert.match(src, /statusFresh\.markFresh\(\)/);
  assert.match(src, /setStatusErrorView/);
  /* C-1399 index DOM negative fix: failure branch re-renders index when !currentTaskId */
  assert.match(src, /!currentTaskId\s*&&\s*lastStatus/, "status-failure branch re-renders index when on overview");
  assert.match(src, /stale\s*&&\s*badgeType\s*===\s*"clean"/, "clean pair badges downgraded to unknown when stale");
  /* both pages carry the banner element the guard writes to */
  ["index.html", "task.html"].forEach(function (page) {
    var html = fs.readFileSync(path.join(__dirname, "..", page), "utf8");
    assert.match(html, /id="status-error"/, page + " has the stale-error banner");
    assert.match(html, /request-guard\.js/, page + " loads request-guard.js");
  });
});

test("index pair badges: clean badges are downgraded to unknown when live status fails (C-1399)", function () {
  var fresh = Guard.createStatusFreshness();
  var pairResult = {
    pair: ["agent-1", "agent-2"],
    status: "clean",
    heads: { "agent-1": "h1", "agent-2": "h2" },
    coverage: { tests_collected: 5 },
  };
  var PairLogic = require("../pair-status.js");
  var statusDoc = {
    agents: [{ agentId: "agent-1", head: "h1" }, { agentId: "agent-2", head: "h2" }],
    heads: { "agent-1": "h1", "agent-2": "h2" },
    pairs: [pairResult],
  };

  function computeBadge(agentA, agentB, status, stale) {
    var st = PairLogic.pairStatus(agentA, agentB, status);
    var badgeType = st.type;
    var why = st.why;
    if (stale && badgeType === "clean") {
      badgeType = "unknown";
      why = why + " · live status could not be refreshed (" + stale.error.message + "); treated as unknown, not clean";
    }
    return { badgeType: badgeType, why: why };
  }

  /* 1. Fresh status: clean pair badge renders clean */
  var initial = computeBadge(statusDoc.agents[0], statusDoc.agents[1], statusDoc, fresh.describe());
  assert.equal(initial.badgeType, "clean");
  assert.match(initial.why, /found no conflict/);

  /* 2. Status fetch fails: stale error set -> clean downgraded to unknown (DOM negative) */
  fresh.markStale(new Error("HTTP 503 Service Unavailable"), 100);
  var staleRender = computeBadge(statusDoc.agents[0], statusDoc.agents[1], statusDoc, fresh.describe());
  assert.equal(staleRender.badgeType, "unknown");
  assert.notEqual(staleRender.badgeType, "clean");
  assert.match(staleRender.why, /treated as unknown, not clean/);

  /* 3. Later successful fetch clears stale -> badge returns to clean */
  fresh.markFresh();
  var recovered = computeBadge(statusDoc.agents[0], statusDoc.agents[1], statusDoc, fresh.describe());
  assert.equal(recovered.badgeType, "clean");
});
