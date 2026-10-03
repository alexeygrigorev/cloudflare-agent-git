/* Agent Branches — change story review UI (shared, vanilla JS, no frameworks).
   Two pages: index.html (overview from GET /status) and task.html?id= (change
   story from GET /tasks/:id). ?fixture=1 loads sample JSON from fixtures/.
   Unknown safety is never rendered as safe. */

"use strict";

(function () {
  var params = new URLSearchParams(window.location.search);
  var FIXTURE_NAME = params.get("fixture") || "";
  var FIXTURE = !!FIXTURE_NAME;
  var API = (params.get("api") || "").replace(/\/+$/, "");
  /* Pair safety logic is shared with node --test via pair-status.js. */
  var PairLogic = window.AgentBranchesPairStatus;

  /* ---------- small helpers ---------- */

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function shortSha(sha) {
    return sha ? String(sha).slice(0, 7) : "";
  }

  function shaHtml(sha) {
    if (!sha) return "<span class='muted'>none yet</span>";
    return "<code class='sha' title='" + esc(sha) + "'>" + esc(shortSha(sha)) + "</code>";
  }

  function fmtWhen(iso) {
    if (!iso) return "<span class='muted'>not recorded</span>";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "<span class='muted'>unknown time</span>";
    var abs = d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    var rel = relative(iso, d);
    return (
      "<time datetime='" + esc(iso) + "'>" + esc(abs) + "</time> <span class='muted small'>(" + esc(rel) + ")</span>"
    );
  }

  function relative(iso, d) {
    var s = Math.max(0, (Date.now() - d.getTime()) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + " min ago";
    if (s < 86400) return Math.floor(s / 3600) + " h ago";
    return Math.floor(s / 86400) + " d ago";
  }

  function plainRef(ref) {
    var m = /^refs\/heads\/(.+)$/.exec(String(ref || ""));
    return m ? m[1] : ref || "not recorded";
  }

  function taskHref(taskId) {
    var keep = FIXTURE ? "&fixture=" + encodeURIComponent(FIXTURE_NAME) : "";
    return "task.html?id=" + encodeURIComponent(taskId) + keep;
  }

  /* ---------- data loading ---------- */

  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error("request failed: HTTP " + r.status + " for " + url);
      return r.json();
    });
  }

  function fixturePath(name) {
    return FIXTURE_NAME === "1"
      ? "fixtures/" + name
      : "fixtures/" + encodeURIComponent(FIXTURE_NAME) + "-" + name;
  }

  function loadStatus() {
    return FIXTURE
      ? fetchJson(FIXTURE_NAME === "1" ? "fixtures/status.json" : "fixtures/status-" + encodeURIComponent(FIXTURE_NAME) + ".json")
      : fetchJson(API + "/status");
  }

  function loadTask(id) {
    if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(id)) {
      return Promise.reject(new Error("bad task id"));
    }
    var url = FIXTURE ? fixturePath(id + ".json") : API + "/tasks/" + encodeURIComponent(id);
    return fetchJson(url);
  }

  function showError(el, error, isFixture) {
    var hint = isFixture
      ? " Fixture files are loaded with fetch(), which browsers block when the page is opened directly from disk. Serve the folder over HTTP — see README-UI.md."
      : " Is the Worker running? Try: npx wrangler dev --local (from prototype/), then open this page with ?api=http://localhost:8787 if it is not served by the Worker yet.";
    el.hidden = false;
    el.innerHTML = "<strong>Could not load the data.</strong> " + esc(error.message) + esc(hint);
  }

  /* ---------- pair safety (never guess "safe") ----------
     Pair status comes ONLY from that pair's own radar result in /status
     (status.pairs, L1 CONTRACT.md v0.1). A pair is "clean" only when its own
     result says clean at the CURRENT heads of both agents and the result
     records a combined test run with collected tests. Individual per-agent
     test evidence is shown on the task page, but it never promotes a pair:
     two individually green agents can still clash when combined (the
     semantic-conflict case, codex C-1334). The decision lives in
     pair-status.js so node --test can exercise the exact same code. */

  function pairStatus(agentA, agentB, status) {
    return PairLogic.pairStatus(agentA, agentB, status);
  }

  var BADGES = {
    conflict: { cls: "conflict", label: "Conflict" },
    clean: { cls: "clean", label: "Clean — tests ran" },
    unknown: { cls: "unknown", label: "Unknown — not safe" },
    not_checked: { cls: "not_checked", label: "Not checked" },
  };

  function badgeHtml(type) {
    var b = BADGES[type];
    return "<span class='badge " + b.cls + "'>" + esc(b.label) + "</span>";
  }

  function ackHtml(warning, viewerAgentId) {
    var by = Array.isArray(warning.acknowledgedBy) ? warning.acknowledgedBy : [];
    var mine = viewerAgentId && by.indexOf(viewerAgentId) !== -1;
    if (mine) {
      var others = by.filter(function (n) { return n !== viewerAgentId; });
      return (
        "This agent acknowledged the warning " + fmtWhen(warning.acknowledgedAt) +
        (others.length ? " <span class='muted small'>(also acknowledged by " + others.map(esc).join(", ") + ")</span>" : "")
      );
    }
    if (by.length) {
      return (
        "Acknowledged by " + by.map(esc).join(", ") + " " + fmtWhen(warning.acknowledgedAt) +
        (viewerAgentId ? ", but <strong>not yet by this agent</strong>." : ".")
      );
    }
    return "<span class='muted'>Not acknowledged yet — the agent has not confirmed it saw this warning.</span>";
  }

  /* ---------- index page ---------- */

  function renderIndex(status) {
    var agents = (status.agents || []).slice().sort(function (x, y) {
      return String(x.agentId).localeCompare(String(y.agentId));
    });

    var canon = document.getElementById("canonical");
    canon.innerHTML = status.canonical && status.canonical.name
      ? "Shared starting repo: <code>" + esc(status.canonical.name) + "</code>"
      : "<span class='muted'>Shared starting repo not created yet.</span>";

    var cards = agents.map(function (ag) {
      var intent = ag.intent ? esc(ag.intent) : "<span class='muted'>Not stated yet</span>";
      return (
        "<article class='card' aria-label='Agent " + esc(ag.agentId) + "'>" +
        "<h3><code>" + esc(ag.agentId) + "</code></h3>" +
        "<p class='kv'><span>Doing:</span> " + intent + "</p>" +
        "<p class='kv'><span>Started from:</span> " +
        (ag.baseSha ? shaHtml(ag.baseSha) : "<span class='muted'>not recorded</span>") + "</p>" +
        "<p class='kv'><span>Latest change:</span> " + shaHtml(ag.head) + "</p>" +
        "<p class='kv'><span>Changes pushed:</span> " + esc(ag.pushes) +
        (ag.lastPushAt ? " <span class='muted small'>(last " + fmtWhen(ag.lastPushAt) + ")</span>" : "") +
        "</p>" +
        "<p class='actions'><a href='" + taskHref(ag.taskId) + "'>Read the change story →</a></p>" +
        "</article>"
      );
    });
    document.getElementById("agents").innerHTML =
      cards.length ? "<div class='cards'>" + cards.join("") + "</div>" : "<p class='muted'>No agent tasks yet.</p>";

    var pairs = [];
    for (var i = 0; i < agents.length; i++) {
      for (var j = i + 1; j < agents.length; j++) {
        var st = pairStatus(agents[i], agents[j], status);
        pairs.push(
          "<li class='pair'>" +
          "<span class='who'><code>" + esc(agents[i].agentId) + "</code> ↔ <code>" + esc(agents[j].agentId) + "</code></span> " +
          badgeHtml(st.type) +
          "<p class='why'>" + esc(st.why) + "</p>" +
          "</li>"
        );
      }
    }
    document.getElementById("pairs").innerHTML = pairs.length
      ? "<ul class='pair-list'>" + pairs.join("") + "</ul>"
      : "<p class='muted'>With fewer than two agents there is nothing to compare yet.</p>";

    var warnings = status.warnings || [];
    var rows = warnings.map(function (w) {
      var state = w.status === "active"
        ? "<span class='badge conflict'>Active</span>"
        : "<span class='badge not_checked'>Resolved</span>";
      return (
        "<tr>" +
        "<td><code>" + esc(w.id) + "</code></td>" +
        "<td><code>" + esc(w.pair.join(" ↔ ")) + "</code></td>" +
        "<td>" + esc(w.reason) + "</td>" +
        "<td>" + fmtWhen(w.createdAt) + "</td>" +
        "<td>" + state + (w.invalidatedAt ? " <span class='muted small'>" + fmtWhen(w.invalidatedAt) + "</span>" : "") + "</td>" +
        "<td>" + ackHtml(w) + "</td>" +
        "</tr>"
      );
    });
    document.getElementById("warnings-body").innerHTML = rows.join("");
    document.getElementById("warnings-section").hidden = rows.length === 0;
  }

  /* ---------- task page ---------- */

  function renderTask(task, status) {
    var agent = task.agent || {};
    var heads = (status && status.heads) || {};
    var currentHead = heads[agent.agentId] || agent.head || null;

    document.title = "Change story — " + (agent.agentId || task.taskId);

    var dl =
      "<dt>Agent</dt><dd><code>" + esc(agent.agentId || task.agentId) + "</code></dd>" +
      "<dt>Task</dt><dd><code>" + esc(task.taskId) + "</code></dd>" +
      "<dt>Doing</dt><dd>" +
      (agent.intent ? esc(agent.intent) : "<span class='muted'>Not stated yet</span>") + "</dd>" +
      "<dt>Started from</dt><dd>" +
      (agent.baseSha ? shaHtml(agent.baseSha) : "<span class='muted'>Not recorded yet</span>") + "</dd>" +
      "<dt>Latest change</dt><dd>" + shaHtml(currentHead) + "</dd>" +
      "<dt>Working copy</dt><dd><span class='small'>own fork <code>" + esc(task.forkName || agent.forkName) +
      "</code>, branch <code>" + esc(plainRef(task.ref || agent.ref)) + "</code></span></dd>" +
      "<dt>Task created</dt><dd>" + fmtWhen(task.createdAt) + "</dd>";
    document.getElementById("task-head").innerHTML = "<dl>" + dl + "</dl>";

    /* Story of changes */
    var log = Array.isArray(agent.pushLog) ? agent.pushLog : [];
    var changes;
    if (log.length) {
      changes =
        "<ol class='changes' reversed>" +
        log
          .slice()
          .reverse()
          .map(function (p) {
            return (
              "<li><span class='when'>" + fmtWhen(p.at) + "</span> — " + shaHtml(p.sha) +
              (p.message ? "<br><span class='muted'>" + esc(p.message) + "</span>" : "") +
              "</li>"
            );
          })
          .join("") +
        "</ol>";
    } else if (agent.pushes > 0 && agent.lastPushAt) {
      changes =
        "<p>" + fmtWhen(agent.lastPushAt) + " — " + shaHtml(currentHead) + "</p>" +
        "<p class='muted small'>" + esc(agent.pushes) + " change" + (agent.pushes === 1 ? "" : "s") +
        " pushed in total. The full list of each change is not recorded yet.</p>";
    } else {
      changes = "<p class='muted'>No changes pushed yet.</p>";
    }
    document.getElementById("changes").innerHTML = changes;

    /* Warnings received by this agent */
    var mine = ((status && status.warnings) || []).filter(function (w) {
      return Array.isArray(w.pair) && w.pair.indexOf(agent.agentId) !== -1;
    });
    var warnHtml;
    if (!mine.length) {
      warnHtml = "<p class='muted'>No warnings received.</p>";
    } else {
      warnHtml = mine
        .map(function (w) {
          var other = w.pair[0] === agent.agentId ? w.pair[1] : w.pair[0];
          var resolved = w.status !== "active";
          return (
            "<div class='warning" + (resolved ? " resolved" : "") + "'>" +
            (resolved
              ? "<span class='badge not_checked'>Resolved</span> "
              : "<span class='badge conflict'>Conflict — needs attention</span> ") +
            "<p><strong>" + esc(w.reason) + "</strong></p>" +
            "<p class='meta'>With <code>" + esc(other) + "</code> · sent " + fmtWhen(w.createdAt) +
            (resolved ? " · went away " + fmtWhen(w.invalidatedAt) : "") + "</p>" +
            "<p class='meta'>Acknowledgement: " + ackHtml(w, agent.agentId) + "</p>" +
            "</div>"
          );
        })
        .join("");
    }
    document.getElementById("warnings").innerHTML = warnHtml;

    /* Test provenance */
    var ev = agent.testEvidence;
    var evidence;
    if (ev) {
      var matchesHead = !currentHead || !ev.head || ev.head === currentHead;
      var passed = ev.exitCode === 0;
      evidence =
        "<div class='evidence'><dl>" +
        "<dt>Command</dt><dd><code>" + esc(ev.command) + "</code></dd>" +
        "<dt>Result</dt><dd>" +
        (passed
          ? "<span class='badge clean'>Passed</span>"
          : "<span class='badge unknown'>Failed — exit " + esc(ev.exitCode) + "</span>") +
        "</dd>" +
        "<dt>Tested change</dt><dd>" + shaHtml(ev.head) +
        (matchesHead
          ? " <span class='muted small'>(the latest change)</span>"
          : " <span class='muted small'>(an older change, not the latest)</span>") +
        "</dd>" +
        "<dt>When</dt><dd>" + fmtWhen(ev.at) + "</dd>" +
        "</dl>" +
        (!matchesHead || !passed
          ? "<p class='small' style='margin-bottom:0'><span class='badge unknown'>Unknown — not safe</span> " +
            "There is no passing test run for the latest change, so this change is not proven safe.</p>"
          : "") +
        "</div>";
    } else {
      evidence =
        "<div class='notice-unknown'>" +
        "<span class='badge unknown'>Unknown — not safe</span> " +
        "<p style='margin:0.4rem 0 0'>No test run is recorded for this change. Without a test run at the " +
        "latest change, safety is unknown — this is never shown as safe.</p></div>";
    }
    document.getElementById("evidence").innerHTML = evidence;

    initReview(task.taskId);
  }

  /* ---------- review decision (local only, per browser) ---------- */

  function reviewKey(taskId) {
    return "agent-branches-review:" + taskId;
  }

  function readReview(taskId) {
    try {
      var raw = window.localStorage.getItem(reviewKey(taskId));
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  function writeReview(taskId, value) {
    try {
      if (value === null) window.localStorage.removeItem(reviewKey(taskId));
      else window.localStorage.setItem(reviewKey(taskId), JSON.stringify(value));
      return true;
    } catch (e) {
      return false;
    }
  }

  var CHOICES = [
    { id: "approve", label: "Approve" },
    { id: "request_changes", label: "Request changes" },
    { id: "note", label: "Note" },
  ];

  function initReview(taskId) {
    var box = document.getElementById("review");
    var current = readReview(taskId);
    var selected = current ? current.decision : null;

    var buttons = CHOICES.map(function (c) {
      return (
        "<button type='button' data-choice='" + c.id + "' aria-pressed='" + (selected === c.id) + "'>" +
        esc(c.label) + "</button>"
      );
    }).join("");

    box.innerHTML =
      "<p class='small' style='margin-top:0'>Your decision stays in this browser only for now — nothing is sent anywhere.</p>" +
      "<div class='choices' role='group' aria-label='Review decision'>" + buttons + "</div>" +
      "<label><span class='small'>Note (optional)</span><br>" +
      "<textarea id='review-note'>" + esc(current && current.note ? current.note : "") + "</textarea></label> " +
      "<p><button type='button' class='primary' id='review-save'>Save decision</button> " +
      "<button type='button' id='review-clear'>Clear</button></p>" +
      "<p class='saved muted' id='review-saved' role='status' aria-live='polite'></p>";

    var choice = selected;
    box.querySelectorAll("[data-choice]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        choice = btn.getAttribute("data-choice");
        box.querySelectorAll("[data-choice]").forEach(function (b) {
          b.setAttribute("aria-pressed", String(b === btn));
        });
      });
    });

    var savedEl = box.querySelector("#review-saved");
    function showSaved(msg) {
      savedEl.textContent = msg;
    }

    box.querySelector("#review-save").addEventListener("click", function () {
      if (!choice) {
        showSaved("Pick a decision first: Approve, Request changes, or Note.");
        return;
      }
      var label = (CHOICES.filter(function (c) { return c.id === choice; })[0] || {}).label;
      var ok = writeReview(taskId, { decision: choice, note: box.querySelector("#review-note").value, at: new Date().toISOString() });
      showSaved(ok
        ? "Saved in this browser just now: " + label + "."
        : "Could not save — this browser blocks local storage.");
    });

    box.querySelector("#review-clear").addEventListener("click", function () {
      writeReview(taskId, null);
      choice = null;
      box.querySelectorAll("[data-choice]").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
      box.querySelector("#review-note").value = "";
      showSaved("Cleared.");
    });

    if (current && current.at) {
      var cl = (CHOICES.filter(function (c) { return c.id === current.decision; })[0] || {}).label;
      showSaved("Saved in this browser " + fmtWhen(current.at) + ": " + (cl || current.decision) + ".");
    }
  }

  /* ---------- boot ---------- */

  window.AgentBranchesUI = {
    FIXTURE: FIXTURE,
    bootIndex: function () {
      var errEl = document.getElementById("error");
      if (FIXTURE) document.getElementById("demo-banner").hidden = false;
      var loading = document.getElementById("loading");
      loadStatus()
        .then(function (status) { renderIndex(status); })
        .catch(function (e) { showError(errEl, e, FIXTURE); })
        .then(function () { loading.hidden = true; });
    },
    bootTask: function () {
      var errEl = document.getElementById("error");
      if (FIXTURE) document.getElementById("demo-banner").hidden = false;
      var loading = document.getElementById("loading");
      var id = params.get("id");
      if (!id) {
        loading.hidden = true;
        showError(errEl, new Error("No task id given. Open this page from the overview, or add ?id=task-0001."), FIXTURE);
        return;
      }
      Promise.all([loadTask(id), loadStatus().catch(function () { return null; })])
        .then(function (r) { renderTask(r[0], r[1]); })
        .catch(function (e) { showError(errEl, e, FIXTURE); })
        .then(function () { loading.hidden = true; });
    },
  };
})();
