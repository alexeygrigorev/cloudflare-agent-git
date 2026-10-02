#!/usr/bin/env python3
"""A01 uptake protocol rev 2: local feasibility spike for the unfinished-WIP
derivation constraint (emit.wip_basis). ZCode independent, 2026-10-02.

Self-contained, stdlib only, self-cleaning /tmp scratch (<250 MB peak).

Demonstrates, with local git only (no Cloudflare, no live agents):

1. WIP-derived warning feasibility: a harness scan of uncommitted worktree
   diffs + peer committed heads can emit a schema-conformant collision warning
   (wip_basis.kind=uncommitted_diff) BEFORE the colliding agent commits, i.e.
   strictly earlier than any completed-change-only oracle (STALE-style, arXiv
   2609.25396) can even see the change. Margin to commit is recorded.
2. False-positive control: disjoint changed-symbol sets emit no warning.
3. Scan-cost bounds at 4,000-file scale: cold/warm `git diff` and `git status`
   wall times, bounding the per-scan cost term of the Y1 latency budget.

This is a mechanism feasibility spike, NOT the R2-1/Y1 kill test: warnings are
derived from a fixture-grade symbol-overlap oracle, and no live agent work-time
is measured. Live-agent runs against a01-uptake-protocol.md rev 2 remain
principal-prioritized.
"""

import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS_PATH = Path(__file__).parent / "a01-wip-feasibility-results.json"
SCAN_MS_BUDGET_NOTE = "per-scan cost term for Y1 latency decomposition; harness-side only"


def git(cwd, *args, timeout=60):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout
    )


def must(cwd, *args):
    r = git(cwd, *args)
    if r.returncode != 0:
        raise SystemExit(f"git {args} failed in {cwd}:\n{r.stderr}")
    return r.stdout.strip()


def init_repo(path, branch="main"):
    path.mkdir(parents=True)
    must(path, "init", "-q", "-b", branch)
    must(path, "config", "user.name", "Fixture")
    must(path, "config", "user.email", "fixture@test")
    must(path, "config", "commit.gpgsign", "false")


def commit_all(path, msg):
    must(path, "add", "-A")
    must(path, "commit", "-q", "-m", msg)
    return must(path, "rev-parse", "HEAD")


DEF_RE = re.compile(r"def\s+([A-Za-z_]\w*)")
HUNK_HEAD_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _def_spans(text):
    spans = []
    for i, line in enumerate(text.splitlines()):
        m = re.match(r"def\s+([A-Za-z_]\w*)", line)
        if m:
            spans.append((i, m.group(1)))
    return spans


def _enclosing(spans, idx):
    name = None
    for start, sym in spans:
        if start <= idx:
            name = sym
        else:
            break
    return name


def changed_symbols(diff_text, old_text, new_text):
    """Top-level Python function symbols touched by a unified diff.

    Changed lines are mapped to their enclosing top-level `def` in the
    respective file version ('-' lines against the old content, '+' lines
    against the new content). Hunk-header funcname context is NOT used: git
    anchors it to the last funcname line before the hunk, which misattributes
    body edits in functions that directly follow a short function.
    """
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


def worktree_wip_symbols(wt, relpath):
    """Symbols touched by uncommitted edits to one file in a worktree."""
    diff = must(wt, "diff", "HEAD", "--", relpath)
    old = must(wt, "show", f"HEAD:{relpath}") if diff else ""
    new = (wt / relpath).read_text()
    return changed_symbols(diff, old, new), diff


def commit_symbols(wt, base_sha, relpath):
    """Symbols touched by one committed change to one file."""
    diff = must(wt, "diff", base_sha, "HEAD", "--", relpath)
    old = must(wt, "show", f"{base_sha}:{relpath}")
    new = must(wt, "show", f"HEAD:{relpath}")
    return changed_symbols(diff, old, new), diff


def digest(*texts):
    import hashlib
    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode())
    return h.hexdigest()


def make_util_py():
    return (
        "def calc_total(items):\n"
        "    return sum(i['price'] for i in items)\n\n"
        "def apply_discount(total, pct):\n"
        "    return total * (1 - pct / 100.0)\n\n"
        "def format_receipt(total):\n"
        "    return f'total={total:.2f}'\n"
    )


def emit_warning(run_id, base_sha, heads, failing, oracle_id, tdigest, wip_kind, artifact_ref):
    return {
        "warning_id": f"warn-{digest(oracle_id, tdigest)[:12]}",
        "run_id": run_id,
        "base_sha": base_sha[:12],
        "head_vector": [h[:12] for h in heads],
        "pair": ["agentA", "agentB"],
        "failing": failing,
        "oracle_id": oracle_id,
        "test_digest": tdigest[:16],
        "ts_emitted": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "generation": 1,
        "wip_basis": {"kind": wip_kind, "artifact_ref": artifact_ref},
    }


def scenario_overlap(base_tmp):
    """Warning derived from A's uncommitted diff fires before A commits."""
    repo = base_tmp / "overlap"
    init_repo(repo)
    (repo / "util.py").write_text(make_util_py())
    (repo / "app.py").write_text("from util import calc_total\nprint(calc_total([]))\n")
    base_sha = commit_all(repo, "base")
    must(repo, "worktree", "add", "-q", "-b", "agentA", str(base_tmp / "wtA"))
    must(repo, "worktree", "add", "-q", "-b", "agentB", str(base_tmp / "wtB"))
    wtA, wtB = base_tmp / "wtA", base_tmp / "wtB"

    # t0: agent A starts editing apply_discount, leaves it UNCOMMITTED.
    t_a_edit = time.perf_counter()
    (wtA / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return total * (1 - pct / 100.0) + 0.5  # A: fee")
    )
    wip_syms_a, diff_a = worktree_wip_symbols(wtA, "util.py")
    t_scan1 = time.perf_counter()
    assert wip_syms_a == {"apply_discount"}, wip_syms_a

    # Scan 1: no peer change yet -> no warning (no counterpart).
    peer_syms_b, diff_b = set(), ""
    warnings_1 = []
    if wip_syms_a & peer_syms_b:
        warnings_1.append("unexpected")

    # t1: agent B commits an overlapping apply_discount change.
    t_b_commit = time.perf_counter()
    (wtB / "util.py").write_text(
        make_util_py().replace("return total * (1 - pct / 100.0)",
                               "return round(total * (1 - pct / 100.0), 2)  # B: rounding")
    )
    commit_all(wtB, "B: round discounted total")
    t_b_done = time.perf_counter()
    peer_syms_b, diff_b = commit_symbols(wtB, base_sha, "util.py")
    heads = [must(wtA, "rev-parse", "HEAD"), must(wtB, "rev-parse", "HEAD")]

    # Scan 2: overlap exists while A's change is still UNCOMMITTED -> emit.
    t_scan2 = time.perf_counter()
    emitted = []
    if wip_syms_a & peer_syms_b:
        emitted.append(emit_warning(
            run_id="fixture-overlap-001", base_sha=base_sha, heads=heads,
            failing=True, oracle_id="symbol-overlap-wip-v0",
            tdigest=digest(diff_a, diff_b),
            wip_kind="uncommitted_diff",
            artifact_ref=f"wtA:util.py@{digest(diff_a)[:12]}",
        ))
    t_emit = time.perf_counter()

    # A keeps working (simulated think/edit time), THEN commits.
    time.sleep(0.4)
    t_a_commit = time.perf_counter()
    commit_all(wtA, "A: add fee")
    t_a_done = time.perf_counter()

    # Completed-change-only oracle (STALE-style) first sees A's change here.
    completed_oracle_available_at = t_a_commit

    # Merge-matrix cost at completion, for contrast (not the availability point).
    # A and B edited the same region, so a textual conflict here is expected;
    # the completed-change path pays this conflict only at commit time.
    t_mt = time.perf_counter()
    mt = git(repo, "merge-tree", "--write-tree", "agentA", "agentB")
    merge_tree_ms = (time.perf_counter() - t_mt) * 1000

    return {
        "scenario": "overlap_uncommitted",
        "warning_emitted_before_agent_commit": t_emit < t_a_commit,
        "wip_margin_to_commit_ms": round((t_a_commit - t_emit) * 1000, 1),
        "completed_change_oracle_margin_ms": round((t_a_commit - completed_oracle_available_at) * 1000, 1),
        "warning_lead_over_completed_oracle_ms": round((t_a_commit - t_emit) * 1000, 1),
        "scan_latency_ms": {
            "scan1_wip_only": round((t_scan1 - t_a_edit) * 1000, 2),
            "scan2_with_peer_head": round((t_emit - t_scan2) * 1000, 2),
            "b_commit_step_ms": round((t_b_done - t_b_commit) * 1000, 2),
            "a_commit_step_ms": round((t_a_done - t_a_commit) * 1000, 2),
        },
        "merge_tree_at_completion_ms": round(merge_tree_ms, 2),
        "merge_tree_at_completion_rc": mt.returncode,
        "emitted_schema_conformant": bool(emitted) and set(emitted[0]) == {
            "warning_id", "run_id", "base_sha", "head_vector", "pair", "failing",
            "oracle_id", "test_digest", "ts_emitted", "generation", "wip_basis"},
        "emitted": emitted,
    }


def scenario_no_overlap(base_tmp):
    """Disjoint symbol sets -> no warning (precision control)."""
    repo = base_tmp / "nooverlap"
    init_repo(repo)
    (repo / "util.py").write_text(make_util_py())
    base_sha = commit_all(repo, "base")
    must(repo, "worktree", "add", "-q", "-b", "agentA", str(base_tmp / "wtA2"))
    must(repo, "worktree", "add", "-q", "-b", "agentB", str(base_tmp / "wtB2"))
    wtA, wtB = base_tmp / "wtA2", base_tmp / "wtB2"

    (wtA / "util.py").write_text(
        make_util_py().replace("return f'total={total:.2f}'",
                               "return f'RECEIPT total={total:.2f}'  # A: receipt only")
    )
    (wtB / "util.py").write_text(
        make_util_py().replace("return sum(i['price'] for i in items)",
                               "return sum(i['price'] for i in items)  # B: total only")
    )
    commit_all(wtB, "B: calc_total tweak")
    wip_a, diff_a = worktree_wip_symbols(wtA, "util.py")
    syms_b, diff_b = commit_symbols(wtB, base_sha, "util.py")
    overlap = wip_a & syms_b
    emitted = bool(overlap)
    return {
        "scenario": "disjoint_symbols",
        "wip_symbols": sorted(wip_a),
        "peer_symbols": sorted(syms_b),
        "warning_emitted": emitted,
        "expected": False,
        "pass": emitted is False,
    }


def scan_cost_bounds(base_tmp, n_files=4000, file_bytes=1500):
    """Cold/warm git diff and status wall times on a 4k-file tree."""
    repo = base_tmp / "scale"
    init_repo(repo)
    filler = repo / "pkg"
    filler.mkdir()
    blob = "".join(f"{i:06x} " + os.urandom(24).hex() * 22 + "\n" for i in range(22))
    for i in range(n_files):
        (filler / f"mod_{i:04d}.py").write_text(blob)
    base_sha = commit_all(repo, "base")
    must(repo, "worktree", "add", "-q", "-b", "agentA", str(base_tmp / "wtS"))
    wt = base_tmp / "wtS"
    # one real WIP edit so diff has content to report
    (wt / "pkg" / "mod_0000.py").write_text(blob + "# WIP edit\n")

    def touch_all():
        for p in wt.rglob("*.py"):
            os.utime(p, None)

    timings = {}
    touch_all()
    t0 = time.perf_counter(); must(wt, "diff", "--name-only", "HEAD")
    timings["diff_cold_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    t0 = time.perf_counter(); must(wt, "diff", "--name-only", "HEAD")
    timings["diff_warm_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    touch_all()
    t0 = time.perf_counter(); must(wt, "status", "--porcelain")
    timings["status_cold_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    t0 = time.perf_counter(); must(wt, "status", "--porcelain")
    timings["status_warm_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    du = subprocess.run(["du", "-sm", str(wt)], capture_output=True, text=True)
    return {
        "scenario": "scan_cost_bounds",
        "n_files": n_files,
        "worktree_mb": du.stdout.split()[0],
        "base_sha": base_sha[:12],
        "timings_ms": timings,
        "note": SCAN_MS_BUDGET_NOTE,
    }


def main():
    git_version = git(".", "--version").stdout.strip()
    t_start = time.perf_counter()
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="zc_wip_feas_") as tmp:
        base = Path(tmp)
        overlap = scenario_overlap(base)
        no_overlap = scenario_no_overlap(base)
        scale = scan_cost_bounds(base)
    wall_s = round(time.perf_counter() - t_start, 1)

    checks = {
        "wip_warning_fires_before_commit": overlap["warning_emitted_before_agent_commit"],
        "schema_conformant_emit": overlap["emitted_schema_conformant"],
        "no_false_positive_disjoint": no_overlap["pass"],
        "cold_diff_under_2s_at_4k_files": scale["timings_ms"]["diff_cold_ms"] < 2000,
    }
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runner": "zcode-independent (aplexer d54c1e11)",
        "purpose": "local feasibility for a01-uptake-protocol.md rev 2 unfinished-WIP constraint; NOT the R2-1/Y1 kill test",
        "git_version": git_version,
        "wall_seconds": wall_s,
        "scenarios": {"overlap": overlap, "no_overlap": no_overlap, "scale": scale},
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({k: results[k] for k in
                      ("timestamp", "git_version", "wall_seconds", "checks", "all_checks_pass")}, indent=2))
    print(f"\noverlap margin: WIP warning led agent-commit by "
          f"{overlap['warning_lead_over_completed_oracle_ms']} ms; "
          f"completed-change-only oracle available only at commit (+{overlap['merge_tree_at_completion_ms']} ms merge-tree)")
    print(f"scale@{scale['n_files']} files ({scale['worktree_mb']} MB): {scale['timings_ms']}")
    print(f"results: {RESULTS_PATH}")
    return 0 if results["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
