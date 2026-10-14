/* Agent Branches — change story review UI (shared, vanilla JS, no frameworks).
   Two pages: index.html (overview from GET /status) and task.html?id= (change
   story from GET /tasks/:id). ?fixture=1 loads sample JSON from fixtures/.
   Live mode re-fetches GET /status every 3 s (paused while the tab is
   hidden); newly appeared warnings and pushes are highlighted for 5 s.
   Unknown safety is never rendered as safe. Requests are generation-guarded
   (C-1385): a slow older response never overwrites newer state, and a failed
   /status fetch shows a stale-error banner — never clean data. */

"use strict";

(function () {
  var params = new URLSearchParams(window.location.search);
  var FIXTURE_NAME = params.get("fixture") || "";
  var FIXTURE = !!FIXTURE_NAME;
  var API = (params.get("api") || "").replace(/\/+$/, "");
  /* Shared with node --test: pair safety (pair-status.js), view logic
     (view-logic.js — polling/highlights/acks/timeline/unprocessed pushes)
     and request bookkeeping (request-guard.js — single-flight generations
     and /status freshness, C-1385). */
  var PairLogic = window.AgentBranchesPairStatus;
  var View = window.AgentBranchesViewLogic;
  var Guard = window.AgentBranchesRequestGuard;
  var Auth = window.AgentBranchesAuth;

  /* ---------- live-update state (per page) ---------- */

  var pollTimer = null;
  var pollPausedByVisibility = false;
  var pollingStarted = false;
  var everRendered = false;
  var lastError = null;
  var lastLoadAt = null;
  var lastStatus = null;
  var lastTask = null;
  var currentTaskId = null;
  /* Single-flight bookkeeping (C-1385): every refresh() takes a generation;
     a response older than the latest settled one is dropped, so an
     out-of-order result can never overwrite newer state. statusFresh tracks
     whether the /status view currently holds fresh data or a stale error. */
  var genTracker = Guard.createGenTracker();
  var statusFresh = Guard.createStatusFreshness();
  /* Bearer auth (C1470; server gate C1462 Task 1): the in-memory session
     copy of the token is authoritative at runtime; localStorage only
     carries it across reloads — and may be blocked, so every access is
     wrapped and the page works from session state alone. */
  var authState = Auth.createAuthState(readStoredToken());

  function readStoredToken() {
    try {
      return Auth.getStoredToken(window.localStorage);
    } catch (e) {
      return null;
    }
  }

  function writeStoredToken(raw) {
    try {
      return Auth.setStoredToken(window.localStorage, raw);
    } catch (e) {
      return { ok: false, token: Auth.normalizeToken(raw) };
    }
  }

  function forgetStoredToken() {
    try {
      return Auth.clearStoredToken(window.localStorage);
    } catch (e) {
      return false;
    }
  }
  /* Highlight bookkeeping: which warnings/pushes appeared recently.
     key -> expiry ms. The first successful load only sets the baseline. */
  var prevWarningIds = null;
  var prevPushKeys = null;
  var freshWarnings = {};
  var freshPushes = {};
  var freshTimer = null;

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
    /* Fixture timestamps are fixed sample dates; "(10 d ago)" next to them
       is noise, so the relative suffix is live-mode only. */
    if (FIXTURE) return "<time datetime='" + esc(iso) + "'>" + esc(abs) + "</time>";
    var rel = relative(iso, d);
    return (
      "<time datetime='" + esc(iso) + "'>" + esc(abs) + "</time> <span class='muted small'>(" + esc(rel) + ")</span>"
    );
  }

  /* Plain-text time for titles/aria-labels (no markup). */
  function whenText(iso) {
    if (!iso) return "time not recorded";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "unknown time";
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function relative(iso, d) {
    var s = Math.max(0, (Date.now() - d.getTime()) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return Math.floor(s / 60) + " min ago";
    if (s < 86400) return Math.floor(s / 3600) + " h ago";
    return Math.floor(s / 86400) + " d ago";
  }

  /* Machine warning reasons such as "radar-conflict:test" read as words. */
  function warningReason(reason) {
    var m = /^radar-conflict:(\w+)$/.exec(String(reason || ""));
    if (!m) return String(reason || "");
    if (m[1] === "test") return "semantic conflict: the combined tests fail";
    if (m[1] === "textual") return "textual conflict: both changed the same lines";
    return "conflict (" + m[1] + ")";
  }

  /* One neutral line per agent card: did this agent's OWN tests pass at its
     latest change? Deliberately not a .badge.clean — an agent's own green
     run never makes any pair safe. */
  function ownTestHtml(ag, lost, stale) {
    var ev = ag.testEvidence;
    var label, icon;
    if (lost) {
      icon = "?";
      label = "Own tests: unknown — latest change never arrived";
    } else if (!ev) {
      icon = "?";
      label = "Own tests: no run recorded";
    } else if (ev.exitCode !== 0) {
      icon = "✕";
      label = "Own tests: " + (ev.command || "tests") + " failed (exit " + ev.exitCode + ")";
    } else if (!ev.head || !ag.head) {
      icon = "?";
      label = "Own tests: passed, but the tested change is unknown";
    } else if (ev.head !== ag.head) {
      icon = "?";
      label = "Own tests: passed on an older change (" + shortSha(ev.head) + ")";
    } else if (stale) {
      icon = "?";
      label = "Own tests: passed (unconfirmed — status out of date)";
    } else {
      icon = "✓";
      label = "Own tests: " + (ev.command || "tests") + " passed alone (exit 0)";
    }
    return (
      "<p class='own-test'><span class='own-test-icon' aria-hidden='true'>" + icon + "</span>" + esc(label) + "</p>"
    );
  }

  function plainRef(ref) {
    var m = /^refs\/heads\/(.+)$/.exec(String(ref || ""));
    return m ? m[1] : ref || "not recorded";
  }

  function taskHref(taskId) {
    var keep = FIXTURE ? "&fixture=" + encodeURIComponent(FIXTURE_NAME) : "";
    if (!FIXTURE && API) keep += "&api=" + encodeURIComponent(API);
    return "task.html?id=" + encodeURIComponent(taskId) + keep;
  }

  function isFreshWarning(id) {
    return View.isFresh(freshWarnings, id, Date.now());
  }

  function isFreshPush(agentId, sha) {
    return View.isFresh(freshPushes, View.pushKey(agentId, sha), Date.now());
  }

  function newBadge() {
    return " <span class='badge new'>New</span>";
  }

  /* Disclosures survive live re-renders: the page re-renders every 3 s, so
     a <details data-key> the viewer opened or closed keeps that state
     instead of snapping back to its default. */
  var disclosureState = {};

  document.addEventListener(
    "toggle",
    function (ev) {
      var el = ev.target;
      if (el && el.tagName === "DETAILS" && el.hasAttribute("data-key")) {
        disclosureState[el.getAttribute("data-key")] = el.open;
      }
    },
    true
  );

  function restoreDisclosures() {
    document.querySelectorAll("details[data-key]").forEach(function (el) {
      var key = el.getAttribute("data-key");
      if (Object.prototype.hasOwnProperty.call(disclosureState, key)) {
        el.open = disclosureState[key];
      }
    });
  }

  /* ---------- data loading ---------- */

  /* Authenticated reads (C1470): fixture/demo reads are static files and go
     out bare; live reads carry `Authorization: Bearer <token>` when a token
     is saved. Failures keep the historical message shape and additionally
     carry `status` + `authKind` ("unauthorized"/"forbidden"/null); a 403
     also carries the raw `bodyText` so the refusal diagnostic can name the
     token's owner (never the token itself). */
  function fetchJson(url) {
    var headers = FIXTURE ? {} : Auth.authHeaders(authState.snapshot().token);
    return fetch(url, { headers: headers }).then(function (r) {
      if (r.ok) return r.json();
      if (r.status === 403) {
        return r.text().then(
          function (text) {
            var err = Auth.httpError(r.status, url);
            err.bodyText = text;
            throw err;
          },
          function () {
            throw Auth.httpError(r.status, url);
          }
        );
      }
      throw Auth.httpError(r.status, url);
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

  function loadHint(isFixture) {
    return isFixture
      ? " Fixture files are loaded with fetch(), which browsers block when the page is opened directly from disk. Serve the folder over HTTP — see README-UI.md."
      : " Is the Worker running? Try: npx wrangler dev --local (from prototype/), then open this page with ?api=http://localhost:8787 if it is not served by the Worker yet.";
  }

  function showError(el, error, isFixture) {
    el.hidden = false;
    el.innerHTML =
      "<strong>Could not load the data.</strong> " +
      esc(error.message) +
      esc(authErrorHint(error)) +
      esc(loadHint(isFixture));
  }

  /* Extra guidance for auth failures: 401 points at the token form, 403
     carries the owner diagnostic (never the token). Plain text, escaped
     with the rest. */
  function authErrorHint(error) {
    if (!error || !error.authKind) return "";
    if (error.authKind === "forbidden") {
      return " " + Auth.describeForbidden(error.bodyText || "", currentTaskId);
    }
    return " " + Auth.describeUnauthorized(currentTaskId ? "task " + currentTaskId : "the status overview");
  }

  /* Explicit stale-error banner for the /status view (C-1385): while the
     latest status fetch has failed, this stays visible and the page is never
     presented as clean — safety badges and warnings may be out of date. */
  function setStatusErrorView() {
    var el = document.getElementById("status-error");
    if (!el) return;
    var stale = statusFresh.describe();
    if (!stale) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    el.hidden = false;
    el.innerHTML =
      "<strong>Live status is out of date.</strong> The latest update failed (" +
      esc(stale.error.message) + "). What you see may be missing newer changes, " +
      "warnings or pair results — treat safety badges as unknown, not clean, " +
      "until the next successful update." + esc(loadHint(FIXTURE));
  }

  /* ---------- bearer-token auth UI (C1470) ----------
     The static markup (#auth form, #auth-prompt, #auth-status,
     #auth-forbidden) ships in the HTML hidden and empty, so first paint is
     identical with or without JS (no hydration mismatch): JS only fills
     prompt text and flips `hidden`. Auth strings are set via textContent —
     tokens are never rendered. The input is prefilled once at wiring time,
     so live re-renders never wipe what is being typed. */

  function setAuthViews() {
    var snap = authState.snapshot();
    var section = document.getElementById("auth");
    var prompt = document.getElementById("auth-prompt");
    var forbidden = document.getElementById("auth-forbidden");
    if (!section || !prompt || !forbidden) return;
    if (FIXTURE) {
      section.hidden = true;
      forbidden.hidden = true;
      forbidden.textContent = "";
      return;
    }
    section.hidden = false;
    if (snap.forbidden) {
      forbidden.hidden = false;
      forbidden.textContent = snap.forbidden;
    } else {
      forbidden.hidden = true;
      forbidden.textContent = "";
    }
    if (snap.needsToken) {
      prompt.textContent = Auth.describeUnauthorized(
        currentTaskId ? "task " + currentTaskId : "the status overview"
      );
    } else if (snap.forbidden) {
      prompt.textContent =
        "The saved token cannot read this task — see the refusal detail above and replace it below.";
    } else if (!snap.token) {
      prompt.textContent =
        "No access token is saved in this browser yet. Paste a bearer token below to load live data.";
    } else {
      prompt.textContent =
        "A token is saved in this browser. It is sent only as an Authorization header to the configured API.";
    }
  }

  function noteAuthStatus(msg) {
    var status = document.getElementById("auth-status");
    if (status) status.textContent = msg;
  }

  function initAuthUI() {
    var section = document.getElementById("auth");
    if (!section || section.getAttribute("data-wired")) return;
    section.setAttribute("data-wired", "true");
    var form = document.getElementById("auth-form");
    var input = document.getElementById("auth-token");
    var clearBtn = document.getElementById("auth-clear");
    var snap = authState.snapshot();
    if (input && snap.token && !input.value) input.value = snap.token;
    if (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var saved = writeStoredToken(input ? input.value : "");
        authState.setToken(saved.token);
        noteAuthStatus(
          saved.token
            ? (saved.ok
              ? "Token saved in this browser. Retrying…"
              : "This browser blocks storage — the token is kept for this page view only. Retrying…")
            : "Token cleared."
        );
        setAuthViews();
        doRefresh(false);
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        forgetStoredToken();
        authState.clearToken();
        if (input) input.value = "";
        noteAuthStatus("Token cleared. Enter a token to load live data.");
        setAuthViews();
        doRefresh(false);
      });
    }
    setAuthViews();
  }

  /* ---------- live indicator ---------- */

  function setLiveState() {
    var el = document.getElementById("live");
    if (!el) return;
    if (pollPausedByVisibility) {
      el.textContent = "Updates paused while the tab is hidden — they resume when you come back.";
      return;
    }
    var mode = FIXTURE
      ? "Demo — re-reading the fixture files"
      : "Live — fetching GET /status";
    var every = " every " + Math.round(View.POLL_MS / 1000) + " s";
    /* Fixture data never changes, so no load timestamp there; and the
       polite live region is only rewritten when its text really changes,
       so screen readers are not re-told the same line every poll. */
    var loaded = lastLoadAt && !FIXTURE ? " · last loaded " + whenText(new Date(lastLoadAt).toISOString()) : "";
    var failed = lastError ? " · last update failed (" + lastError.message + "), retrying" : "";
    var text = mode + every + loaded + failed + ".";
    if (el.textContent !== text) el.textContent = text;
  }

  /* ---------- highlight bookkeeping ---------- */

  /* Diff the incoming status against the previous one; genuinely new
     warnings/pushes stay highlighted for FRESH_MS. The very first load only
     establishes the baseline, so opening the page highlights nothing. */
  function absorbFreshness(status) {
    var now = Date.now();
    var wIds = View.warningIdsOf(status);
    var pKeys = View.allPushKeys(status);
    if (prevWarningIds !== null) {
      freshWarnings = View.extendFresh(freshWarnings, View.addedKeys(prevWarningIds, wIds), now, View.FRESH_MS);
      freshPushes = View.extendFresh(freshPushes, View.addedKeys(prevPushKeys, pKeys), now, View.FRESH_MS);
    }
    prevWarningIds = wIds;
    prevPushKeys = pKeys;
  }

  /* Re-render when the next highlight expires, so the "New" mark really goes
     away after ~5 s instead of lingering until the next poll. */
  function scheduleFreshExpiry() {
    if (freshTimer) {
      clearTimeout(freshTimer);
      freshTimer = null;
    }
    var wWait = View.msUntilExpiry(freshWarnings, Date.now());
    var pWait = View.msUntilExpiry(freshPushes, Date.now());
    var wait = 0;
    if (wWait > 0 && (pWait === 0 || wWait < pWait)) wait = wWait;
    else wait = pWait;
    if (wait <= 0) return;
    freshTimer = setTimeout(function () {
      freshTimer = null;
      rerenderCurrent();
      scheduleFreshExpiry();
    }, wait + 50);
  }

  function rerenderCurrent() {
    if (!lastStatus && !lastTask) return;
    try {
      if (currentTaskId) {
        if (lastTask) renderTask(lastTask, lastStatus);
      } else if (lastStatus) {
        renderIndex(lastStatus);
      }
    } catch (e) {
      /* a re-render for highlight expiry must never break the page */
    }
  }

  /* ---------- pair safety (never guess "safe") ----------
     Pair status comes ONLY from that pair's own radar result in /status
     (status.pairs, L1 CONTRACT). A pair is "clean" only when its own
     result says clean at the CURRENT heads of both agents and the result
     records a combined test run with collected tests. A lost push for
     either agent forces not_checked (true heads unknown — never safe).
     The decision lives in pair-status.js so node --test exercises it. */

  function pairStatus(agentA, agentB, status) {
    return PairLogic.pairStatus(agentA, agentB, status);
  }

  /* Every badge carries an icon as well as words, so no state is signalled
     by color alone. */
  var BADGES = {
    conflict: { cls: "conflict", label: "Conflict", icon: "✕" },
    clean: { cls: "clean", label: "Clean — tests ran", icon: "✓" },
    unknown: { cls: "unknown", label: "Unknown — not safe", icon: "?" },
    not_checked: { cls: "not_checked", label: "Not checked", icon: "–" },
  };

  var PAIR_RANK = { conflict: 0, unknown: 1, not_checked: 2, clean: 3 };

  function badgeHtml(type) {
    var b = BADGES[type];
    return (
      "<span class='badge " + b.cls + "'><span class='badge-icon' aria-hidden='true'>" + b.icon + "</span>" +
      esc(b.label) + "</span>"
    );
  }

  /* Small inline badge with an icon, for states outside the pair BADGES. */
  function stateBadge(cls, icon, label) {
    return (
      "<span class='badge " + cls + "'><span class='badge-icon' aria-hidden='true'>" + icon + "</span>" +
      esc(label) + "</span>"
    );
  }

  function plural(n, one, many) {
    return n + " " + (n === 1 ? one : many);
  }

  /* The page's one key message: can these changes be combined? Built only
     from the (already stale-downgraded) pair badges, so it can never say
     "safe" when any pair is unknown, not checked or out of date. */
  function verdictHtml(counts, total, lostCount, stale) {
    var notProven = counts.unknown + counts.not_checked;
    var tone, icon, title, sub;
    if (!total) {
      tone = "caution";
      icon = "?";
      title = "Nothing to compare yet";
      sub = "Safety is checked per pair of agents; fewer than two agents are working right now.";
    } else if (counts.conflict) {
      tone = "danger";
      icon = "✕";
      title = "Not safe to combine: " + plural(counts.conflict, "conflict", "conflicts");
      sub =
        plural(counts.conflict, "pair clashes", "pairs clash") + " when tested together" +
        (notProven ? ", and " + plural(notProven, "more pair is", "more pairs are") + " not proven safe" : "") +
        ".";
    } else if (notProven) {
      tone = "caution";
      icon = "?";
      title = "Not proven safe";
      sub =
        plural(notProven, "pair has", "pairs have") +
        " not been proven safe together. Unknown is never treated as safe.";
    } else if (lostCount) {
      /* Every listed pair may be clean, but a push the server never saw
         means some agent's real latest change is unknown: never green. */
      tone = "caution";
      icon = "?";
      title = "Not proven safe — a push never arrived";
      sub = "The listed pairs passed, but an agent's latest change is unknown.";
    } else {
      tone = "ok";
      icon = "✓";
      title = "All " + plural(total, "pair", "pairs") + " tested clean together";
      sub = "Every pair was combined at its latest changes and the combined tests ran without a clash.";
    }
    if (lostCount && (counts.conflict || notProven)) {
      sub += " " + plural(lostCount, "push", "pushes") + " never arrived, so an agent's latest change is unknown.";
    }
    if (stale) {
      sub = "Live status is out of date (" + stale.error.message + "), so nothing below counts as clean. " + sub;
    }
    function tally(n, label) {
      return "<li" + (n ? "" : " class='zero'") + "><strong>" + n + "</strong> " + esc(label) + "</li>";
    }
    return (
      "<div class='verdict tone-" + tone + "'>" +
      "<p class='verdict-title'><span class='verdict-icon' aria-hidden='true'>" + icon + "</span>" + esc(title) + "</p>" +
      "<p class='verdict-sub'>" + esc(sub) + "</p>" +
      "<ul class='tally' role='list' aria-label='Pairs by result'>" +
      tally(counts.conflict, "conflict") +
      tally(counts.unknown, "unknown") +
      tally(counts.not_checked, "not checked") +
      tally(counts.clean, "clean") +
      "</ul></div>"
    );
  }

  /* ---------- warning acknowledgements (POST /warnings/:id/ack) ---------- */

  function ackCellHtml(warning, viewerAgentId) {
    var rows = View.ackRows(warning);
    if (!rows.length) {
      return "<span class='muted'>Not acknowledged yet — no agent has confirmed it saw this warning.</span>";
    }
    var mine = false;
    var parts = rows.map(function (a) {
      if (viewerAgentId && a.agent === viewerAgentId) mine = true;
      var who = viewerAgentId && a.agent === viewerAgentId
        ? "<strong>" + esc(a.agent) + "</strong>"
        : "<code>" + esc(a.agent) + "</code>";
      return (
        who + " " + fmtWhen(a.at) +
        (a.head ? " <span class='muted small'>at " + shaHtml(a.head) + "</span>" : "") +
        (a.note ? "<br><span class='small'>&ldquo;" + esc(a.note) + "&rdquo;</span>" : "")
      );
    });
    var missing = viewerAgentId && !mine
      ? "<br><span class='muted small'>Not yet acknowledged by this agent.</span>"
      : "";
    return parts.join("<br>") + missing;
  }

  /* ---------- compact per-agent timeline strip ---------- */

  var TL_META = {
    push: { icon: "+", word: "push", cls: "tl-push" },
    warning: { icon: "!", word: "warning", cls: "tl-warning" },
    ack: { icon: "\u2713", word: "acknowledged", cls: "tl-ack" },
  };

  function timelineHtml(agent, warnings) {
    var events = View.buildTimeline(agent, warnings);
    if (!events.length) {
      return "<p class='muted small' style='margin:0.3rem 0 0'>No pushes, warnings or acknowledgements recorded yet.</p>";
    }
    var cap = 12;
    var shown = events.slice(-cap);
    var dropped = events.length - shown.length;
    var chips = shown.map(function (e) {
      var m = TL_META[e.type];
      var fresh = "";
      var title;
      if (e.type === "push") {
        title = "Push " + shortSha(e.sha) + (e.message ? " — " + e.message : "") + " — " + whenText(e.at);
        if (isFreshPush(agent.agentId, e.sha)) fresh = " fresh";
      } else if (e.type === "warning") {
        title =
          "Warning " + e.warningId + (e.other ? " (with " + e.other + ")" : "") +
          (e.reason ? " — " + e.reason : "") +
          (e.status && e.status !== "active" ? " — since resolved" : "") +
          " — " + whenText(e.at);
        if (isFreshWarning(e.warningId)) fresh = " fresh";
      } else {
        title =
          "Acknowledged warning " + e.warningId +
          (e.note ? " — \u201C" + e.note + "\u201D" : "") +
          " — " + whenText(e.at);
      }
      return (
        "<li class='tl " + m.cls + fresh + "' tabindex='0' title='" + esc(title) + "'" +
        " aria-label='" + esc(m.word + ": " + title) + "'>" +
        "<span class='tl-icon' aria-hidden='true'>" + m.icon + "</span>" +
        "<span class='tl-word'>" + esc(m.word) + "</span>" +
        (fresh ? newBadge() : "") +
        "</li>"
      );
    });
    return (
      (dropped > 0 ? "<span class='muted small'>+" + dropped + " earlier</span>" : "") +
      "<ol class='timeline' role='list' aria-label='Timeline for " + esc(agent.agentId) + "'>" + chips.join("") + "</ol>"
    );
  }

  /* ---------- unprocessed (lost) pushes — the head is UNKNOWN ---------- */

  function unknownHeadHtml(reason) {
    return (
      stateBadge("unknown", "?", "Unknown") + " <span class='small'>true latest change UNKNOWN — " +
      esc(reason) +
      ". Nothing is clean for this agent until the push is delivered.</span>"
    );
  }

  function renderLost(status) {
    var section = document.getElementById("lost-section");
    if (!section) return;
    var recs = Array.isArray(status.unprocessedPushes) ? status.unprocessedPushes : [];
    section.hidden = recs.length === 0;
    if (!recs.length) return;
    var items = recs.map(function (r) {
      var who = r.agentId
        ? "<code>" + esc(r.agentId) + "</code>"
        : "<span class='muted'>an unknown agent</span>";
      return (
        "<li class='lost-item'>" +
        "<p class='lead'>" + stateBadge("unknown", "?", "Not processed") + " A push by " + who +
        " could not be recorded" +
        (typeof r.attempts === "number" ? " after " + esc(r.attempts) + " attempt" + (r.attempts === 1 ? "" : "s") : "") +
        ".</p>" +
        "<p class='why small'>Until it is delivered, " +
        (r.agentId ? "<code>" + esc(r.agentId) + "</code>'s" : "the agent's") +
        " true latest change is UNKNOWN, and every pair involving the agent stays not checked — never clean.</p>" +
        "<details class='inline' data-key='lost-" + esc(r.agentId || "") + "-" + esc(r.sha || "") + "'><summary>Delivery details</summary>" +
        "<p class='small muted' style='margin:0'>Repo <code>" + esc(r.repo || "unknown repo") + "</code>, branch <code>" +
        esc(plainRef(r.ref)) + "</code>, change " + shaHtml(r.sha) +
        (r.lastError ? " · last error: <code>" + esc(r.lastError) + "</code>" : "") +
        " · first seen " + whenText(r.firstAt) + ", last try " + whenText(r.lastAt) + ".</p>" +
        "</details>" +
        "</li>"
      );
    });
    document.getElementById("lost-list").innerHTML = "<ul class='lost-list' role='list'>" + items.join("") + "</ul>";
  }

  /* ---------- stale status view (C-1385) ----------
     While the /status fetch is failing, the page keeps the last good data
     only as explicitly STALE: the banner stays up and every section that
     could otherwise look clean carries this notice. */

  function staleNoteHtml(stale) {
    return (
      "<div class='notice-unknown'>" +
      stateBadge("unknown", "?", "Status out of date") + " " +
      "<p style='margin:0.4rem 0 0'>The live status could not be refreshed (" +
      esc(stale.error.message) +
      "), so this section comes from the last successful load and may be missing " +
      "newer events — treat it as unknown, not clean.</p></div>"
    );
  }

  /* ---------- index page ---------- */

  function renderIndex(status) {
    var stale = statusFresh.describe();
    var agents = (status.agents || []).slice().sort(function (x, y) {
      return String(x.agentId).localeCompare(String(y.agentId));
    });
    var allWarnings = status.warnings || [];

    renderLost(status);

    var canon = document.getElementById("canonical");
    canon.innerHTML =
      status.canonical && status.canonical.name
        ? "Shared starting repo: <code>" + esc(status.canonical.name) + "</code>"
        : "Shared starting repo not created yet.";

    var cards = agents.map(function (ag) {
      var intent = ag.intent ? esc(ag.intent) : "<span class='muted'>Intent not stated yet</span>";
      var lost = View.unknownHeadReason(ag.agentId, status);
      var latest = lost
        ? stateBadge("unknown", "?", "Unknown — push never arrived")
        : shaHtml(ag.head) +
          (isFreshPush(ag.agentId, ag.head) ? newBadge() : "");
      var cardOpen = isFreshPush(ag.agentId, ag.head);
      return (
        "<article class='card" + (isFreshPush(ag.agentId, ag.head) ? " fresh" : "") + "' aria-label='Agent " + esc(ag.agentId) + "'>" +
        "<h3><code>" + esc(ag.agentId) + "</code></h3>" +
        "<p class='intent'>" + intent + "</p>" +
        "<p class='kv'>Latest change: " + latest + "</p>" +
        ownTestHtml(ag, lost, stale) +
        "<details class='inline' data-key='card-" + esc(ag.agentId) + "'" + (cardOpen ? " open" : "") + "><summary>" +
        esc(plural(Number(ag.pushes) || 0, "push", "pushes")) + " · timeline</summary>" +
        "<p class='kv'>Started from " +
        (ag.baseSha ? shaHtml(ag.baseSha) : "<span class='muted'>not recorded</span>") +
        (ag.lastPushAt ? " · last push " + fmtWhen(ag.lastPushAt) : "") + "</p>" +
        "<div class='timeline-wrap'>" + timelineHtml(ag, allWarnings) + "</div>" +
        "</details>" +
        "<p class='actions'><a href='" + taskHref(ag.taskId) + "'>Open change story <span aria-hidden='true'>→</span></a></p>" +
        "</article>"
      );
    });
    document.getElementById("agents").innerHTML =
      cards.length ? "<div class='cards'>" + cards.join("") + "</div>" : "<p class='muted'>No agent tasks yet.</p>";

    var pairs = [];
    var counts = { conflict: 0, clean: 0, unknown: 0, not_checked: 0 };
    for (var i = 0; i < agents.length; i++) {
      for (var j = i + 1; j < agents.length; j++) {
        var st = pairStatus(agents[i], agents[j], status);
        var badgeType = st.type;
        var why = st.why;
        if (stale && badgeType === "clean") {
          badgeType = "unknown";
          why =
            why +
            " · live status could not be refreshed (" +
            stale.error.message +
            "); treated as unknown, not clean";
        }
        counts[badgeType] += 1;
        pairs.push({
          rank: PAIR_RANK[badgeType],
          html:
            "<li class='pair is-" + badgeType + "'>" +
            "<div class='pair-head'>" +
            "<span class='who'><code>" + esc(agents[i].agentId) + "</code><span class='vs' aria-label='and'>↔</span><code>" +
            esc(agents[j].agentId) + "</code></span> " +
            badgeHtml(badgeType) +
            "</div>" +
            "<p class='why'>" + esc(why) + "</p>" +
            "</li>",
        });
      }
    }
    /* Most urgent first: conflicts, then unknown, then not checked, then clean. */
    pairs.sort(function (x, y) { return x.rank - y.rank; });
    document.getElementById("pairs").innerHTML = pairs.length
      ? "<ul class='pair-list' role='list'>" + pairs.map(function (p) { return p.html; }).join("") + "</ul>"
      : "<p class='muted'>With fewer than two agents there is nothing to compare yet.</p>";

    var lostCount = Array.isArray(status.unprocessedPushes) ? status.unprocessedPushes.length : 0;
    var verdict = document.getElementById("verdict");
    if (verdict) {
      verdict.innerHTML = verdictHtml(counts, pairs.length, lostCount, stale);
      verdict.hidden = false;
    }

    var warnings = allWarnings;
    var activeCount = 0;
    var rows = warnings.map(function (w) {
      if (w.status === "active") activeCount += 1;
      var state = w.status === "active"
        ? stateBadge("conflict", "!", "Active")
        : stateBadge("not_checked", "✓", "Resolved");
      var fresh = isFreshWarning(w.id);
      return (
        "<tr class='" + (fresh ? "fresh" : "") + "'>" +
        "<td><code>" + esc(w.id) + "</code>" + (fresh ? newBadge() : "") + "</td>" +
        "<td><code>" + esc(w.pair.join(" ↔ ")) + "</code></td>" +
        "<td>" + esc(warningReason(w.reason)) + "</td>" +
        "<td>" + fmtWhen(w.createdAt) + "</td>" +
        "<td>" + state + (w.invalidatedAt ? " <span class='muted small'>" + fmtWhen(w.invalidatedAt) + "</span>" : "") + "</td>" +
        "<td>" + ackCellHtml(w) + "</td>" +
        "</tr>"
      );
    });
    document.getElementById("warnings-body").innerHTML = rows.join("");
    document.getElementById("warnings-section").hidden = rows.length === 0;
    var wCount = document.getElementById("warnings-count");
    if (wCount) {
      wCount.textContent = "(" + rows.length + " · " + activeCount + " active)";
    }
    restoreDisclosures();
  }

  /* ---------- task page ---------- */

  function renderTask(task, status) {
    var agent = task.agent || {};
    var heads = (status && status.heads) || {};
    var allWarnings = (status && status.warnings) || [];
    var stale = statusFresh.describe();
    var lost = agent.agentId ? View.unknownHeadReason(agent.agentId, status) : null;
    var currentHead = lost ? null : heads[agent.agentId] || agent.head || null;

    document.title = "Change story — " + (agent.agentId || task.taskId);

    var intentText = task.intent || agent.intent;
    var titleEl = document.getElementById("task-title");
    if (titleEl) {
      titleEl.innerHTML = "<code>" + esc(agent.agentId || task.agentId || task.taskId) + "</code>";
    }
    var ledeEl = document.getElementById("task-lede");
    if (ledeEl) {
      ledeEl.textContent = intentText ? intentText : "This agent has not stated what it is doing yet.";
    }

    var dl =
      "<dt>Agent</dt><dd><code>" + esc(agent.agentId || task.agentId) + "</code></dd>" +
      "<dt>Task</dt><dd><code>" + esc(task.taskId) + "</code></dd>" +
      /* intent + base live on the task record itself (GET /tasks/:id returns
         base_sha/intent at the top level; /status agents carry intent/baseSha
         for the index cards). Prefer the task-level fields, fall back to the
         agent object for older fixtures. */
      "<dt>Doing</dt><dd>" +
      ((task.intent || agent.intent) ? esc(task.intent || agent.intent) : "<span class='muted'>Not stated yet</span>") + "</dd>" +
      "<dt>Started from</dt><dd>" +
      ((task.base_sha || agent.baseSha) ? shaHtml(task.base_sha || agent.baseSha) : "<span class='muted'>Not recorded yet</span>") + "</dd>" +
      "<dt>Latest change</dt><dd>" +
      (lost ? unknownHeadHtml(lost) : shaHtml(currentHead)) + "</dd>" +
      "<dt>Working copy</dt><dd><span class='small'>own fork <code>" + esc(task.forkName || agent.forkName) +
      "</code>, branch <code>" + esc(plainRef(task.ref || agent.ref)) + "</code></span></dd>" +
      "<dt>Task created</dt><dd>" + fmtWhen(task.createdAt) + "</dd>";
    document.getElementById("task-head").innerHTML =
      (stale ? staleNoteHtml(stale) : "") +
      "<ul class='facts'>" +
      "<li>Latest change: " + (lost ? stateBadge("unknown", "?", "Unknown") : shaHtml(currentHead)) + "</li>" +
      "<li>Started from: " +
      ((task.base_sha || agent.baseSha) ? shaHtml(task.base_sha || agent.baseSha) : "not recorded") + "</li>" +
      "<li>Task: <code>" + esc(task.taskId) + "</code></li>" +
      "</ul>" +
      "<details class='inline' data-key='task-details'><summary>All task details</summary><dl>" + dl + "</dl></details>";

    document.getElementById("timeline").innerHTML =
      "<details class='inline' data-key='task-timeline'><summary>Timeline strip: pushes, warnings, acknowledgements</summary>" +
      timelineHtml(agent, allWarnings) + "</details>";

    /* Story of changes */
    var log = Array.isArray(agent.pushLog) ? agent.pushLog : [];
    var changes;
    if (lost) {
      changes =
        "<div class='notice-unknown' style='margin-bottom:0.6rem'>" +
        badgeHtml("unknown") + " " +
        "<p>This list may be missing the agent's true latest change: its newest push never reached the server.</p></div>" +
        changesListHtml(agent, log, currentHead);
    } else {
      changes = changesListHtml(agent, log, currentHead);
    }
    document.getElementById("changes").innerHTML = changes;

    /* Warnings received by this agent */
    var mine = allWarnings.filter(function (w) {
      return Array.isArray(w.pair) && w.pair.indexOf(agent.agentId) !== -1;
    });
    var warnHtml;
    if (!mine.length) {
      /* A stale status must never read as "no warnings" (C-1385): without a
         fresh fetch, an empty list is unknown, not clean. */
      warnHtml = stale
        ? "<div class='notice-unknown'>" + stateBadge("unknown", "?", "Unknown") +
          "<p>No warnings are recorded as of the last successful load, " +
          "but the live status could not be refreshed (" + esc(stale.error.message) +
          ") — a newer warning may be missing.</p></div>"
        : "<p class='muted'>No warnings received.</p>";
    } else {
      var cardsOf = function (list) {
        return list.map(function (w) {
          var other = w.pair[0] === agent.agentId ? w.pair[1] : w.pair[0];
          var resolved = w.status !== "active";
          var fresh = isFreshWarning(w.id);
          var acks = View.ackRows(w);
          var ackHtml = acks.length
            ? "<details class='inline' data-key='ack-" + esc(w.id) + "'><summary>" +
              esc(plural(acks.length, "acknowledgement", "acknowledgements")) + "</summary>" +
              "<p class='meta'>" + ackCellHtml(w, agent.agentId) + "</p></details>"
            : "<p class='meta'>" + ackCellHtml(w, agent.agentId) + "</p>";
          return (
            "<div class='warning" + (resolved ? " resolved" : "") + (fresh ? " fresh" : "") + "'>" +
            (resolved
              ? stateBadge("not_checked", "✓", "Resolved")
              : stateBadge("conflict", "!", "Conflict — needs attention")) +
            (fresh ? newBadge() : "") +
            "<p class='reason'>" + esc(warningReason(w.reason)) + "</p>" +
            "<p class='meta'>With <code>" + esc(other) + "</code> · sent " + fmtWhen(w.createdAt) +
            (resolved ? " · went away " + fmtWhen(w.invalidatedAt) : "") + "</p>" +
            ackHtml +
            "</div>"
          );
        }).join("");
      };
      var activeList = mine.filter(function (w) { return w.status === "active"; });
      var resolvedList = mine.filter(function (w) { return w.status !== "active"; });
      /* Active warnings lead; resolved history folds away once something
         active needs attention. */
      warnHtml = activeList.length && resolvedList.length
        ? cardsOf(activeList) +
          "<details class='inline' data-key='resolved-warnings'><summary>" +
          esc(plural(resolvedList.length, "resolved earlier warning", "resolved earlier warnings")) +
          "</summary>" + cardsOf(resolvedList) + "</details>"
        : cardsOf(mine);
    }
    document.getElementById("warnings").innerHTML = warnHtml;

    /* Test provenance */
    document.getElementById("evidence").innerHTML = evidenceHtml(agent, currentHead, lost);

    var activeMine = mine.filter(function (w) { return w.status === "active"; }).length;
    var verdictEl = document.getElementById("task-verdict");
    if (verdictEl) {
      verdictEl.innerHTML = taskVerdictHtml(agent, currentHead, lost, stale, activeMine);
      verdictEl.hidden = false;
    }

    restoreDisclosures();
    initReviewOnce(task.taskId);
  }

  /* The task page's one key message. Mirrors evidenceHtml: only a passing
     run recorded at the current head, with fresh status, reads as tested —
     and even then it never claims the agent is safe to combine with others. */
  function taskVerdictHtml(agent, currentHead, lost, stale, activeWarnings) {
    var ev = agent.testEvidence;
    var tone, icon, title, sub;
    if (lost) {
      tone = "caution";
      icon = "?";
      title = "Unknown — a push never arrived";
      sub = "The server never recorded this agent's newest push, so its latest change is unknown and not proven safe.";
    } else if (stale) {
      tone = "caution";
      icon = "?";
      title = "Unknown — live status is out of date";
      sub = "Whether tests ran at the true latest change is unknown, not safe.";
    } else if (!ev) {
      tone = "caution";
      icon = "?";
      title = "Not proven safe — no test run recorded";
      sub = "There is no test run for the latest change.";
    } else if (ev.exitCode !== 0) {
      tone = "danger";
      icon = "✕";
      title = "Tests failed (exit " + ev.exitCode + ")";
      sub = "The latest recorded test run did not pass.";
    } else if (!currentHead || !ev.head) {
      tone = "caution";
      icon = "?";
      title = "Not proven safe — tested change unknown";
      sub = "The passing run cannot be matched to the latest change, so it does not count.";
    } else if (ev.head !== currentHead) {
      tone = "caution";
      icon = "?";
      title = "Not proven safe — tests ran on an older change";
      sub = "The last passing run was for " + shortSha(ev.head) + ", not the latest change " + shortSha(currentHead) + ".";
    } else {
      tone = "ok";
      icon = "✓";
      title = "Its own tests passed at the latest change";
      sub = "Own tests alone never make a pair safe — see the Pair Safety Radar for combined results.";
    }
    if (activeWarnings) {
      tone = "danger";
      icon = "!";
      sub = plural(activeWarnings, "active conflict warning needs", "active conflict warnings need") + " attention. " + sub;
    }
    return (
      "<div class='verdict tone-" + tone + "'>" +
      "<p class='verdict-title'><span class='verdict-icon' aria-hidden='true'>" + icon + "</span>" + esc(title) + "</p>" +
      "<p class='verdict-sub'>" + esc(sub) + "</p></div>"
    );
  }

  function changesListHtml(agent, log, currentHead) {
    if (log.length) {
      return (
        "<ol class='changes' role='list' reversed>" +
        log
          .slice()
          .reverse()
          .map(function (p) {
            var fresh = isFreshPush(agent.agentId, p.sha);
            var tested = agent.testEvidence && agent.testEvidence.head === p.sha;
            return (
              "<li class='" + (fresh ? "fresh" : "") + "'><span class='when'>" + fmtWhen(p.at) + "</span> — " + shaHtml(p.sha) +
              (currentHead && p.sha === currentHead ? " <span class='tag'>Latest</span>" : "") +
              (tested ? " <span class='tag'>Last tested</span>" : "") +
              (fresh ? newBadge() : "") +
              (p.message ? "<br><span class='muted'>" + esc(p.message) + "</span>" : "") +
              "</li>"
            );
          })
          .join("") +
        "</ol>"
      );
    }
    if (agent.pushes > 0 && agent.lastPushAt) {
      var freshHead = isFreshPush(agent.agentId, agent.head);
      return (
        "<p class='" + (freshHead ? "fresh" : "") + "'>" + fmtWhen(agent.lastPushAt) + " — " + shaHtml(currentHead) +
        (freshHead ? newBadge() : "") + "</p>" +
        "<p class='muted small'>" + esc(agent.pushes) + " change" + (agent.pushes === 1 ? "" : "s") +
        " pushed in total. The full list of each change is not recorded yet.</p>"
      );
    }
    return "<p class='muted'>No changes pushed yet.</p>";
  }

  function evidenceHtml(agent, currentHead, lost) {
    var ev = agent.testEvidence;
    var stale = statusFresh.describe();
    if (lost) {
      return (
        "<div class='notice-unknown'>" +
        badgeHtml("unknown") + " " +
        "<p>The agent's true latest change is UNKNOWN, and no test run can exist for a change the server never saw — " +
        "this change is not proven safe.</p>" +
        "<p class='small muted'>Why: " + esc(lost) + ".</p></div>"
      );
    }
    if (ev) {
      /* Strict: a run only covers the latest change when both heads are
         known and equal; a missing head is never treated as a match. */
      var matchesHead = !!(currentHead && ev.head && ev.head === currentHead);
      var passed = ev.exitCode === 0;
      var resultBadge = stale
        ? (passed
          ? stateBadge("not_checked", "?", "Passed (unconfirmed)")
          : stateBadge("conflict", "✕", "Failed — exit " + ev.exitCode))
        : (passed
          ? (matchesHead
            ? stateBadge("clean", "✓", "Passed")
            /* A pass on an older change is not green: it proves nothing
               about the latest change. */
            : stateBadge("not_checked", "?", "Passed — on an older change"))
          : stateBadge("conflict", "✕", "Failed — exit " + ev.exitCode));
      /* Conclusion first, nuance after: a reader never sees a pass before
         learning that it does not cover the latest change. */
      var conclusion = stale
        ? "<p class='bottom-line'>" + badgeHtml("unknown") + " " +
          "Live status could not be refreshed (" + esc(stale.error.message) + "); whether tests ran at the true current head is unknown, not safe.</p>"
        : (!matchesHead || !passed
          ? "<p class='bottom-line'>" + badgeHtml("unknown") + " " +
            "There is no passing test run for the latest change, so this change is not proven safe.</p>"
          : "");
      return (
        "<div class='evidence'>" + conclusion + "<dl>" +
        "<dt>Command</dt><dd><code>" + esc(ev.command) + "</code></dd>" +
        "<dt>Result</dt><dd>" + resultBadge + "</dd>" +
        "<dt>Tested change</dt><dd>" + shaHtml(ev.head) +
        (stale
          ? " <span class='muted small'>(live status unconfirmed · " + esc(stale.error.message) + ")</span>"
          : (matchesHead
            ? " <span class='muted small'>(the latest change)</span>"
            : " <span class='muted small'>(an older change, not the latest)</span>")) +
        "</dd>" +
        "<dt>When</dt><dd>" + fmtWhen(ev.at) + "</dd>" +
        "</dl>" +
        "</div>"
      );
    }
    return (
      "<div class='notice-unknown'>" +
      badgeHtml("unknown") + " " +
      "<p style='margin:0.4rem 0 0'>No test run is recorded for this change. Without a test run at the " +
      "latest change, safety is unknown — this is never shown as safe.</p></div>"
    );
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

  /* The review box is interactive (buttons, note textarea): it is initialized
     exactly once per task so live re-renders never wipe what is being typed. */
  function initReviewOnce(taskId) {
    var box = document.getElementById("review");
    if (box.getAttribute("data-for") === taskId) return;
    initReview(taskId);
    box.setAttribute("data-for", taskId);
  }

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

  /* ---------- polling (GET /status every 3 s, paused when hidden) ---------- */

  /* A status result is never swallowed into null (C-1385): failures arrive
     as {ok:false, error} and are surfaced, not hidden. */
  function statusOk(status) {
    if (!status) return { ok: false, error: new Error("server returned an empty status document") };
    return { ok: true, status: status };
  }

  function statusFailed(error) {
    return { ok: false, error: error };
  }

  function refresh() {
    var gen = genTracker.begin();
    var p = currentTaskId
      ? Promise.all([loadTask(currentTaskId), loadStatus().then(statusOk, statusFailed)]).then(function (r) {
          return { task: r[0], statusResult: r[1] };
        })
      : loadStatus().then(statusOk, statusFailed).then(function (statusResult) {
          return { task: null, statusResult: statusResult };
        });
    return p.then(
      function (r) {
        /* Single-flight guard (C-1385): when this response settles after a
           newer request already has, it is out of order — drop it instead of
           overwriting newer state. */
        if (!genTracker.settle(gen)) return;

        if (!r.statusResult.ok) {
          /* /status failed: record the error, mark the status view stale with
             the explicit banner, and never render the page as clean. A 401
             additionally raises the token prompt; a 403 raises the refusal
             diagnostic — both keep the stale downgrade, so nothing reads as
             clean while unauthenticated. */
          statusFresh.markStale(r.statusResult.error);
          lastError = r.statusResult.error;
          if (lastError && lastError.authKind === "unauthorized") {
            authState.markUnauthorized();
          } else if (lastError && lastError.authKind === "forbidden") {
            authState.markForbidden(Auth.describeForbidden(lastError.bodyText || "", currentTaskId));
          }
          setAuthViews();
          setStatusErrorView();
          if (currentTaskId && r.task) {
            lastTask = r.task; /* the task story loaded; render it marked stale */
            renderTask(lastTask, lastStatus);
            everRendered = true;
          } else if (!currentTaskId && lastStatus) {
            /* Index view re-render marked stale (C-1399): downgrades clean badges to unknown */
            renderIndex(lastStatus);
            everRendered = true;
          }
          return;
        }

        statusFresh.markFresh();
        lastError = null;
        authState.markOk();
        setAuthViews();
        lastStatus = r.statusResult.status;
        if (currentTaskId) lastTask = r.task;
        lastLoadAt = Date.now();
        absorbFreshness(lastStatus);
        setStatusErrorView();
        if (currentTaskId) renderTask(lastTask, lastStatus);
        else renderIndex(lastStatus);
        everRendered = true;
        scheduleFreshExpiry();
      },
      function (e) {
        /* A late failure from an already-outdated request is dropped too. */
        if (!genTracker.settle(gen)) return;
        /* A 401/403 from GET /tasks/:id (task page) updates the auth state
           before the error propagates to doRefresh for rendering. */
        if (e && e.authKind === "unauthorized") authState.markUnauthorized();
        else if (e && e.authKind === "forbidden") {
          authState.markForbidden(Auth.describeForbidden(e.bodyText || "", currentTaskId));
        }
        setAuthViews();
        throw e; /* doRefresh records lastError and shows the load banner */
      }
    );
  }

  function doRefresh(first) {
    return refresh().then(
      function () {
        setLiveState();
      },
      function (e) {
        lastError = e;
        setAuthViews();
        if (first && !everRendered) {
          showError(document.getElementById("error"), e, FIXTURE);
        }
        setLiveState();
      }
    );
  }

  function handleVisibility() {
    if (document.hidden) {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
      pollPausedByVisibility = true;
    } else {
      pollPausedByVisibility = false;
      if (!pollTimer) {
        pollTimer = setInterval(function () { doRefresh(false); }, View.POLL_MS);
      }
      doRefresh(false); /* catch up immediately when coming back */
    }
    setLiveState();
  }

  function startPolling() {
    if (pollingStarted) return;
    pollingStarted = true;
    document.addEventListener("visibilitychange", handleVisibility);
    if (document.hidden) {
      pollPausedByVisibility = true;
      return;
    }
    pollTimer = setInterval(function () { doRefresh(false); }, View.POLL_MS);
  }

  /* ---------- boot ---------- */

  window.AgentBranchesUI = {
    FIXTURE: FIXTURE,
    /* Headless-verifiable auth snapshot for tests and operators. */
    auth: function () {
      return authState.snapshot();
    },
    bootIndex: function () {
      initAuthUI();
      var loading = document.getElementById("loading");
      currentTaskId = null;
      doRefresh(true).then(function () { loading.hidden = true; });
      startPolling();
      setLiveState();
    },
    bootTask: function () {
      initAuthUI();
      var loading = document.getElementById("loading");
      var id = params.get("id");
      if (!id) {
        loading.hidden = true;
        showError(
          document.getElementById("error"),
          new Error("No task id given. Open this page from the overview, or add ?id=task-0001."),
          FIXTURE
        );
        return;
      }
      currentTaskId = id;
      doRefresh(true).then(function () { loading.hidden = true; });
      startPolling();
      setLiveState();
    },
  };
})();
