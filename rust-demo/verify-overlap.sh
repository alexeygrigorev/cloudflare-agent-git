#!/usr/bin/env bash
# Prove the three overlap facts for the rust-demo TASKS.md tasks, from the
# reference patches in rust-demo/.harness/patches/:
#
#   fact 1: T1+T2 → git textual conflict (same function rewritten in lib.rs)
#   fact 2: T2+T3 → git merge is CLEAN, but `cargo test` breaks to compile
#           (T3's new caller still uses the pre-T2 public contract)
#   fact 3: T1, T2, T3 each pass `cargo test` on their own
#
# Idempotent: rebuilds the scratch repo via scripts/mkscratch.sh every run.
# All cargo runs are wrapped by scripts/guard/build_guard.py, use --jobs 2,
# and keep CARGO_TARGET_DIR inside rust-demo/. Exits 0 iff all facts hold.
set -uo pipefail

DEMO="$(cd "$(dirname "$0")" && pwd)"                      # .../rust-demo
MAIN_REPO="/home/alexey/git/cloudflare-agent-git"
GUARD="$MAIN_REPO/scripts/guard/build_guard.py"
SCRATCH="$DEMO/.harness/scratch"
REPO="$(bash "$DEMO/scripts/mkscratch.sh")"
REPORT="$SCRATCH/verify-report.txt"
TARGETS="$SCRATCH/verify-targets"
mkdir -p "$TARGETS"

MEM_GIB=10          # stop if MemAvailable < 10 GiB
GROWTH_MB=1024      # per-run target growth cap
FREE_MB=51200       # 50 GB disk floor (guard enforces too)

pass_all=1

mem_gate() {
    awk -v min=$((MEM_GIB * 1048576)) '/MemAvailable/ {m=$2*1024} END {exit !(m >= min)}' /proc/meminfo
}

guarded_cargo_test() { # $1 = label, $2 = workdir, $3 = targetdir
    mem_gate || { echo "MEM_GATE_FAIL: MemAvailable < ${MEM_GIB} GiB, stopping" | tee -a "$REPORT"; exit 43; }
    ( cd "$2" && CARGO_TARGET_DIR="$3" python3 "$GUARD" \
        --max-growth-mb "$GROWTH_MB" --min-free-mb "$FREE_MB" --timeout 300 \
        "$3" cargo test --jobs 2 ) 2>&1
}

append() { printf '%s\n' "$*" >> "$REPORT"; }

: > "$REPORT"
append "# verify-overlap report"
append "date: $(date -Is)"
append "repo: $REPO (base $(git -C "$REPO" rev-parse --short HEAD))"
append ""

# ---------- fact 3 (do it first: creates t1/t2/t3 reference branches) ----
append "## fact 3: each task alone is green"
for t in t1 t2 t3; do
    git -C "$REPO" checkout -q -B "$t" main
    if ! git -C "$REPO" apply --whitespace=nowarn "$DEMO/.harness/patches/$t.patch"; then
        append "FAIL $t: patch did not apply"; pass_all=0; continue
    fi
    git -C "$REPO" add -A
    git -C "$REPO" -c user.name=verify-overlap -c user.email=verify@agents.local \
        commit -q -m "$t (reference patch applied)"
    out="$(guarded_cargo_test "$t" "$REPO" "$TARGETS/$t")"
    if printf '%s' "$out" | grep -q '^GUARD_SUCCESS' \
       && printf '%s' "$out" | grep -q '^test result: ok'; then
        n="$(printf '%s' "$out" | grep -c '^test result: ok')"
        append "PASS $t alone: GUARD_SUCCESS, $n 'test result: ok' blocks"
    else
        append "FAIL $t alone: expected green cargo test"
        printf '%s\n' "$out" | grep -E 'GUARD_|error' | head -5 | while IFS= read -r l; do append "  $l"; done
        pass_all=0
    fi
done
append ""

# ---------- fact 1: T1+T2 textual conflict -------------------------------
append "## fact 1: T1+T2 merge conflict"
git -C "$REPO" checkout -q -B merge-t1-t2 "t1"
merge_err="$(git -C "$REPO" merge --no-edit t2 2>&1)"
merge_rc=$?
if [ "$merge_rc" -ne 0 ] && git -C "$REPO" diff --name-only --diff-filter=U | grep -q '^src/lib.rs$'; then
    conflicted="$(git -C "$REPO" diff --name-only --diff-filter=U | tr '\n' ' ')"
    append "PASS T1+T2: merge exited $merge_rc with unresolved path(s): $conflicted"
else
    append "FAIL T1+T2: expected a textual conflict in src/lib.rs (rc=$merge_rc)"
    pass_all=0
fi
git -C "$REPO" merge --abort >/dev/null 2>&1 || true
git -C "$REPO" checkout -q main
append ""

# ---------- fact 2: T2+T3 clean merge, broken build ----------------------
append "## fact 2: T2+T3 clean merge, cargo test breaks"
git -C "$REPO" checkout -q -B merge-t2-t3 "t2"
if git -C "$REPO" merge --no-edit t3 >/dev/null 2>&1; then
    unmerged="$(git -C "$REPO" diff --name-only --diff-filter=U | wc -l)"
    if [ "$unmerged" -eq 0 ]; then
        append "PASS T2+T3 merge: git merge exited 0, no unresolved paths"
        out="$(guarded_cargo_test "merge-t2-t3" "$REPO" "$TARGETS/merge-t2-t3")"
        if printf '%s' "$out" | grep -q '^GUARD_FAIL' && printf '%s' "$out" | grep -Eq 'error(\[|:)' ; then
            errline="$(printf '%s\n' "$out" | grep -E '^error' | head -1)"
            append "PASS T2+T3 break: merged tree fails to compile — $errline"
        else
            append "FAIL T2+T3 break: expected compile failure after clean merge"
            printf '%s\n' "$out" | grep -E 'GUARD_|test result|^error' | head -5 | while IFS= read -r l; do append "  $l"; done
            pass_all=0
        fi
    else
        append "FAIL T2+T3: merge reported unmerged paths"; pass_all=0
    fi
else
    append "FAIL T2+T3: merge itself conflicted; tasks no longer overlap as designed"; pass_all=0
fi
append ""

# ---------- summary ------------------------------------------------------
append "## summary"
if [ "$pass_all" -eq 1 ]; then
    append "ALL_FACTS_PASS"
else
    append "FACTS_FAILED"
fi

cat "$REPORT"
[ "$pass_all" -eq 1 ]
