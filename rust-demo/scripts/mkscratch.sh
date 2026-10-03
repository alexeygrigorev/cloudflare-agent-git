#!/usr/bin/env bash
# Materialize a standalone tiny git repo holding the base crate, extracted
# from the committed state of the rust-demo worktree. Idempotent: wipes and
# rebuilds rust-demo/.harness/scratch each run.
# Usage: mkscratch.sh  → prints path of the fresh repo on stdout.
set -euo pipefail

DEMO="$(cd "$(dirname "$0")/.." && pwd)"        # .../rust-demo
WT="$(cd "$DEMO/.." && pwd)"                    # proto/rust-demo worktree
SCRATCH="$DEMO/.harness/scratch"
REPO="$SCRATCH/repo"

test -d "$WT/rust-demo/crate/src" || { echo "FATAL: $WT/rust-demo/crate missing" >&2; exit 1; }

rm -rf "$SCRATCH"
mkdir -p "$REPO"
git -C "$WT" archive HEAD:rust-demo/crate | tar -x -C "$REPO"
git -C "$REPO" init -q -b main
git -C "$REPO" add -A
git -C "$REPO" -c user.name=zc-rust-lane -c user.email=zc-rust-lane@agents.local \
    commit -q -m "base: shortlinks crate (imported from proto/rust-demo)"
printf '%s\n' "$REPO"
