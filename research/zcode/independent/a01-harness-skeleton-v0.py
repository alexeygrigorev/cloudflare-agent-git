#!/usr/bin/env python3
"""A01 uptake protocol rev 2: harness skeleton v0.2. ZCode independent, 2026-10-02.

v0.1 incorporates the accepted Grok R7-1/2/3 corrections (research/grok/
r7-a01-harness-challenge.md, commit 247d9cb) at the harness-machinery level:

  R7-3  pass/fail comes from a REAL external pinned oracle committed in the
        scratch fixture (test_suite.py run by subprocess at base / A / B /
        combined), never from a constant. Warnings for the behavioral
        scenario carry failing="combined_behavior" with oracle_status=
        "verified": the harness materializes each agent's UNCOMMITTED work
        as a tree (temp index + write-tree), merge-trees the two WIP trees,
        and runs the suite on the combined tree BEFORE either agent commits.
        Symbol overlap stays in as an advisory scanner only (oracle_status=
        "advisory"), never pass/fail.
  R7-1  agent events (consume/action) are no longer recorded by the harness
        calling itself: the scripted agent writes them to a per-agent OUTBOX
        file (the contract a live z.ai executor process would honor) and the
        harness ingests that file, countersigning vector currency and
        generation at ingest. The funnel counts (eligible / delivered /
        consumed / current / stale / fenced / ignored / effective) are
        computed from the journal, per codex-principal's reporting request.
  R7-2  no repair/wasted-work figure is claimed here at all: those numbers
        require paired arms with a real model (grok-head's live smoke). The
        skeleton records only machinery-level latencies it actually
        measures.

New scenario: BOTH writers uncommitted (the case v0 did not cover) - the
harness warns both agents before either commits.

Carried from v0: poll-based watcher over real git worktrees, section 1
schema-validated JSONL journal, base_sha + ordered head_vector scoping,
dedup with duplicate journaling, vector_current re-checks, generation
fence, stale/fenced/uptake classification, real-repo scan.

NOT the R2-1/Y1 kill test. Agents remain deterministic scripted stand-ins;
deliver->consume and consume->action latencies of a real model are
unmeasured; the live arms (notice vs no-notice, wasted work, repair effort)
belong to grok-head's allocated pilot. Self-contained, stdlib only,
self-cleaning /tmp scratch, well under 512 MB.
"""

import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import io
from datetime import datetime, timezone
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "a01-harness-skeleton-v0-results.json"
POLL_INTERVAL_S = 0.4
WATCHER_LAG_BUDGET_MS = 2 * POLL_INTERVAL_S * 1000
ORACLE_TIMEOUT_S = 30

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
    "emit": {"duplicate", "oracle_status", "wip_digest"},  # dedup incl. WIP content
    "agent_action": {"classification", "source"},    # sec 4 class; agent_outbox|test
    "push_observed": {"watcher_lag_ms"},
    "consume": {"ts_agent_reported"},
    "run_end": {"retention"},
}
SUITE_NAME = "test_suite.py"


def monotonic_ms():
    return time.monotonic_ns() // 1_000_000


def wall_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def git(cwd, *args, timeout=60, env=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=timeout, env=env)


def must(cwd, *args, **kw):
    r = git(cwd, *args, **kw)
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


# --- external pinned oracle ---------------------------------------------

SUITE_TEXT = (
    "import sys\n"
    "from util import apply_discount, format_receipt\n"
    "r = format_receipt(apply_discount(100, 10))\n"
    "assert r.startswith('total='), r\n"
    "num = float(r[len('total='):])\n"
    "assert 0 < num < 100, r\n"
    "print('ORACLE-PASS', r)\n"
)

def oracle_id():
    return "external-suite-" + sha256(SUITE_TEXT)[:8]


def run_oracle(dirpath):
    """Run the pinned suite in a directory; return (rc, summary)."""
    r = subprocess.run([sys.executable, SUITE_NAME], cwd=dirpath,
                       capture_output=True, text=True, timeout=ORACLE_TIMEOUT_S)
    return r.returncode, (r.stdout.strip() or r.stderr.strip().splitlines()[-1]
                          if (r.stdout.strip() or r.stderr.strip()) else "")


def wip_tree(wt):
    """Materialize a worktree's UNCOMMITTED state as a tree object without
    touching its real index: GIT_INDEX_FILE=<nonexistent> git add -A;
    git write-tree. The index path must NOT pre-exist: git rejects a
    zero-byte index file ("smaller than expected")."""
    with tempfile.TemporaryDirectory(prefix="wipidx_") as td:
        idx = Path(td) / "index"
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "GIT_INDEX_FILE": str(idx)}
        git(wt, "add", "-A", env=env)
        return must(wt, "write-tree", env=env)


def tree_to_dir(repo, tree, dest):
    """Materialize a tree object into a directory via git archive."""
    raw = subprocess.run(["git", "archive", "--format=tar", tree], cwd=repo,
                         capture_output=True, timeout=30, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
        tf.extractall(dest)


def tree_to_commit(repo, tree, base_sha):
    """Wrap a tree as a commit on top of base so merge-tree can combine it."""
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin",
           "GIT_AUTHOR_NAME": "Skeleton", "GIT_AUTHOR_EMAIL": "skeleton@test",
           "GIT_COMMITTER_NAME": "Skeleton", "GIT_COMMITTER_EMAIL": "skeleton@test"}
    return subprocess.run(["git", "commit-tree", tree, "-p", base_sha,
                           "-m", f"wip {tree[:8]}"], cwd=repo,
                          capture_output=True, text=True, env=env,
                          timeout=30, check=True).stdout.strip()


def combined_oracle(repo, base_sha, tree_a, tree_b):
    """merge-tree two trees (WIP or committed) onto base, run suite on the
    combined tree. Returns dict(clean, pass_, rc, detail)."""
    try:
        ca = tree_to_commit(repo, tree_a, base_sha)
        cb = tree_to_commit(repo, tree_b, base_sha)
    except (subprocess.SubprocessError, subprocess.CalledProcessError) as e:
        return {"clean": False, "pass_": False, "rc": -1, "detail": str(e)[:80]}
    mt = git(repo, "merge-tree", "--write-tree", ca, cb)
    clean = mt.returncode == 0
    if not clean:
        return {"clean": False, "pass_": False, "rc": mt.returncode,
                "detail": "merge conflict"}
    tree = mt.stdout.split()[0]
    with tempfile.TemporaryDirectory(dir=repo.parent, prefix="combined_") as td:
        tree_to_dir(repo, tree, td)
        rc, detail = run_oracle(td)
    return {"clean": True, "pass_": rc == 0, "rc": rc, "detail": detail[:80]}


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


# --- symbol-overlap advisory scanner (kept from v0; advisory only) ------

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


ALL_SCHEMA_ERRORS = []


class Journal:
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
    """Poll-based watcher + protocol machinery over real worktrees.

    Agent events enter ONLY through per-agent outbox files (the live-run
    contract): each line is JSON {event: consume|action, warning_id, action?,
    generation?, ts_agent_monotonic_ms}. ingest_outbox() journals them with
    harness-observed vector/generation countersigns.
    """

    HARNESS_REV = "skeleton-v0.2"
    ADVISORY_ORACLE = "symbol-overlap-wip-v0"
    REACTION_WINDOW_MS = 600_000  # sec 4 default; not binding in the skeleton

    def __init__(self, run_id, base_sha, agents, journal, workdir):
        self.run_id = run_id
        self.base_sha = base_sha
        self.agents = dict(sorted(agents.items()))
        self.journal = journal
        self.workdir = workdir
        self.generation = 1
        self.seen_heads = {}
        self.emitted_keys = {}
        self.deliver_count = {}
        self.notices = {}
        self.notice_files = {}      # warning_id -> notice file path (agent reads this)
        self.inboxes = {a: [] for a in self.agents}
        self.outbox_path = {a: workdir / f"outbox_{a}.jsonl" for a in self.agents}
        self.outbox_offset = {a: 0 for a in self.agents}
        self.ref_update_ts_ms = {}
        # per-run scratch: outbox/notice files must never outlive the run's
        # offsets (a shared workdir would replay a prior scenario's outbox)
        workdir.mkdir(parents=True, exist_ok=True)

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
        # pinned oracle files land in every worktree via the base commit
        self.journal.append("run_start", run_id=self.run_id,
                            protocol_version="a01-uptake-rev2",
                            fixture_id=fixture_id, harness_rev=self.HARNESS_REV,
                            agents=sorted(self.agents), seed_pairs=seed_pairs)

    def scan_once(self):
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

        emitted_now = 0
        heads = self.observable_heads()
        # arm 1: oracle-verified scan - combine all WIP trees pairwise and run
        # the pinned suite on the combined tree BEFORE either agent commits
        wip_trees = {aid: (wip_tree(spec["wt"]) if must(
            spec["wt"], "status", "--porcelain").strip() else None)
            for aid, spec in self.agents.items()}
        active = [aid for aid, t in wip_trees.items() if t]
        for i, aid in enumerate(active):
            for peer in active[i + 1:]:
                res = combined_oracle(self._main_repo(), self.base_sha,
                                      wip_trees[aid], wip_trees[peer])
                if not res["pass_"]:
                    if self._emit(aid, peer, heads, failing="combined_behavior",
                                  oracle=self._oracle_ref(), status="verified",
                                  detail=res["detail"],
                                  wip_digest=sha256(wip_trees[aid]
                                                    + wip_trees[peer])):
                        emitted_now += 1
        # arm 2: advisory symbol-overlap scan (WIP vs peer committed/WIP)
        wip = {aid: wip_evidence(spec["wt"]) for aid, spec in self.agents.items()}
        committed = {aid: committed_symbols(spec["wt"], self.base_sha)
                     for aid, spec in self.agents.items()}
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
                    if self._emit(aid, peer, heads, failing="textual",
                                  oracle=self.ADVISORY_ORACLE, status="advisory",
                                  detail="symbol overlap",
                                  wip_digest=sha256(
                                      "|".join(sorted(my_syms & peer_syms)))):
                        emitted_now += 1
        return {"push_observed": new_pushes, "emitted": emitted_now,
                "scan_ms": monotonic_ms() - t0}

    def _main_repo(self):
        # all fixture worktrees share one main repo; store it on first use
        if not hasattr(self, "_repo"):
            first = next(iter(self.agents.values()))["wt"]
            gitdir = must(first, "rev-parse", "--git-common-dir")
            self._repo = Path(gitdir).resolve().parent
        return self._repo

    def _oracle_ref(self):
        return f"{oracle_id()}@suite:{SUITE_NAME}"

    def _emit(self, aid, peer, heads, failing, oracle, status, detail,
              wip_digest):
        # v0.2: the dedup key includes the digest of the triggering WIP
        # evidence. Unchanged WIP re-scans still dedupe (no spam); MATERIALLY
        # CHANGED WIP re-emits under a fresh warning_id so a writer who keeps
        # editing after a warning gets re-notified.
        pair = sorted([aid, peer])
        # warning_id covers BOTH the failing behavior and the exact WIP
        # evidence state: two WIP states with the same failure manifestation
        # are distinct notices (a consumer must tell stale from fresh).
        tdigest = sha256(detail + "|".join(pair) + oracle + wip_digest)
        key = (self.base_sha, self.canonical_vector(heads), oracle, wip_digest)
        fields = dict(
            warning_id=f"warn-{tdigest[:12]}",
            run_id=self.run_id, base_sha=self.base_sha[:12],
            head_vector=heads, pair=pair, failing=failing,
            oracle_id=oracle, test_digest=tdigest[:16],
            ts_emitted=monotonic_ms(), generation=self.generation,
            wip_basis={"kind": "uncommitted_diff",
                       "artifact_ref": f"{aid}:uncommitted@{wip_digest[:12]}"},
            oracle_status=status, wip_digest=wip_digest)
        if key in self.emitted_keys:
            fields["duplicate"] = True
            self.journal.append("emit", **fields)
            return False
        self.emitted_keys[key] = fields["warning_id"]
        self.journal.append("emit", **fields)
        self.notices[fields["warning_id"]] = fields
        for member in pair:          # both writers are warned (R7-3 ask)
            self.deliver(fields["warning_id"], member)
        return True

    def deliver(self, warning_id, agent_id):
        # notice lands as a FILE the agent process reads (live-run contract);
        # the in-proc list mirrors it for the scripted stand-ins.
        nf = self.workdir / f"notice_{warning_id}_{agent_id}.json"
        nf.write_text(json.dumps(self.notices[warning_id]))
        self.notice_files[warning_id] = nf
        self.inboxes[agent_id].append(warning_id)
        self.deliver_count[warning_id] = self.deliver_count.get(warning_id, 0) + 1
        self.journal.append("deliver", warning_id=warning_id,
                            ts_delivered=monotonic_ms(), channel="notice-file-v0.1")

    # -- agent-side events via outbox (R7-1 contract) ---------------------
    def agent_report(self, agent_id, payload):
        """Called by the AGENT side (scripted stand-in here; a live executor
        process in the real run): append to the agent's outbox file."""
        with self.outbox_path[agent_id].open("a") as f:
            f.write(json.dumps(payload) + "\n")

    def ingest_outbox(self, agent_id):
        """Harness side: journal new outbox lines with countersigns."""
        p = self.outbox_path[agent_id]
        if not p.exists():
            return []
        lines = p.read_text().splitlines()[self.outbox_offset[agent_id]:]
        self.outbox_offset[agent_id] += len(lines)
        ingested = []
        for line in lines:
            msg = json.loads(line)
            wid = msg["warning_id"]
            if msg["event"] == "consume":
                current = self.vector_current(self.notices[wid]["head_vector"])
                ev = self.journal.append(
                    "consume", warning_id=wid, ts_consumed=monotonic_ms(),
                    agent_id=agent_id, vector_current=current,
                    ts_agent_reported=msg.get("ts_agent_monotonic_ms"))
                ingested.append(ev)
            elif msg["event"] == "action":
                minted = self.notices[wid]
                if msg.get("generation", self.generation) != self.generation:
                    classification = "fenced"
                elif not self.vector_current(minted["head_vector"]):
                    classification = "stale"
                else:
                    classification = "uptake"
                ev = self.journal.append(
                    "agent_action", warning_id=wid, run_id=self.run_id,
                    agent_id=agent_id, action=msg["action"],
                    ts_action_started=msg.get("ts_agent_monotonic_ms",
                                              monotonic_ms()),
                    ts_action_ended=monotonic_ms(),
                    new_head_sha=msg.get("new_head_sha", ""),
                    generation=msg.get("generation", self.generation),
                    classification=classification, source="agent_outbox")
                ingested.append(ev)
        return ingested

    def crash(self, agent_id):
        old = self.generation
        self.generation += 1
        self.journal.append("fence_event", run_id=self.run_id, kind="crash",
                            old_generation=old, new_generation=self.generation,
                            ts=monotonic_ms())

    def run_outcome(self, merged_clean, combined_pass, landed_sha,
                    repair_seconds=None, wasted_work_seconds=None):
        # repair/wasted-work stay unset here: real values require the live
        # paired arms (grok-head pilot); None is journaled, never fabricated.
        self.journal.append("run_outcome", run_id=self.run_id,
                            merged_clean=merged_clean, combined_pass=combined_pass,
                            landed_sha=landed_sha,
                            ts_integration_tested=monotonic_ms(),
                            repair_seconds=repair_seconds,
                            wasted_work_seconds=wasted_work_seconds)

    def run_end(self):
        # retention: the run's journal, notices, outboxes and any candidate
        # bundles stay on disk until an independent reviewer releases them
        self.journal.append("run_end", run_id=self.run_id, ts=monotonic_ms(),
                            retention="bundle+scratch preserved until "
                                      "independent review release")

    def funnel(self):
        """codex-requested counts, computed from the journal."""
        j = self.journal
        emitted = [e for e in j.all("emit") if not e.get("duplicate")]
        delivered = j.all("deliver")
        consumed = j.all("consume")
        consumed_ids = {c["warning_id"] for c in consumed}
        current = {c["warning_id"] for c in consumed if c["vector_current"]}
        actions = j.all("agent_action")
        acted = {a["warning_id"] for a in actions}
        uptake = len([a for a in actions if a["classification"] == "uptake"])
        return {
            "eligible_emitted": len(emitted),
            "delivered": len(delivered),
            "consumed": len(consumed),
            # per-event count (two agents consuming one warning = 2 events)
            "consumed_vector_current": len([c for c in consumed
                                            if c["vector_current"]]),
            "effective_action_uptake": uptake,
            "effective_action_rate": (round(uptake / len(emitted), 3)
                                      if emitted else "undefined"),
            "stale_actions": len([a for a in actions
                                  if a["classification"] == "stale"]),
            "fenced_actions": len([a for a in actions
                                   if a["classification"] == "fenced"]),
            "ignored": len(current - acted),
        }

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


def seed_fixture(path):
    """Base repo: util.py + the pinned oracle suite, committed once."""
    init_repo(path)
    (path / "util.py").write_text(make_util_py())
    (path / SUITE_NAME).write_text(SUITE_TEXT)
    return commit_all(path, "base: util + pinned oracle suite")


def add_agent(repo, name, branch):
    # wt dir keyed by branch: branch names are unique per scenario, so
    # scenario fixtures never collide on worktree paths
    base = repo.parent
    wt = base / f"wt_{branch.replace('-', '_')}"
    must(repo, "worktree", "add", "-q", "-b", branch, str(wt))
    return {"wt": wt, "branch": branch}


def scenario_behavioral_both_wip(base):
    """R7 answer scenario: BOTH writers uncommitted; the pinned external
    oracle fails on the combined WIP trees; BOTH agents are warned before
    either commits; both act via outbox; resolution makes combined pass."""
    repo = base / "repo"
    base_sha = seed_fixture(repo)
    agents = {aid: add_agent(repo, aid, aid)
              for aid in ("agentA", "agentB", "agentC")}
    journal = Journal(base / "behavioral.jsonl")
    h = UptakeHarness("skel-behavioral-001", base_sha, agents, journal,
                      base / "ws_behavioral")
    h.run_start(fixture_id="discount-fee-x-receipt-assert",
                seed_pairs=[["agentA", "agentB"]])

    stop = threading.Event()
    h.start_watcher(stop)
    time.sleep(POLL_INTERVAL_S * 2)

    # oracle sanity: base passes in each worktree
    base_rc, _ = run_oracle(agents["agentA"]["wt"])

    # BOTH agents leave overlapping-behavior WIP:
    # A: +0.555 fee  -> combined receipt prints total=90.56 (unrounded input)
    # B: assert pre-rounded total inside format_receipt -> combined FAILS
    (agents["agentA"]["wt"] / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return total * (1 - pct / 100.0) + 0.555  # A fee"))
    (agents["agentB"]["wt"] / "util.py").write_text(
        make_util_py().replace("return f'total={total:.2f}'",
                               "assert total == round(total, 2), 'pre-round total'\n"
                               "    return f'total={total:.2f}'"))
    h.ref_update_ts_ms["agentB"] = monotonic_ms()  # unused here; B stays WIP
    time.sleep(POLL_INTERVAL_S * 3)      # watcher ticks: must warn BOTH

    delivered_a = bool(h.inboxes["agentA"])
    delivered_b = bool(h.inboxes["agentB"])
    # find the verified emit (oracle arm, not advisory)
    ver = [e for e in journal.all("emit")
           if e.get("oracle_status") == "verified" and not e.get("duplicate")]
    verified_emit = ver[0] if ver else None
    # a_sha/b_sha at emit must be base for BOTH (nothing committed yet)
    shas_at_emit = {v["agent_id"]: v["sha"][:12] for v in verified_emit["head_vector"]} \
        if verified_emit else {}

    # both agents consume + act THROUGH THE OUTBOX (R7-1: agent-side emission)
    for aid in ("agentA", "agentB"):
        h.agent_report(aid, {"event": "consume",
                             "warning_id": verified_emit["warning_id"],
                             "ts_agent_monotonic_ms": monotonic_ms()})
        h.agent_report(aid, {"event": "action", "action": "pause_adjust_wip",
                             "warning_id": verified_emit["warning_id"],
                             "generation": verified_emit["generation"],
                             "ts_agent_monotonic_ms": monotonic_ms()})
    time.sleep(0.1)
    h.ingest_outbox("agentA")
    h.ingest_outbox("agentB")
    classes = {a["agent_id"]: a["classification"]
               for a in journal.all("agent_action", source="agent_outbox")}

    # v0.2 regression: UNCHANGED WIP re-scans must stay deduped (no notice
    # spam), MATERIALLY CHANGED WIP must re-emit under a fresh key so a
    # writer who keeps editing after a warning is re-notified.
    wid_v1 = verified_emit["warning_id"]
    digest_v1 = verified_emit["wip_digest"]
    dedup_no_spam = len([d for d in journal.all("deliver")
                         if d["warning_id"] == wid_v1]) == 2
    (agents["agentA"]["wt"] / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return total * (1 - pct / 100.0) + 0.777  # A fee v2"))
    time.sleep(POLL_INTERVAL_S * 3)      # watcher ticks: changed WIP -> re-emit
    ver2 = [e for e in journal.all("emit")
            if e.get("oracle_status") == "verified" and not e.get("duplicate")]
    changed_reemitted = (len(ver2) == 2
                         and ver2[1]["warning_id"] != wid_v1
                         and ver2[1]["wip_digest"] != digest_v1
                         and ver2[1]["wip_basis"]["artifact_ref"]
                         != verified_emit["wip_basis"]["artifact_ref"])

    # resolution: A discards the fee WIP entirely (the uptake action); B keeps
    # the assert. A's head stays at base - no commit is needed to adjust WIP.
    must(agents["agentA"]["wt"], "checkout", "--", "util.py")
    landed = must(agents["agentA"]["wt"], "rev-parse", "agentA")
    time.sleep(POLL_INTERVAL_S * 2)
    stop.set()
    time.sleep(0.1)

    # outcome: B still WIP; verify with combined oracle B-WIP x A-head
    b_tree = wip_tree(agents["agentB"]["wt"])
    a_head_tree = must(agents["agentA"]["wt"], "rev-parse", "agentA^{tree}")
    outcome = combined_oracle(repo, base_sha, b_tree, a_head_tree)

    # counterfactual: had A kept the fee, the combined tree WOULD fail.
    must(agents["agentA"]["wt"], "checkout", "-q", "-b", "naive")
    (agents["agentA"]["wt"] / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return total * (1 - pct / 100.0) + 0.555  # naive fee"))
    commit_all(agents["agentA"]["wt"], "naive: keep fee")
    naive_tree = must(agents["agentA"]["wt"], "rev-parse", "naive^{tree}")
    counterfactual = combined_oracle(repo, base_sha, b_tree, naive_tree)

    h.run_outcome(merged_clean=outcome["clean"], combined_pass=outcome["pass_"],
                  landed_sha=landed[:12])
    h.run_end()
    return {
        "scenario": "behavioral_both_wip",
        "oracle_base_pass_rc0": base_rc == 0,
        "warned_both_before_either_committed": bool(
            delivered_a and delivered_b
            and shas_at_emit.get("agentA") == base_sha[:12]
            and shas_at_emit.get("agentB") == base_sha[:12]),
        "failing_class": verified_emit["failing"] if verified_emit else None,
        "oracle_status": verified_emit.get("oracle_status") if verified_emit else None,
        "actions_classified": classes,
        "wip_digest_dedup_v1": wid_v1,
        "unchanged_wip_dedup_no_spam": dedup_no_spam,
        "changed_wip_reemitted_new_key": changed_reemitted,
        "resolution_combined_clean": outcome["clean"],
        "resolution_oracle_pass": outcome["pass_"],
        "counterfactual_naive_combined_fails": not counterfactual["pass_"],
        "funnel": h.funnel(),
    }


def scenario_stale(base):
    repo = base / "repo_stale"
    base_sha = seed_fixture(repo)
    agents = {aid: add_agent(repo, aid, f"x-{aid[-1]}")
              for aid in ("agentA", "agentB")}
    journal = Journal(base / "stale.jsonl")
    h = UptakeHarness("skel-stale-001", base_sha, agents, journal,
                      base / "ws_stale")
    h.run_start(fixture_id="stale-vector", seed_pairs=[["agentA", "agentB"]])
    h.scan_once()

    (agents["agentA"]["wt"] / "util.py").write_text(
        make_util_py().replace("return f'total={total:.2f}'",
                               "return f'TOTAL {total:.2f} EUR'  # A"))
    (agents["agentB"]["wt"] / "util.py").write_text(
        make_util_py().replace("return f'total={total:.2f}'",
                               "return f'[{total:.2f}]'  # B"))
    commit_all(agents["agentB"]["wt"], "B: bracket receipt")
    h.scan_once()
    wid = h.inboxes["agentA"][0]

    (agents["agentB"]["wt"] / "notes.txt").write_text("advance\n")
    commit_all(agents["agentB"]["wt"], "B: unrelated advance")
    h.agent_report("agentA", {"event": "consume", "warning_id": wid,
                              "ts_agent_monotonic_ms": monotonic_ms()})
    h.agent_report("agentA", {"event": "action", "action": "rebase_anyway",
                              "warning_id": wid, "generation": h.generation,
                              "ts_agent_monotonic_ms": monotonic_ms()})
    h.ingest_outbox("agentA")
    consume_ev = journal.last("consume", warning_id=wid)
    action_ev = journal.last("agent_action", warning_id=wid)
    h.run_end()
    return {
        "scenario": "stale_vector_advance",
        "consume_vector_current": consume_ev["vector_current"],
        "action_classification": action_ev["classification"],
        "stale_not_counted_as_uptake": action_ev["classification"] == "stale",
    }


def scenario_fence(base):
    repo = base / "repo_fence"
    base_sha = seed_fixture(repo)
    agents = {aid: add_agent(repo, aid, f"f-{aid[-1]}")
              for aid in ("agentA", "agentB")}
    journal = Journal(base / "fence.jsonl")
    h = UptakeHarness("skel-fence-001", base_sha, agents, journal,
                      base / "ws_fence")
    h.run_start(fixture_id="generation-fence", seed_pairs=[["agentA", "agentB"]])
    h.scan_once()

    (agents["agentA"]["wt"] / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return total * (1 - pct / 100.0) - 1  # A"))
    (agents["agentB"]["wt"] / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return (total * (1 - pct / 100.0)) * 0.9  # B"))
    commit_all(agents["agentB"]["wt"], "B: extra discount")
    h.scan_once()
    wid = h.inboxes["agentA"][0]
    gen_at_mint = h.notices[wid]["generation"]

    h.crash("agentA")
    # agent acts with the PRE-crash generation in its outbox message
    h.agent_report("agentA", {"event": "action", "action": "act_on_stale_lease",
                              "warning_id": wid, "generation": gen_at_mint,
                              "ts_agent_monotonic_ms": monotonic_ms()})
    h.ingest_outbox("agentA")
    action_ev = journal.last("agent_action", warning_id=wid)
    h.run_end()
    return {
        "scenario": "generation_fence",
        "generation_at_mint": gen_at_mint,
        "generation_after_crash": h.generation,
        "action_classification": action_ev["classification"],
        "fenced_action_rejected": action_ev["classification"] == "fenced",
    }


def scenario_control(base):
    """Oracle-verified negative control: disjoint edits combine to PASS."""
    repo = base / "repo_control"
    base_sha = seed_fixture(repo)
    agents = {aid: add_agent(repo, aid, f"c-{aid[-1]}")
              for aid in ("agentA", "agentB")}
    journal = Journal(base / "control.jsonl")
    h = UptakeHarness("skel-control-001", base_sha, agents, journal,
                      base / "ws_control")
    h.run_start(fixture_id="disjoint-control", seed_pairs=[])
    (agents["agentA"]["wt"] / "notes_a.txt").write_text("a\n")
    (agents["agentB"]["wt"] / "notes_b.txt").write_text("b\n")
    res = h.scan_once()
    # explicit oracle cross-check: the two WIP trees combine and pass
    ta = wip_tree(agents["agentA"]["wt"])
    tb = wip_tree(agents["agentB"]["wt"])
    outcome = combined_oracle(repo, base_sha, ta, tb)
    h.run_end()
    return {
        "scenario": "disjoint_control",
        "emitted": res["emitted"],
        "no_false_positive": res["emitted"] == 0,
        "control_combined_oracle_pass": outcome["pass_"],
        # v0.2: zero-warning run -> action rate must be "undefined", not 0
        "zero_warning_action_rate": h.funnel()["effective_action_rate"],
    }


def scenario_real_repo(base):
    src = Path(__file__).resolve().parents[3]
    clone = base / "realrepo"
    r = git(src, "clone", "-q", "--no-hardlinks", str(src), str(clone))
    if r.returncode != 0:
        return {"scenario": "real_repo_scan", "error": r.stderr.strip()[:200]}
    target = (clone / "research" / "zcode" / "independent"
              / "a01-wip-feasibility-fixture.py")
    original = target.read_text()
    target.write_text(original.replace("    spans = []\n",
                                       "    spans = []  # real-repo WIP probe\n", 1))
    journal = Journal(base / "real.jsonl")
    head = must(clone, "rev-parse", "HEAD")
    h = UptakeHarness("skel-real-001", head,
                      {"probe": {"wt": clone, "branch": "HEAD"}}, journal,
                      base / "ws_real")
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
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="zc_harness_v01_") as tmp:
        base = Path(tmp)
        behavioral = scenario_behavioral_both_wip(base)
        stale = scenario_stale(base)
        fence = scenario_fence(base)
        control = scenario_control(base)
        real = scenario_real_repo(base)

    wall_s = round(time.perf_counter() - t_start, 1)
    checks = {
        "oracle_base_passes": behavioral["oracle_base_pass_rc0"],
        "warned_both_before_either_committed":
            behavioral["warned_both_before_either_committed"],
        "failing_is_combined_behavior": behavioral["failing_class"] == "combined_behavior",
        "oracle_status_verified": behavioral["oracle_status"] == "verified",
        "actions_from_agent_outbox_uptake": all(
            v == "uptake" for v in behavioral["actions_classified"].values())
            and len(behavioral["actions_classified"]) == 2,
        "resolution_oracle_pass": behavioral["resolution_oracle_pass"],
        "counterfactual_naive_combined_fails":
            behavioral["counterfactual_naive_combined_fails"],
        "unchanged_wip_dedup_no_spam": behavioral["unchanged_wip_dedup_no_spam"],
        "changed_wip_reemits_new_key": behavioral["changed_wip_reemitted_new_key"],
        "zero_warning_rate_undefined":
            behavioral["funnel"]["effective_action_rate"] != "undefined"
            and control["zero_warning_action_rate"] == "undefined",
        "stale_detected_not_uptake": stale["stale_not_counted_as_uptake"],
        "fenced_action_rejected": fence["fenced_action_rejected"],
        "control_no_emit_and_oracle_pass": control["no_false_positive"]
            and control["control_combined_oracle_pass"],
        "real_repo_wip_symbols_found": real.get("expected_symbol_present", False),
        "journal_schema_valid": not ALL_SCHEMA_ERRORS,
    }
    results = {
        "timestamp": wall_iso(),
        "runner": "zcode-independent (aplexer d54c1e11)",
        "purpose": ("harness skeleton v0.2: grok R7-1/2/3 corrections at harness level - "
                    "external pinned oracle at base/A/B/combined, both-writers-uncommitted "
                    "warning, agent-side outbox emission, funnel counts; v0.2 adds "
                    "WIP-digest dedup key (unchanged WIP dedupes, changed WIP re-emits), "
                    "zero-warning action rate = undefined, run-end retention; NOT the "
                    "R2-1/Y1 kill test (scripted stand-ins; live arms are grok-head's pilot)"),
        "dedup_granularity": ("digest over the exact failing WIP tree pair "
                              "(content-addressed); one notice per distinct "
                              "failing WIP state; WIP churn re-emits by design "
                              "and shows up in funnel.delivered"),
        "oracle_id": oracle_id(),
        "poll_interval_s": POLL_INTERVAL_S,
        "watcher_lag_budget_ms": WATCHER_LAG_BUDGET_MS,
        "schema_extensions_declared": {k: sorted(v)
                                       for k, v in SCHEMA_EXTENSIONS.items()},
        "schema_errors": ALL_SCHEMA_ERRORS,
        "wall_seconds": wall_s,
        "scenarios": {"behavioral": behavioral, "stale": stale, "fence": fence,
                      "control": control, "real_repo": real},
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({k: results[k] for k in
                      ("timestamp", "wall_seconds", "checks", "all_checks_pass")},
                     indent=2))
    print(f"\nbehavioral: both_warned="
          f"{behavioral['warned_both_before_either_committed']} "
          f"classes={behavioral['actions_classified']} "
          f"resolution_pass={behavioral['resolution_oracle_pass']} "
          f"counterfactual_fails={behavioral['counterfactual_naive_combined_fails']}")
    print(f"funnel: {behavioral['funnel']}")
    print(f"results: {RESULTS_PATH}")
    return 0 if results["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
