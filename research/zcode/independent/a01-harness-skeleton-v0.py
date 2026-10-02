#!/usr/bin/env python3
"""A01 uptake protocol rev 2: harness skeleton v0. ZCode independent, 2026-10-02.

Iterates a01-wip-feasibility-fixture.py from a linear feasibility spike toward
the live-gate harness: a poll-based watcher over REAL git worktrees driving the
a01-uptake-protocol.md rev 2 machinery end to end —

  * push_observed detection from real ref updates (measured watcher lag),
  * WIP evidence from real uncommitted diffs (wip_basis=uncommitted_diff),
  * base_sha + ordered head_vector [{agent_id, fork, sha}] scoping,
  * dedup key (base_sha, canonical_json(head_vector), oracle_id) with
    duplicate journaling and single delivery,
  * vector_current re-check at consume/action with stale classification,
  * monotonic generation fence with fence_event on simulated crash,
  * uptake classification per protocol section 4 (uptake / stale / fenced),
  * latency segments (observe->emit->deliver) with per-segment N,
  * JSONL journal validated against the section 1 schema per line,
  * one scan against a real clone of THIS workspace repository.

Self-contained, stdlib only, self-cleaning /tmp scratch (well under 512 MB).
Agents are DETERMINISTIC SCRIPTED STAND-INS in fixed interleaving: the watcher
loop is real and concurrent, but no live model agents run, so deliver->consume
and consume->first-action latencies are NOT measured here. This skeleton is
NOT the R2-1/Y1 kill test; it is the harness-side half a live run would drive.
"""

import hashlib
import json
import re
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "a01-harness-skeleton-v0-results.json"
POLL_INTERVAL_S = 0.4
WATCHER_LAG_BUDGET_MS = 2 * POLL_INTERVAL_S * 1000  # one tick + scan margin

# --- section 1 schema: required field sets per event type (skeleton-side
# extensions are declared separately and reported as protocol deviations). ---
SCHEMA = {
    "run_start": {"run_id", "protocol_version", "fixture_id", "harness_rev",
                  "agents", "seed_pairs"},
    "push_observed": {"run_id", "agent_id", "sha", "parent_sha", "ts_push_observed",
                      "branch"},
    "emit": {"warning_id", "run_id", "base_sha", "head_vector", "pair", "failing",
             "oracle_id", "test_digest", "ts_emitted", "generation", "wip_basis"},
    "deliver": {"warning_id", "ts_delivered", "channel"},
    "consume": {"warning_id", "ts_consumed", "agent_id", "vector_current"},
    "agent_action": {"warning_id", "run_id", "agent_id", "action",
                     "ts_action_started", "ts_action_ended", "new_head_sha",
                     "generation"},
    "run_outcome": {"run_id", "merged_clean", "combined_pass", "landed_sha",
                    "ts_integration_tested", "repair_seconds",
                    "wasted_work_seconds"},
    "fence_event": {"run_id", "kind", "old_generation", "new_generation", "ts"},
    "run_end": {"run_id", "ts"},
}
SCHEMA_EXTENSIONS = {
    "emit": {"duplicate"},                  # journaled re-emission flag (sec 3)
    "agent_action": {"classification"},     # uptake|stale|fenced|too_late (sec 4)
    "push_observed": {"watcher_lag_ms"},    # ref-update -> observed lag where known
}


def monotonic_ms():
    return time.monotonic_ns() // 1_000_000


def wall_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def git(cwd, *args, timeout=60):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=timeout)


def must(cwd, *args):
    r = git(cwd, *args)
    if r.returncode != 0:
        raise SystemExit(f"git {args} failed in {cwd}:\n{r.stderr}")
    return r.stdout.strip()


def init_repo(path, branch="main"):
    path.mkdir(parents=True)
    must(path, "init", "-q", "-b", branch)
    must(path, "config", "user.name", "Skeleton")
    must(path, "config", "user.email", "skeleton@test")
    must(path, "config", "commit.gpgsign", "false")


def commit_all(path, msg):
    must(path, "add", "-A")
    must(path, "commit", "-q", "-m", msg)
    return must(path, "rev-parse", "HEAD")


# --- symbol-overlap oracle core (fixture-grade, reused from the feasibility
# fixture; same known limitation: top-level Python functions only). ---

DEF_LINE_RE = re.compile(r"def\s+([A-Za-z_]\w*)")
HUNK_HEAD_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _def_spans(text):
    return [(i, m.group(1)) for i, line in enumerate(text.splitlines())
            if (m := DEF_LINE_RE.match(line))]


def _enclosing(spans, idx):
    name = None
    for start, sym in spans:
        if start <= idx:
            name = sym
        else:
            break
    return name


def changed_symbols(diff_text, old_text, new_text):
    old_spans, new_spans = _def_spans(old_text), _def_spans(new_text)
    syms = set()
    old_ln = new_ln = 0
    for line in diff_text.splitlines():
        hm = HUNK_HEAD_RE.match(line)
        if hm:
            old_ln = int(hm.group(1)) - 1
            new_ln = int(hm.group(3)) - 1
            continue
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            sym = _enclosing(new_spans, new_ln)
            if sym:
                syms.add(sym)
            new_ln += 1
        elif line.startswith("-"):
            sym = _enclosing(old_spans, old_ln)
            if sym:
                syms.add(sym)
            old_ln += 1
        else:
            new_ln += 1
            old_ln += 1
    return syms


def wip_evidence(wt):
    """Real uncommitted-diff evidence: {relpath: (symbols, diff_text)}."""
    evidence = {}
    rels = [l for l in must(wt, "diff", "--name-only", "HEAD").splitlines() if l]
    for rel in rels:
        if not rel.endswith(".py"):
            continue
        diff = must(wt, "diff", "HEAD", "--", rel)
        old = must(wt, "show", f"HEAD:{rel}") if diff else ""
        new = (wt / rel).read_text()
        evidence[rel] = (changed_symbols(diff, old, new), diff)
    return evidence


def committed_symbols(wt, base_sha):
    """Symbols one agent's committed head touches vs base: {relpath: syms}."""
    out = {}
    rels = [l for l in must(wt, "diff", "--name-only", base_sha, "HEAD").splitlines() if l]
    for rel in rels:
        if not rel.endswith(".py"):
            continue
        diff = must(wt, "diff", base_sha, "HEAD", "--", rel)
        old = must(wt, "show", f"{base_sha}:{rel}")
        new = must(wt, "show", f"HEAD:{rel}")
        out[rel] = changed_symbols(diff, old, new)
    return out


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


ALL_SCHEMA_ERRORS = []  # global so tmpdir-cleaned journals stay auditable


class Journal:
    """Append-only JSONL with per-line section-1 schema validation."""

    def __init__(self, path):
        self.path = path
        self.events = []

    def append(self, etype, **fields):
        required = SCHEMA[etype]
        missing = required - set(fields)
        extra = set(fields) - required - SCHEMA_EXTENSIONS.get(etype, set())
        if missing or extra:
            ALL_SCHEMA_ERRORS.append(
                {"event": etype, "missing": sorted(missing),
                 "unexpected": sorted(extra)})
        ev = {"etype": etype, "ts_ms": monotonic_ms(), **fields}
        self.events.append(ev)
        with self.path.open("a") as f:
            f.write(json.dumps(ev, sort_keys=True) + "\n")
        return ev

    def last(self, etype, **match):
        for ev in reversed(self.events):
            if ev["etype"] == etype and all(
                    ev.get(k) == v for k, v in match.items()):
                return ev
        return None

    def all(self, etype, **match):
        return [ev for ev in self.events
                if ev["etype"] == etype
                and all(ev.get(k) == v for k, v in match.items())]


class UptakeHarness:
    """Poll-based watcher + protocol machinery over real worktrees."""

    ORACLE_ID = "symbol-overlap-wip-v0"
    HARNESS_REV = "skeleton-v0"

    def __init__(self, run_id, base_sha, agents, journal):
        # agents: {agent_id: {"wt": Path, "branch": str}}; ordered by agent_id
        self.run_id = run_id
        self.base_sha = base_sha
        self.agents = dict(sorted(agents.items()))
        self.journal = journal
        self.generation = 1
        self.seen_heads = {}        # agent_id -> sha already journaled
        self.emitted_keys = {}      # dedup key -> warning_id
        self.deliver_count = {}     # warning_id -> deliveries made
        self.notices = {}           # warning_id -> minted emit event fields
        self.inboxes = {a: [] for a in self.agents}
        self.ref_update_ts_ms = {}  # optional exact ref-update instants (test-provided)

    # -- vector helpers ---------------------------------------------------
    def observable_heads(self):
        return [{"agent_id": aid, "fork": spec["branch"],
                 "sha": must(spec["wt"], "rev-parse", spec["branch"])}
                for aid, spec in self.agents.items()]

    @staticmethod
    def canonical_vector(vec):
        return json.dumps(vec, sort_keys=True, separators=(",", ":"))

    def vector_current(self, minted_vector):
        return self.observable_heads() == minted_vector

    # -- protocol steps ---------------------------------------------------
    def run_start(self, fixture_id, seed_pairs):
        self.journal.append("run_start", run_id=self.run_id,
                            protocol_version="a01-uptake-rev2",
                            fixture_id=fixture_id, harness_rev=self.HARNESS_REV,
                            agents=sorted(self.agents), seed_pairs=seed_pairs)

    def scan_once(self):
        """One watcher tick: push observation + WIP/committed overlap scan."""
        t0 = monotonic_ms()
        new_pushes = 0
        for aid, spec in self.agents.items():
            head = must(spec["wt"], "rev-parse", spec["branch"])
            if self.seen_heads.get(aid) != head:
                count = must(spec["wt"], "rev-list", "--count", spec["branch"])
                parent = must(spec["wt"], "rev-parse", f"{spec['branch']}~1") \
                    if count != "1" else ""
                lag = (monotonic_ms() - self.ref_update_ts_ms[aid]
                       if aid in self.ref_update_ts_ms else 0)
                self.journal.append(
                    "push_observed", run_id=self.run_id, agent_id=aid, sha=head,
                    parent_sha=parent, ts_push_observed=monotonic_ms(),
                    branch=spec["branch"], watcher_lag_ms=lag)
                self.seen_heads[aid] = head
                new_pushes += 1

        wip = {aid: wip_evidence(spec["wt"]) for aid, spec in self.agents.items()}
        committed = {aid: committed_symbols(spec["wt"], self.base_sha)
                     for aid, spec in self.agents.items()}

        emitted_now = 0
        heads = self.observable_heads()
        for aid in self.agents:
            my_syms = set()
            for rel, (syms, _d) in wip[aid].items():
                my_syms |= syms
            if not my_syms:
                continue
            for peer in self.agents:
                if peer == aid:
                    continue
                peer_syms = set()
                for rel, syms in committed[peer].items():
                    peer_syms |= syms
                for rel, (syms, _d) in wip[peer].items():
                    peer_syms |= syms
                if my_syms & peer_syms:
                    if self._emit(aid, peer, heads):
                        emitted_now += 1
        return {"push_observed": new_pushes, "emitted": emitted_now,
                "scan_ms": monotonic_ms() - t0}

    def _emit(self, aid, peer, heads):
        pair = sorted([aid, peer])
        wip_diffs = []
        for who in pair:
            for _rel, (_syms, d) in wip_evidence(self.agents[who]["wt"]).items():
                wip_diffs.append(d)
        tdigest = sha256("|".join(wip_diffs) or "".join(pair))
        key = (self.base_sha, self.canonical_vector(heads), self.ORACLE_ID)
        fields = dict(
            warning_id=f"warn-{sha256(self.ORACLE_ID + tdigest)[:12]}",
            run_id=self.run_id, base_sha=self.base_sha[:12],
            head_vector=heads, pair=pair, failing="textual",
            oracle_id=self.ORACLE_ID, test_digest=tdigest[:16],
            ts_emitted=monotonic_ms(), generation=self.generation,
            wip_basis={"kind": "uncommitted_diff",
                       "artifact_ref": f"{aid}:uncommitted@{tdigest[:12]}"})
        if key in self.emitted_keys:
            fields["duplicate"] = True   # journaled, suppressed for delivery
            self.journal.append("emit", **fields)
            return False
        self.emitted_keys[key] = fields["warning_id"]
        self.journal.append("emit", **fields)
        self.notices[fields["warning_id"]] = fields
        self.deliver(fields["warning_id"], aid)
        return True

    def deliver(self, warning_id, agent_id):
        self.inboxes[agent_id].append(warning_id)
        self.deliver_count[warning_id] = self.deliver_count.get(warning_id, 0) + 1
        self.journal.append("deliver", warning_id=warning_id,
                            ts_delivered=monotonic_ms(), channel="inproc-queue-v0")

    def consume(self, warning_id, agent_id):
        current = self.vector_current(self.notices[warning_id]["head_vector"])
        self.journal.append("consume", warning_id=warning_id,
                            ts_consumed=monotonic_ms(), agent_id=agent_id,
                            vector_current=current)
        return current

    def record_action(self, warning_id, agent_id, action, generation,
                      started_offset_ms=0, new_head_sha=""):
        minted = self.notices[warning_id]
        if generation != self.generation:
            classification = "fenced"     # sec 3: older generation rejected
        elif not self.vector_current(minted["head_vector"]):
            classification = "stale"      # sec 3/4: correctness signal, not uptake
        else:
            classification = "uptake"
        self.journal.append(
            "agent_action", warning_id=warning_id, run_id=self.run_id,
            agent_id=agent_id, action=action,
            ts_action_started=monotonic_ms() - started_offset_ms,
            ts_action_ended=monotonic_ms(), new_head_sha=new_head_sha,
            generation=generation, classification=classification)
        return classification

    def crash(self, agent_id):
        old = self.generation
        self.generation += 1
        self.journal.append("fence_event", run_id=self.run_id, kind="crash",
                            old_generation=old, new_generation=self.generation,
                            ts=monotonic_ms())

    def run_outcome(self, merged_clean, combined_pass, landed_sha,
                    repair_seconds=0.0, wasted_work_seconds=0.0):
        self.journal.append("run_outcome", run_id=self.run_id,
                            merged_clean=merged_clean, combined_pass=combined_pass,
                            landed_sha=landed_sha,
                            ts_integration_tested=monotonic_ms(),
                            repair_seconds=repair_seconds,
                            wasted_work_seconds=wasted_work_seconds)

    def run_end(self):
        self.journal.append("run_end", run_id=self.run_id, ts=monotonic_ms())

    # -- watcher loop -----------------------------------------------------
    def start_watcher(self, stop_event):
        def loop():
            while not stop_event.is_set():
                self.scan_once()
                stop_event.wait(POLL_INTERVAL_S)
        th = threading.Thread(target=loop, daemon=True)
        th.start()
        return th


# --- fixture material ---------------------------------------------------

def make_util_py():
    return ("def calc_total(items):\n"
            "    return sum(i['price'] for i in items)\n\n"
            "def apply_discount(total, pct):\n"
            "    return total * (1 - pct / 100.0)\n\n"
            "def format_receipt(total):\n"
            "    return f'total={total:.2f}'\n")


def seeded_collision(base):
    """Scenarios 1+2: real watcher, WIP emit before commit, uptake, dedup."""
    repo = base / "seeded"
    init_repo(repo)
    (repo / "util.py").write_text(make_util_py())
    base_sha = commit_all(repo, "base")
    agents = {}
    for aid in ("agentA", "agentB", "agentC"):
        must(repo, "worktree", "add", "-q", "-b", aid, str(base / f"wt_{aid}"))
        agents[aid] = {"wt": base / f"wt_{aid}", "branch": aid}
    journal = Journal(base / "seeded.jsonl")
    h = UptakeHarness("skel-seeded-001", base_sha, agents, journal)
    h.run_start(fixture_id="util-py-discount", seed_pairs=[["agentA", "agentB"]])

    stop = threading.Event()
    h.start_watcher(stop)
    time.sleep(POLL_INTERVAL_S * 2)        # watcher settles baseline heads

    # A edits apply_discount, leaves it UNCOMMITTED, keeps working.
    (agents["agentA"]["wt"] / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return total * (1 - pct / 100.0) + 0.5  # A fee"))
    time.sleep(0.8)                        # simulated A work inside the WIP window

    # B commits an overlapping apply_discount change; interaction now exists.
    h.ref_update_ts_ms["agentB"] = monotonic_ms()
    (agents["agentB"]["wt"] / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return round(total * (1 - pct / 100.0), 2)  # B"))
    commit_all(agents["agentB"]["wt"], "B: round discounted total")

    # watcher tick must observe the push and emit+deliver to A
    deadline = time.monotonic() + 5 * POLL_INTERVAL_S + 3
    while time.monotonic() < deadline and not h.inboxes["agentA"]:
        time.sleep(0.05)
    delivered = bool(h.inboxes["agentA"])
    t_delivered = time.monotonic()
    warn_id = h.inboxes["agentA"][0]
    emit_ev = journal.last("emit", warning_id=warn_id)
    push_ev = journal.last("push_observed", agent_id="agentB")
    watcher_lag_ms = push_ev["watcher_lag_ms"]
    time.sleep(0.8)                        # more simulated A work after delivery
    h.scan_once()                          # unchanged state: must journal a duplicate

    # A consumes: vector still current (A's observable head is still base)
    current = h.consume(warn_id, "agentA")
    cls = h.record_action(warn_id, "agentA", "pause_rebase_adopt_peers_line",
                          generation=emit_ev["generation"], started_offset_ms=300)

    # A adjusts: adopts B's rounding line verbatim, moves the fee idea to
    # format_receipt. Identical same-line changes on both sides merge clean.
    b_line = "    return round(total * (1 - pct / 100.0), 2)  # B"
    resolved = (make_util_py()
                .replace("    return total * (1 - pct / 100.0)\n", b_line + "\n")
                .replace("    return f'total={total:.2f}'\n",
                         "    return f'total={total:.2f} (+fee)'  # A fee note\n"))
    (agents["agentA"]["wt"] / "util.py").write_text(resolved)
    landed = commit_all(agents["agentA"]["wt"], "A: adopt B rounding, fee to receipt")
    time.sleep(POLL_INTERVAL_S * 2)        # watcher observes A's push
    stop.set()
    time.sleep(0.1)

    mt = git(repo, "merge-tree", "--write-tree", "agentA", "agentB")
    clean = mt.returncode == 0
    h.run_outcome(merged_clean=clean, combined_pass=clean,  # textual proxy, no suite
                  landed_sha=landed[:12],
                  repair_seconds=round(time.monotonic() - t_delivered, 3),
                  wasted_work_seconds=1.6)  # simulated work inside WIP window

    dup_events = journal.all("emit", warning_id=warn_id)
    duplicate_journaled = any(e.get("duplicate") for e in dup_events)
    single_delivery = h.deliver_count[warn_id] == 1
    h.run_end()

    a_sha_at_emit = emit_ev["head_vector"][0]["sha"]  # agentA sorts first
    return {
        "scenario": "seeded_collision_watchloop",
        "warning_delivered_to_wip_agent": delivered,
        "emit_while_agentA_uncommitted": a_sha_at_emit.startswith(emit_ev["base_sha"]),
        "wip_basis_kind": emit_ev["wip_basis"]["kind"],
        "vector_scoped": emit_ev["head_vector"][0]["agent_id"] == "agentA",
        "consume_vector_current": current,
        "action_classification": cls,
        "watcher_lag_ms": watcher_lag_ms,
        "merge_tree_clean_after_resolution": clean,
        "duplicate_journaled_not_delivered": bool(duplicate_journaled
                                                  and single_delivery),
        "emit_events_for_warning": len(dup_events),
        "warning_id": warn_id,
    }


def stale_vector(base):
    """Scenario 3: sibling head advances between emit and consume -> stale."""
    repo = base / "stale"
    init_repo(repo)
    (repo / "util.py").write_text(make_util_py())
    base_sha = commit_all(repo, "base")
    agents = {}
    for aid in ("agentA", "agentB"):
        must(repo, "worktree", "add", "-q", "-b", f"x-{aid[-1]}",
             str(base / f"st_{aid}"))
        agents[aid] = {"wt": base / f"st_{aid}", "branch": f"x-{aid[-1]}"}
    journal = Journal(base / "stale.jsonl")
    h = UptakeHarness("skel-stale-001", base_sha, agents, journal)
    h.run_start(fixture_id="util-py-receipt", seed_pairs=[["agentA", "agentB"]])
    h.scan_once()                          # baseline heads

    (agents["agentA"]["wt"] / "util.py").write_text(
        make_util_py().replace("return f'total={total:.2f}'",
                               "return f'TOTAL {total:.2f} EUR'  # A"))
    (agents["agentB"]["wt"] / "util.py").write_text(
        make_util_py().replace("return f'total={total:.2f}'",
                               "return f'[{total:.2f}]'  # B"))
    commit_all(agents["agentB"]["wt"], "B: bracket receipt")
    h.scan_once()                          # emit on vector v1, deliver to A
    warn_id = h.inboxes["agentA"][0]

    # vector advances: B pushes AGAIN (unrelated file) before A consumes
    (agents["agentB"]["wt"] / "app.txt").write_text("unrelated\n")
    commit_all(agents["agentB"]["wt"], "B: unrelated advance")
    current = h.consume(warn_id, "agentA")
    cls = h.record_action(warn_id, "agentA", "rebase_anyway",
                          generation=h.generation)
    h.run_end()
    return {
        "scenario": "stale_vector_advance",
        "consume_vector_current": current,
        "action_classification": cls,
        "stale_not_counted_as_uptake": cls == "stale",
    }


def generation_fence(base):
    """Scenario 4: notice minted pre-crash rejected post-restart."""
    repo = base / "fence"
    init_repo(repo)
    (repo / "util.py").write_text(make_util_py())
    base_sha = commit_all(repo, "base")
    agents = {}
    for aid in ("agentA", "agentB"):
        must(repo, "worktree", "add", "-q", "-b", f"f-{aid[-1]}",
             str(base / f"fc_{aid}"))
        agents[aid] = {"wt": base / f"fc_{aid}", "branch": f"f-{aid[-1]}"}
    journal = Journal(base / "fence.jsonl")
    h = UptakeHarness("skel-fence-001", base_sha, agents, journal)
    h.run_start(fixture_id="util-py-discount", seed_pairs=[["agentA", "agentB"]])
    h.scan_once()

    (agents["agentA"]["wt"] / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return total * (1 - pct / 100.0) - 1  # A"))
    (agents["agentB"]["wt"] / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return (total * (1 - pct / 100.0)) * 0.9  # B"))
    commit_all(agents["agentB"]["wt"], "B: extra coupon")
    h.scan_once()
    warn_id = h.inboxes["agentA"][0]
    gen_at_mint = h.notices[warn_id]["generation"]

    h.crash("agentA")
    cls = h.record_action(warn_id, "agentA", "rebase_stale_lease",
                          generation=gen_at_mint)
    h.run_end()
    return {
        "scenario": "generation_fence",
        "generation_at_mint": gen_at_mint,
        "generation_after_crash": h.generation,
        "action_classification": cls,
        "fenced_action_rejected": cls == "fenced",
    }


def no_overlap_control(base):
    """Scenario 5: disjoint symbols produce no emit through the full path."""
    repo = base / "control"
    init_repo(repo)
    (repo / "util.py").write_text(make_util_py())
    base_sha = commit_all(repo, "base")
    agents = {}
    for aid in ("agentA", "agentB"):
        must(repo, "worktree", "add", "-q", "-b", f"c-{aid[-1]}",
             str(base / f"ct_{aid}"))
        agents[aid] = {"wt": base / f"ct_{aid}", "branch": f"c-{aid[-1]}"}
    journal = Journal(base / "control.jsonl")
    h = UptakeHarness("skel-control-001", base_sha, agents, journal)
    h.run_start(fixture_id="util-py-disjoint", seed_pairs=[])
    (agents["agentA"]["wt"] / "util.py").write_text(
        make_util_py().replace("return f'total={total:.2f}'",
                               "return f'r={total:.2f}'  # A receipt"))
    (agents["agentB"]["wt"] / "util.py").write_text(
        make_util_py().replace("return sum(i['price'] for i in items)",
                               "return sum(i['price'] for i in items)  # B totals"))
    commit_all(agents["agentB"]["wt"], "B: totals comment")
    res = h.scan_once()
    h.run_end()
    return {
        "scenario": "no_overlap_control",
        "emitted": res["emitted"],
        "no_false_positive": res["emitted"] == 0,
    }


def real_repo_scan(base):
    """Scenario 6: one real scan pass on a clone of THIS workspace repo."""
    src = Path(__file__).resolve().parents[3]
    clone = base / "realrepo"
    r = git(src, "clone", "-q", "--no-hardlinks", str(src), str(clone))
    if r.returncode != 0:
        return {"scenario": "real_repo_scan", "error": r.stderr.strip()[:200]}
    target = (clone / "research" / "zcode" / "independent"
              / "a01-wip-feasibility-fixture.py")
    original = target.read_text()
    # real uncommitted edit inside a real function body (_def_spans)
    target.write_text(original.replace("    spans = []\n",
                                       "    spans = []  # real-repo WIP probe\n", 1))
    journal = Journal(base / "real.jsonl")
    head = must(clone, "rev-parse", "HEAD")
    h = UptakeHarness("skel-real-001", head,
                      {"probe": {"wt": clone, "branch": "HEAD"}}, journal)
    h.run_start(fixture_id="cloudflare-agent-git-probe", seed_pairs=[])
    res = h.scan_once()
    ev_pairs = wip_evidence(clone).values()
    syms = sorted(set().union(*(s for s, _d in ev_pairs))) if ev_pairs else []
    n_files = subprocess.run(["git", "ls-files"], cwd=clone,
                             capture_output=True, text=True).stdout.count("\n")
    return {
        "scenario": "real_repo_scan",
        "repo_files": n_files,
        "wip_symbols_extracted": syms,
        "expected_symbol_present": "_def_spans" in syms,
        "scan_ms": res["scan_ms"],
    }


def main():
    t_start = time.perf_counter()
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="zc_harness_v0_") as tmp:
        base = Path(tmp)
        seeded = seeded_collision(base)
        stale = stale_vector(base)
        fence = generation_fence(base)
        control = no_overlap_control(base)
        real = real_repo_scan(base)

    wall_s = round(time.perf_counter() - t_start, 1)
    checks = {
        "warning_delivered_to_wip_agent": seeded["warning_delivered_to_wip_agent"],
        "emit_while_agentA_uncommitted": seeded["emit_while_agentA_uncommitted"],
        "wip_basis_uncommitted_diff": seeded["wip_basis_kind"] == "uncommitted_diff",
        "vector_scoped_notice": seeded["vector_scoped"],
        "watcher_lag_within_budget": seeded["watcher_lag_ms"] <= WATCHER_LAG_BUDGET_MS,
        "uptake_classified_on_current_vector": seeded["action_classification"] == "uptake",
        "merge_clean_after_resolution": seeded["merge_tree_clean_after_resolution"],
        "duplicate_journaled_not_delivered": seeded["duplicate_journaled_not_delivered"],
        "stale_detected_not_uptake": stale["stale_not_counted_as_uptake"],
        "fenced_action_rejected": fence["fenced_action_rejected"],
        "no_false_positive_disjoint": control["no_false_positive"],
        "real_repo_wip_symbols_found": real.get("expected_symbol_present", False),
        "journal_schema_valid": not ALL_SCHEMA_ERRORS,
    }
    results = {
        "timestamp": wall_iso(),
        "runner": "zcode-independent (aplexer d54c1e11)",
        "purpose": ("harness skeleton v0 for a01-uptake-protocol.md rev 2: watcher + "
                    "vector/dedup/stale/fence machinery on real worktrees with scripted "
                    "stand-in agents; NOT the R2-1/Y1 kill test (no live agents; "
                    "deliver->consume and consume->action latencies unmeasured)"),
        "poll_interval_s": POLL_INTERVAL_S,
        "watcher_lag_budget_ms": WATCHER_LAG_BUDGET_MS,
        "schema_extensions_declared": {k: sorted(v)
                                       for k, v in SCHEMA_EXTENSIONS.items()},
        "schema_errors": ALL_SCHEMA_ERRORS,
        "wall_seconds": wall_s,
        "scenarios": {"seeded": seeded, "stale": stale, "fence": fence,
                      "control": control, "real_repo": real},
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({k: results[k] for k in
                      ("timestamp", "wall_seconds", "checks", "all_checks_pass")},
                     indent=2))
    print(f"\nseeded: delivered={seeded['warning_delivered_to_wip_agent']} "
          f"uptake={seeded['action_classification']} "
          f"lag={seeded['watcher_lag_ms']}ms "
          f"duplicate_ok={seeded['duplicate_journaled_not_delivered']}")
    print(f"stale={stale['action_classification']} "
          f"fence={fence['action_classification']} "
          f"control_emit={control['emitted']} "
          f"real_scan={real.get('scan_ms')}ms syms={real.get('wip_symbols_extracted')}")
    print(f"results: {RESULTS_PATH}")
    return 0 if results["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
