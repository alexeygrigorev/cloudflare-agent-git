#!/usr/bin/env bash
# A/B benchmark of the user's Rust-worktree pain, small scale (N=3 agent
# worktrees, zero-dep demo crate). Two modes:
#
#   (a) NAIVE:                 each worktree gets its own cold
#                              CARGO_TARGET_DIR; all 3 `cargo test --jobs 2`
#                              run in parallel (no admission control).
#   (b) AGENT BRANCHES MODE:   ONE shared warm target prebuilt once for the
#                              base commit; jobs admitted under a RAM budget
#                              (max 2 concurrent, MemAvailable >= 10 GiB).
#
# Measured per mode: total target bytes (du -sb), peak RSS (per-process via
# /usr/bin/time -v AND workload-cgroup memory.peak), batch wall time,
# incremental rebuild wall time after one small edit (MAX_LINKS const).
# Raw numbers -> bench/results.json; human summary -> bench/README.md.
# No extrapolation beyond what is measured here.
#
# Safety: every cargo run is wrapped by scripts/guard/build_guard.py
# (growth cap 1024 MB, disk floor 50 GB, timeout 300 s), cargo -j 2, and a
# 10 GiB MemAvailable preflight/launch gate. CARGO_TARGET_DIRs live only
# inside rust-demo/. Idempotent: bench/run/ is wiped and rebuilt each run.
set -uo pipefail

DEMO="$(cd "$(dirname "$0")/.." && pwd)"
WT="$(cd "$DEMO/.." && pwd)"
MAIN_REPO="/home/alexey/git/cloudflare-agent-git"
GUARD="$MAIN_REPO/scripts/guard/build_guard.py"
RUN="$DEMO/bench/run"

MEM_MIN_KB=$((10 * 1048576))   # 10 GiB, meminfo units (kB)
GROWTH_MB=1024
FREE_MB=51200                  # 50 GB disk floor
N=3

die() { echo "BENCH_ABORT: $*" >&2; exit 44; }
mem_avail_kb() { awk '/MemAvailable/ {print $2}' /proc/meminfo; }
mem_gate() { [ "$(mem_avail_kb)" -ge "$MEM_MIN_KB" ]; }
disk_free_mb() { df -Pm "$DEMO" | awk 'NR==2 {print $4}'; }
now_s() { date +%s.%N; }

# ---- preflight gates ----------------------------------------------------
mem_gate || die "MemAvailable $(mem_avail_kb) kB < ${MEM_MIN_KB} kB"
[ "$(disk_free_mb)" -ge "$FREE_MB" ] || die "disk free $(disk_free_mb) MB < ${FREE_MB} MB"

CGREL="$(awk -F: '$1=="0" {print $3}' /proc/self/cgroup)"
CGPATH="/sys/fs/cgroup${CGREL}"
cgroup_peak_kb() { cat "$CGPATH/memory.peak" 2>/dev/null || echo NA; }
cgroup_reset() { echo reset > "$CGPATH/memory.peak" 2>/dev/null || return 1; }

# ---- fresh scratch repo + N worktrees per mode --------------------------
rm -rf "$RUN"
mkdir -p "$RUN"
REPO="$RUN/repo"
mkdir -p "$REPO"
git -C "$WT" archive HEAD:rust-demo/crate | tar -x -C "$REPO"
git -C "$REPO" init -q -b main
git -C "$REPO" add -A
git -C "$REPO" -c user.name=zc-rust-lane -c user.email=zc-rust-lane@agents.local \
    commit -q -m "base: shortlinks crate"
for i in $(seq 1 "$N"); do
    git -C "$REPO" worktree add -q --detach "$RUN/naive/wt-$i" main
    git -C "$REPO" worktree add -q --detach "$RUN/shared/wt-$i" main
done

# ---- one guarded, time'd cargo test -------------------------------------
# run_job <cwd> <target_dir> <tag>
run_job() {
    local cwd="$1" target="$2" tag="$3"
    ( cd "$cwd" && /usr/bin/time -v -o "$RUN/$tag.time" env CARGO_TARGET_DIR="$target" \
        python3 "$GUARD" --max-growth-mb "$GROWTH_MB" --min-free-mb "$FREE_MB" --timeout 300 \
        "$target" cargo test --jobs 2 ) \
        > "$RUN/$tag.out" 2> "$RUN/$tag.err"
    echo $? > "$RUN/$tag.rc"
}

# launch_admitted <cwd> <target_dir> <tag>  → background job; pid in $LAUNCHED_PID
LAUNCHED_PID=
launch_admitted() {
    local tries=0
    while ! mem_gate; do
        tries=$((tries + 1))
        if [ "$tries" -gt 120 ]; then die "RAM budget: MemAvailable < 10 GiB for 120 s"; fi
        sleep 1
    done
    run_job "$@" &
    LAUNCHED_PID=$!
}

du_bytes() { du -sb "$1" 2>/dev/null | awk '{print $1}' || echo 0; }

record_du() { # <tag> <target_dir>
    echo "$(du_bytes "$2")" > "$RUN/$1.du"
}

# ==========================================================================
# MODE A: NAIVE — private cold targets, all N jobs in parallel
# ==========================================================================
cgroup_reset || echo "note: cgroup memory.peak not resettable; peak covers prior activity" > "$RUN/cgroup-peak-caveat"
t0=$(now_s)
pids_a=()
for i in $(seq 1 "$N"); do
    run_job "$RUN/naive/wt-$i" "$RUN/naive/wt-$i/target" "naive-j$i" &
    pids_a+=($!)
done
for p in "${pids_a[@]}"; do wait "$p"; done
t1=$(now_s)
echo "$(python3 -c "print(f'{$t1-$t0:.3f}')")" > "$RUN/WALL_NAIVE"
echo "$(cgroup_peak_kb)" > "$RUN/CGPEAK_NAIVE_BYTES"
for i in $(seq 1 "$N"); do record_du "naive-j$i-target" "$RUN/naive/wt-$i/target"; done

# incremental rebuild, mode A: one small edit in wt-1, rerun
sed -i 's/pub const MAX_LINKS: usize = 10_000;/pub const MAX_LINKS: usize = 20_000;/' \
    "$RUN/naive/wt-1/src/lib.rs"
t0=$(now_s)
run_job "$RUN/naive/wt-1" "$RUN/naive/wt-1/target" "naive-incr"
t1=$(now_s)
echo "$(python3 -c "print(f'{$t1-$t0:.3f}')")" > "$RUN/WALL_NAIVE_INCR"
record_du "naive-incr-target" "$RUN/naive/wt-1/target"

# ==========================================================================
# MODE B: AGENT BRANCHES — one shared warm target, RAM-budget admission
# ==========================================================================
cgroup_reset || true
WARM="$RUN/shared/warm-target"
t0=$(now_s)
run_job "$RUN/shared/wt-1" "$WARM" "shared-prewarm"
t1=$(now_s)
echo "$(python3 -c "print(f'{$t1-$t0:.3f}')")" > "$RUN/WALL_PREWARM"
record_du "shared-prewarm" "$WARM"

t0=$(now_s)
launch_admitted "$RUN/shared/wt-1" "$WARM" "shared-j1"; p1=$LAUNCHED_PID
launch_admitted "$RUN/shared/wt-2" "$WARM" "shared-j2"; p2=$LAUNCHED_PID
wait "$p1"
launch_admitted "$RUN/shared/wt-3" "$WARM" "shared-j3"; p3=$LAUNCHED_PID   # slot freed, mem-gated
wait "$p2"
wait "$p3"
t1=$(now_s)
echo "$(python3 -c "print(f'{$t1-$t0:.3f}')")" > "$RUN/WALL_SHARED"
echo "$(cgroup_peak_kb)" > "$RUN/CGPEAK_SHARED_BYTES"
record_du "shared-total" "$WARM"

# incremental rebuild, mode B: same one-line edit, shared warm target
sed -i 's/pub const MAX_LINKS: usize = 10_000;/pub const MAX_LINKS: usize = 20_000;/' \
    "$RUN/shared/wt-1/src/lib.rs"
t0=$(now_s)
run_job "$RUN/shared/wt-1" "$WARM" "shared-incr"
t1=$(now_s)
echo "$(python3 -c "print(f'{$t1-$t0:.3f}')")" > "$RUN/WALL_SHARED_INCR"
record_du "shared-incr" "$WARM"

# ---- assemble results.json + README.md ----------------------------------
python3 - "$RUN" "$DEMO" "$CGPATH" <<'PYEOF'
import json, re, subprocess, sys
from pathlib import Path

run, demo, cgpath = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]

def rd(name):
    p = run / name
    return p.read_text().strip() if p.exists() else None

def job(tag, target_du_tag=None):
    time_txt = rd(f"{tag}.time") or ""
    err = rd(f"{tag}.err") or ""
    m_rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", time_txt)
    m_wall = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (\S+)", time_txt)
    m_guard = re.search(r"GUARD_(SUCCESS|FAIL|TERMINATED)[^\n]*", err)
    return {
        "tag": tag,
        "exit_code": rd(f"{tag}.rc"),
        "target_bytes": int(rd(f"{target_du_tag or tag}.du") or 0),
        "time_v_max_rss_kb": int(m_rss.group(1)) if m_rss else None,
        "time_v_wall": m_wall.group(1) if m_wall else None,
        "guard_line": m_guard.group(0) if m_guard else None,
    }

def meminfo():
    d = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        if k in ("MemTotal", "MemAvailable"):
            d[k] = int(v.strip().split()[0]) * 1024
    return d

cargo = subprocess.run(["cargo", "--version"], capture_output=True, text=True).stdout.strip()
rustc = subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip()
kernel = open("/proc/sys/kernel/osrelease").read().strip()

# all target dirs currently inside rust-demo (the <=3GB budget)
def is_target(p):
    return p.is_dir() and (p.name == "target" or p.name.startswith("target-") or p.name == "warm-target")
targets = sorted(p for p in demo.rglob("*") if is_target(p) and ".harness/scratch" not in p.parts or p.is_dir() and (p.name == "target" or p.name.startswith("target-") or p.name == "warm-target") and ".harness/scratch" not in p.parts)
per_target = {str(p.relative_to(demo)): int(subprocess.run(["du", "-sb", str(p)], capture_output=True, text=True).stdout.split()[0]) for p in targets}
targets_total = sum(per_target.values())

naive_jobs = [job(f"naive-j{i}", f"naive-j{i}-target") for i in (1, 2, 3)]
naive_targets_bytes = sum(j["target_bytes"] for j in naive_jobs)
shared_jobs = [job(f"shared-j{i}") for i in (1, 2, 3)]
prewarm = job("shared-prewarm", "shared-prewarm")

res = {
    "as_of": subprocess.run(["date", "-Is"], capture_output=True, text=True).stdout.strip(),
    "subject": "N=3 agent worktrees each running `cargo test`, zero-dep demo crate `shortlinks`",
    "host": {
        "kernel": kernel, "cargo": cargo, "rustc": rustc,
        "mem_total_bytes": meminfo()["MemTotal"],
        "mem_available_bytes_end": meminfo()["MemAvailable"],
        "workload_cgroup": cgpath,
        "admission_rule": "max 2 concurrent jobs, launch only when MemAvailable >= 10 GiB",
        "guard": "scripts/guard/build_guard.py --max-growth-mb 1024 --min-free-mb 51200 --timeout 300",
        "cargo_jobs_flag": "--jobs 2",
    },
    "mode_a_naive": {
        "description": "private cold CARGO_TARGET_DIR per worktree, 3 cargo test in parallel",
        "batch_wall_s": float(rd("WALL_NAIVE")),
        "peak_cgroup_bytes_since_cgroup_creation": rd("CGPEAK_NAIVE_BYTES"),
        "sum_job_max_rss_kb_upper_bound": sum(j["time_v_max_rss_kb"] or 0 for j in naive_jobs),
        "targets_total_bytes": naive_targets_bytes,
        "jobs": naive_jobs,
        "incremental_after_small_edit": {
            "edit": "MAX_LINKS 10_000 -> 20_000 in src/lib.rs (wt-1)",
            "wall_s": float(rd("WALL_NAIVE_INCR")),
            "target_bytes_after": int(rd("naive-incr-target.du") or 0),
            "job": job("naive-incr", "naive-incr-target"),
        },
    },
    "mode_b_agent_branches": {
        "description": "one shared warm CARGO_TARGET_DIR for the base commit; jobs admitted max 2 concurrent under 10 GiB MemAvailable budget",
        "prewarm": {"wall_s": float(rd("WALL_PREWARM")), "target_bytes_after": int(rd("shared-prewarm.du") or 0), "job": prewarm},
        "batch_wall_s": float(rd("WALL_SHARED")),
        "total_wall_s": float(rd("WALL_PREWARM")) + float(rd("WALL_SHARED")),
        "peak_cgroup_bytes_since_cgroup_creation": rd("CGPEAK_SHARED_BYTES"),
        "sum_job_max_rss_kb_upper_bound": sum(j["time_v_max_rss_kb"] or 0 for j in shared_jobs),
        "shared_target_bytes": int(rd("shared-total.du") or 0),
        "jobs": shared_jobs,
        "incremental_after_small_edit": {
            "edit": "MAX_LINKS 10_000 -> 20_000 in src/lib.rs (wt-1)",
            "wall_s": float(rd("WALL_SHARED_INCR")),
            "target_bytes_after": int(rd("shared-incr.du") or 0),
            "job": job("shared-incr", "shared-incr"),
        },
    },
    "target_dirs_inside_rustdemo": {"per_dir_bytes": per_target, "total_bytes": targets_total, "budget_bytes": 3 * 1024**3},
    "caveats": [
        "Zero-dependency crate: absolute numbers are small; only mode-vs-mode ratios are meaningful here.",
    "Single run on a shared desktop host: small wall-time differences are noise (batch wall varied 0.87-1.33 s for naive across runs).",
    "Target-dir budget inventory (target_dirs_inside_rustdemo) excludes transient .harness/scratch verify targets, which are rebuilt per verify-overlap run.",
        "cargo file-locks the shared build dir: mode-B jobs serialize on cargo's own lock even though up to 2 are admitted; observed wall time reflects that.",
        "kernel 6.8 cannot reset memory.peak, so cgroup readings are monotonic since cgroup creation and NOT comparable between modes; per-mode comparison uses /usr/bin/time -v max-RSS (per job process tree) and its honest upper-bound sum.",
        "No extrapolation beyond measured numbers.",
    ],
}
(demo / "bench" / "results.json").write_text(json.dumps(res, indent=2) + "\n")

def kib(x): return f"{int(x)/1024:.1f}"

r = res
lines = []
A = r["mode_a_naive"]; B = r["mode_b_agent_branches"]
lines += [
    "# bench: NAIVE vs AGENT BRANCHES MODE (N=3 worktrees, `cargo test`)",
    "",
    f"As of: {r['as_of']}.  Host: {r['host']['kernel']}, {r['host']['cargo']}, {r['host']['rustc']}.",
    "Raw numbers (du -sb bytes, /usr/bin/time -v + workload-cgroup memory.peak, wall clock);",
    "every cargo run wrapped by build_guard.py, `-j 2`, mode-B admission: max 2 concurrent, MemAvailable >= 10 GiB.",
    "",
    "| metric | (a) NAIVE: 3 private cold targets | (b) AGENT BRANCHES: one shared warm target |",
    "|---|---|---|",
    f"| target bytes after batch (du -sb) | {A['targets_total_bytes']:,} | {B['shared_target_bytes']:,} |",
    f"| batch wall time (s) | {A['batch_wall_s']} | {B['batch_wall_s']} (prewarm {B['prewarm']['wall_s']} s, total {B['total_wall_s']} s) |",
    f"| per-job max-RSS sum, upper bound of concurrent total (KiB) | {A['sum_job_max_rss_kb_upper_bound']} | {B['sum_job_max_rss_kb_upper_bound']} |",
    f"| per-job max RSS (KiB, time -v) | {', '.join(str(j['time_v_max_rss_kb']) for j in A['jobs'])} | {', '.join(str(j['time_v_max_rss_kb']) for j in B['jobs'])} |",
    f"| incremental rebuild after 1-line edit (s) | {A['incremental_after_small_edit']['wall_s']} | {B['incremental_after_small_edit']['wall_s']} |",
    "",
    "Per-job exit codes: "
    f"naive {[j['exit_code'] for j in A['jobs']]}, shared {[j['exit_code'] for j in B['jobs']]} "
    f"(0 = cargo test green under guard).",
    "",
    "## What this shows at this scale",
    "",
    f"- Disk: naive keeps {A['targets_total_bytes']:,} target bytes vs {B['shared_target_bytes']:,} shared "
    f"({A['targets_total_bytes']/B['shared_target_bytes']:.1f}x) - the worktree-per-agent target duplication the user feels.",
    f"- Concurrent compile memory: naive per-job max-RSS sums to {A['sum_job_max_rss_kb_upper_bound']} KiB upper bound vs "
    f"{B['sum_job_max_rss_kb_upper_bound']} KiB for shared admitted jobs (cargo's own lock additionally serializes mode B).",
    f"- Wall time at N=3 on a zero-dep crate: naive batch {A['batch_wall_s']} s vs shared total {B['total_wall_s']} s "
    f"(prewarm {B['prewarm']['wall_s']} s included) - at THIS scale naive is not slower; the user's real fleets have heavier dep graphs and N>>3, where cold-target duplication and parallel rustc RAM dominate. No extrapolation is claimed.",
    "",
    "## Caveats",
    "",
]
lines += [f"- {c}" for c in r["caveats"]]
lines += [
    "",
    "Raw JSON: `results.json` (same directory). Reproduce: `bash rust-demo/bench/run_bench.sh`.",
    "",
]
(demo / "bench" / "README.md").write_text("\n".join(lines))
print("results.json + README.md written")
PYEOF
rc=$?
[ "$rc" -eq 0 ] || die "results assembly failed"
echo "BENCH_DONE"
