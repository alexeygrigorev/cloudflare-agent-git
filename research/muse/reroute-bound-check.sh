#!/usr/bin/env bash
# Live bound-session reply-reroute check (Muse independent path).
# A(tag mover) sends to B; A dies; C reuses tag mover; B replies to A's
# message from inside its workload. Expect: to.session_id == C, rerouted_from == A.
set -euo pipefail

BIN="${APLEXER_BIN:-/home/alexey/git/aplexer-wt/shared-target/debug/aplexer}"
[ -x "$BIN" ] || { echo "ERROR: binary not executable: $BIN" >&2; exit 1; }

unset APLEXER_SESSION_ID APLEXER_WORKSPACE APLEXER_TAG
SCRATCH=$(mktemp -d /tmp/muse-reroute-XXXXXX)
cleanup() {
    "$BIN" kill "$SCRATCH:mover" 2>/dev/null || true
    "$BIN" kill "$SCRATCH:responder" 2>/dev/null || true
    rm -rf "$SCRATCH"
}
trap cleanup EXIT

run_in_session() {
    local sel="$1" cmd="$2" done_file="$SCRATCH/done_$RANDOM$RANDOM"
    "$BIN" send "$sel" "$cmd; echo __DONE__ > '$done_file'" --enter
    local waited=0
    while [ ! -f "$done_file" ]; do
        sleep 0.2; waited=$((waited + 1))
        [ "$waited" -ge 100 ] && { echo "FAIL: timeout in $sel" >&2; return 1; }
    done
    rm -f "$done_file"
}

"$BIN" start --engine shell --workspace "$SCRATCH" --tag mover > /dev/null
"$BIN" start --engine shell --workspace "$SCRATCH" --tag responder > /dev/null
sleep 2

run_in_session "$SCRATCH:mover" "$BIN whoami --json > '$SCRATCH/whoami-a.json'"
ID_A=$(jq -r '.id' "$SCRATCH/whoami-a.json")
echo "holder A: $ID_A"

run_in_session "$SCRATCH:mover" \
  "$BIN message send --to responder --json 'reroute probe' > '$SCRATCH/msg.json' 2>'$SCRATCH/msg.err'"
MSG=$(jq -r '.id' "$SCRATCH/msg.json")
[ -n "$MSG" ] && [ "$MSG" != "null" ] || { echo "FAIL: send"; cat "$SCRATCH/msg.err" >&2; exit 1; }
echo "message: $MSG"

"$BIN" kill "$SCRATCH:mover" > /dev/null
echo "waiting for killed holder record to clear (kill grace)..."
settled=0
for _ in $(seq 1 60); do
    if ! "$BIN" list --json 2>/dev/null | python3 -c "import json,sys; sys.exit(0 if any(r.get('tag')=='mover' and r.get('workspace')=='$SCRATCH' for r in json.load(sys.stdin)) else 1)"; then settled=1; break; fi
    sleep 0.5
done
[ "$settled" = 1 ] || { echo "FAIL: mover record never cleared" >&2; exit 1; }
sleep 1
"$BIN" start --engine shell --workspace "$SCRATCH" --tag mover > /dev/null
sleep 2
run_in_session "$SCRATCH:mover" "$BIN whoami --json > '$SCRATCH/whoami-c.json'"
ID_C=$(jq -r '.id' "$SCRATCH/whoami-c.json")
[ "$ID_C" != "$ID_A" ] || { echo "FAIL: restart kept UUID" >&2; exit 1; }
echo "holder C: $ID_C (fresh)"

run_in_session "$SCRATCH:responder" \
  "$BIN message reply --json '$MSG' 'reroute reply' > '$SCRATCH/reply.json' 2>'$SCRATCH/reply.err'"
TO_SID=$(jq -r '.to.session_id' "$SCRATCH/reply.json")
REROUTED=$(jq -r '.to.rerouted_from' "$SCRATCH/reply.json")
[ "$TO_SID" = "$ID_C" ] || { echo "FAIL: to.session_id=$TO_SID, want $ID_C" >&2; exit 1; }
[ "$REROUTED" = "$ID_A" ] || { echo "FAIL: rerouted_from=$REROUTED, want $ID_A" >&2; exit 1; }
grep -q "rerouted" "$SCRATCH/reply.err" || { echo "FAIL: no reroute warning on stderr" >&2; exit 1; }
echo "PASS reroute: to=$TO_SID rerouted_from=$REROUTED + stderr warning"
echo "=== LIVE REROUTE CHECK BEHAVES AS SPECIFIED ==="
