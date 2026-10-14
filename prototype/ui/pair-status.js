/* Pure pair-safety logic for the Agent Branches review UI. No DOM, no fetch,
   so node --test can load the same code the browser uses (codex C-1334).
   A pair's status comes ONLY from that pair's own radar result in /status
   (status.pairs, L1 CONTRACT.md v0.1 PairStatusView). Individual per-agent
   test evidence is never an input here: two agents that are each green on
   their own can still clash when their changes are combined. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else if (root) root.AgentBranchesPairStatus = api;
})(typeof self !== "undefined" ? self : this, function () {
  function coversPair(pair, a, b) {
    return (
      Array.isArray(pair) &&
      ((pair[0] === a && pair[1] === b) || (pair[0] === b && pair[1] === a))
    );
  }

  /* Per-agent heads are keyed by agentId per the contract
     (heads[agentId]); positional heads.a / heads.b from older data are
     tolerated as a fallback, matched through the pair order. */
  function headFor(view, agentId) {
    var heads = (view && view.heads) || {};
    if (Object.prototype.hasOwnProperty.call(heads, agentId) && heads[agentId] != null) {
      return heads[agentId];
    }
    var pair = (view && Array.isArray(view.pair)) ? view.pair : [];
    if (pair[0] === agentId && heads.a != null) return heads.a;
    if (pair[1] === agentId && heads.b != null) return heads.b;
    return null;
  }

  /* Positive evidence that the radar's combined test run actually collected
     and ran tests: a numeric tests_collected recorded on the pair result
     (runner coverage / structured evidence). A bare string evidence, an
     absent coverage, or a count of 0 never counts. */
  function collectedTests(view) {
    var sources = [view && view.coverage, view && view.evidence];
    for (var i = 0; i < sources.length; i++) {
      var s = sources[i];
      if (s && typeof s === "object" && !Array.isArray(s)) {
        if (typeof s.tests_collected === "number") return s.tests_collected;
        if (typeof s.testsCollected === "number") return s.testsCollected;
      }
    }
    return null;
  }

  function checkedAtCurrentHeads(view, status) {
    var current = (status && status.heads) || {};
    var pair = (view && Array.isArray(view.pair)) ? view.pair : [];
    if (pair.length !== 2) return false;
    for (var i = 0; i < pair.length; i++) {
      var now = current[pair[i]];
      var checked = headFor(view, pair[i]);
      if (!now || !checked || checked !== now) return false;
    }
    return true;
  }

  function fresh(view, status) {
    return !view.stale && checkedAtCurrentHeads(view, status);
  }

  var KIND_WORDS = { textual: "textual conflict", test: "semantic conflict" };

  function clip(text) {
    return text.length > 160 ? text.slice(0, 157) + "…" : text;
  }

  /* Evidence is either a string or a structured record
     ({tests_collected, tests_failed, details}); both are surfaced so a
     semantic (test) conflict shows which combined tests failed and why. */
  function detail(view) {
    var bits = [];
    if (view.kind) bits.push(KIND_WORDS[view.kind] || "kind: " + view.kind);
    var ev = view.evidence;
    if (typeof ev === "string" && ev) {
      bits.push(clip(ev));
    } else if (ev && typeof ev === "object" && !Array.isArray(ev)) {
      var failed = typeof ev.tests_failed === "number" ? ev.tests_failed : ev.testsFailed;
      var total = typeof ev.tests_collected === "number" ? ev.tests_collected : ev.testsCollected;
      if (typeof failed === "number" && failed > 0 && typeof total === "number") {
        bits.push(failed + " of " + total + " combined tests failed");
      }
      if (typeof ev.details === "string" && ev.details) bits.push(clip(ev.details));
    }
    return bits.length ? " (" + bits.join("; ") + ")" : "";
  }

  var NOT_CHECKED_YET =
    "These two changes have not been compared at their latest versions yet.";

  /* A lost push (CONTRACT 0.1.3 silent-callback guard) means the agent's
     true head is UNKNOWN: the recorded head may be behind reality and every
     stored result for that agent is suspect. This pair can never be clean,
     and the server-side forcing (not_checked + unprocessedReason on the pair
     view) is matched here from status.unprocessedPushes as a client-side
     gate, so older/cached pair views cannot present as current either. */
  function lostRecordFor(a, b, status) {
    var list = Array.isArray(status.unprocessedPushes) ? status.unprocessedPushes : [];
    for (var i = 0; i < list.length; i++) {
      var r = list[i];
      if (r && (r.agentId === a || r.agentId === b)) {
        return { agentId: r.agentId, record: r };
      }
    }
    return null;
  }

  function lostPushWhy(lost) {
    var r = lost.record;
    var bits = [];
    if (r.lastError) bits.push(String(r.lastError));
    if (typeof r.attempts === "number") {
      bits.push(r.attempts + " delivery attempt" + (r.attempts === 1 ? "" : "s"));
    }
    var detail = bits.length ? " (" + bits.join("; ") + ")" : "";
    return (
      lost.agentId +
      "'s latest change is UNKNOWN: a push notification was lost" + detail +
      ". This pair cannot be called safe until the push is delivered and re-checked."
    );
  }

  /* Decide the badge for one pair of agents from /status alone. */
  function pairStatus(agentA, agentB, status) {
    status = status || {};
    var a = agentA.agentId;
    var b = agentB.agentId;
    var heads = status.heads || {};

    var lost = lostRecordFor(a, b, status);
    if (lost) {
      return { type: "not_checked", why: lostPushWhy(lost) };
    }

    if (!heads[a] || !heads[b]) {
      return {
        type: "not_checked",
        why: "At least one of these agents has not pushed a change yet, so there is nothing to compare.",
      };
    }

    var list = Array.isArray(status.pairs) ? status.pairs : [];
    var view = null;
    for (var i = 0; i < list.length; i++) {
      if (coversPair(list[i].pair, a, b)) {
        view = list[i];
        break;
      }
    }
    if (!view) return { type: "not_checked", why: NOT_CHECKED_YET };

    /* The server records WHY the pair was forced to not_checked (codex
       C-1357); surface it instead of the generic staleness line. */
    if (view.unprocessedReason) {
      return {
        type: "not_checked",
        why:
          "This pair is not checked, and never shown safe: " + String(view.unprocessedReason) +
          " A fresh comparison at the true latest changes is needed first.",
      };
    }

    if (!fresh(view, status)) {
      return {
        type: "not_checked",
        why:
          NOT_CHECKED_YET +
          " A comparison exists, but one of the changes has moved on since it was made.",
      };
    }

    if (view.status === "conflict") {
      return {
        type: "conflict",
        why:
          "Tested together at their latest changes, these two clash" +
          detail(view) +
          ". One of them needs fixing before they can be combined.",
      };
    }

    if (view.status === "unknown") {
      return {
        type: "unknown",
        why:
          "Checked together, but not proven safe" +
          detail(view) +
          ". Do not treat this pair as safe.",
      };
    }

    if (view.status === "clean") {
      var collected = collectedTests(view);
      if (collected != null && collected > 0) {
        return {
          type: "clean",
          why:
            "Combined at their latest changes, the tests ran together " +
            "(" + collected + " test" + (collected === 1 ? "" : "s") + " collected) and found no conflict.",
        };
      }
      return {
        type: "not_checked",
        why:
          "No merge conflict, but no combined tests ran — so the pair is not proven to work together " +
          "and stays not checked.",
      };
    }

    return { type: "not_checked", why: NOT_CHECKED_YET };
  }

  return { pairStatus: pairStatus, collectedTests: collectedTests };
});
