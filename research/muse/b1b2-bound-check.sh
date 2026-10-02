#!/usr/bin/env bash
# B1/B2 behavioral boundary checks for aplexer idempotency (Muse independent path).
# B1 tag-reuse: killed holder's tag reused by a new session; replay of the same
#     key must return the STALE original id (documented logical-identity semantic).
# B2 post-GC/quota: after the original is evicted past retention caps, replay of
#     the same key must mint a NEW id (duplicate-delivery boundary).
# All identity-sensitive sends originate inside bound workloads via `aplexer send`
# (spawn-stamped identity). Filler traffic likewise runs inside a worker PTY.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${APLEXER_BIN:-/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer}"
[ -x "$BIN" ] || { echo "ERROR: binary not executable: $BIN" >&2; exit 1; }

unset APLEXER_SESSION_ID APLEXER_WORKSPACE APLEXER_TAG
SCRATCH=$(mktemp -d /tmp/muse-b1b2-XXXXXX)
cleanup() {
    "$BIN" kill "$SCRATCH:b1a" 2>/dev/null || true
    "$BIN" kill "$SCRATCH:b1b" 2>/dev/null || true
    "$BIN" kill "$SCRATCH:b2a" 2>/dev/null || true
    "$BIN" kill "$SCRATCH:b2b" 2>/dev/null || true
    rm -rf "$SCRATCH"
}
trap cleanup EXIT

run_in_session() {
    local sel="$1" cmd="$2" done_file="$SCRATCH/done_$RANDOM$RANDOM"
    "$BIN" send "$sel" "$cmd; echo __DONE__ > '$done_file'" --enter
    local waited=0
    while [ ! -f "$done_file" ]; do
        sleep 0.2; waited=$((waited + 1))
        [ "$waited" -ge 100 ] && { echo "FAIL: timeout in $sel: $cmd" >&2; return 1; }
    done
    rm -f "$done_file"
}

echo "=== B1 setup ==="
"$BIN" start --engine shell --workspace "$SCRATCH" --tag b1a > /dev/null
"$BIN" start --engine shell --workspace "$SCRATCH" --tag b1b > /dev/null
sleep 2

echo "=== B1: holder A sends K1 ==="
run_in_session "$SCRATCH:b1a" \
  "$BIN message send --to b1b --idempotency-key key-reuse-1 --json 'reuse payload' > '$SCRATCH/b1_orig.json' 2>'$SCRATCH/b1_orig.err'"
ID_ORIG=$(jq -r '.id' "$SCRATCH/b1_orig.json")
[ -n "$ID_ORIG" ] && [ "$ID_ORIG" != "null" ] || { echo "FAIL: B1 original send"; cat "$SCRATCH/b1_orig.err" >&2; exit 1; }
echo "original id: $ID_ORIG"

echo "=== B1: kill A, new session C reuses tag b1a ==="
"$BIN" kill "$SCRATCH:b1a" > /dev/null
sleep 1
"$BIN" start --engine shell --workspace "$SCRATCH" --tag b1a > /dev/null
sleep 2
run_in_session "$SCRATCH:b1a" \
  "$BIN message send --to b1b --idempotency-key key-reuse-1 --json 'reuse payload' > '$SCRATCH/b1_replay.json' 2>'$SCRATCH/b1_replay.err'"
ID_REPLAY=$(jq -r '.id' "$SCRATCH/b1_replay.json")
[ "$ID_REPLAY" = "$ID_ORIG" ] || { echo "FAIL: B1 expected stale-id inheritance, got $ID_REPLAY vs $ID_ORIG" >&2; exit 1; }
echo "PASS B1: reused-tag replay inherits stale id ($ID_REPLAY == $ID_ORIG)"

echo "=== B2 setup ==="
"$BIN" start --engine shell --workspace "$SCRATCH" --tag b2a > /dev/null
"$BIN" start --engine shell --workspace "$SCRATCH" --tag b2b > /dev/null
sleep 2

echo "=== B2: A sends K2, record ID1 ==="
run_in_session "$SCRATCH:b2a" \
  "$BIN message send --to b2b --idempotency-key key-gc-1 --json 'gc boundary payload' > '$SCRATCH/b2_orig.json' 2>'$SCRATCH/b2_orig.err'"
ID1=$(jq -r '.id' "$SCRATCH/b2_orig.json")
[ -n "$ID1" ] && [ "$ID1" != "null" ] || { echo "FAIL: B2 original send"; cat "$SCRATCH/b2_orig.err" >&2; exit 1; }
echo "original id: $ID1"

echo "=== B2: filler traffic past the 10MiB workspace cap (inside B workload) ==="
run_in_session "$SCRATCH:b2b" \
  "for i in \$(seq 1 175); do P=\$(head -c 60000 /dev/urandom | base64 | head -c 60000); $BIN message send --to b2a \"\$P\" >/dev/null 2>&1 || echo FILLFAIL\$i; done; echo fill-done"
echo "filler done"

echo "=== B2: original must be evicted (checked from inside B workload) ==="
run_in_session "$SCRATCH:b2b" \
  "$BIN message show --json '$ID1' >'$SCRATCH/b2_show.txt' 2>&1; echo SHOW_RC=\$? >'$SCRATCH/b2_show_rc.txt'"
if grep -q "SHOW_RC=0" "$SCRATCH/b2_show_rc.txt"; then
    echo "NOTE B2: original survived quota pressure (cap not exceeded?) — cannot prove post-GC mint"
    exit 2
fi
echo "original evicted (show fails as expected)"

echo "=== B2: replay K2 must mint a NEW id ==="
run_in_session "$SCRATCH:b2a" \
  "$BIN message send --to b2b --idempotency-key key-gc-1 --json 'gc boundary payload' > '$SCRATCH/b2_replay.json' 2>'$SCRATCH/b2_replay.err'"
ID2=$(jq -r '.id' "$SCRATCH/b2_replay.json")
[ -n "$ID2" ] && [ "$ID2" != "null" ] || { echo "FAIL: B2 replay send failed"; cat "$SCRATCH/b2_replay.err" >&2; exit 1; }
[ "$ID2" != "$ID1" ] || { echo "FAIL: B2 replay wrongly deduplicated to evicted id" >&2; exit 1; }
echo "PASS B2: post-eviction replay mints new id ($ID2 != $ID1)"
echo "=== ALL B1/B2 BOUNDARY CHECKS BEHAVE AS DOCUMENTED ==="
