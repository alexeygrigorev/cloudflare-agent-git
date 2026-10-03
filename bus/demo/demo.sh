#!/usr/bin/env bash
# Two-'machine' demo against one local `wrangler dev`:
#   1. bad token rejected            2. A->B delivery
#   3. offline queueing (B down while A sends)
#   4. dedup on resend (deterministic outbox id + bus duplicate receipt)
# No network beyond localhost; uses the Agent Branches node_modules (no installs).
set -euo pipefail

BUS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKER_DIR="$BUS_DIR/worker"
NODE_MODULES="${NODE_MODULES:-/home/alexey/git/agent-branches-l1/prototype/node_modules}"
PORT="${BUS_DEMO_PORT:-8791}"
URL="http://127.0.0.1:$PORT"
ALPHA_TOKEN="alpha-local-demo-token"
BETA_TOKEN="beta-local-demo-token"

WORK="$(mktemp -d /tmp/aplexer-bus-demo.XXXXXX)"
ALPHA_HOME="$WORK/alpha"; BETA_HOME="$WORK/beta"
mkdir -p "$ALPHA_HOME/.local/bus-outbox" "$BETA_HOME/.local"
INBOX="$BETA_HOME/inbox.jsonl"
WRANGLER_PID=""

cleanup() {
  if [[ -n "$WRANGLER_PID" ]]; then
    kill -TERM -- "-$WRANGLER_PID" 2>/dev/null || kill "$WRANGLER_PID" 2>/dev/null || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1" >&2; exit 1; }

bridge() { # bridge <machine> <token> <home> <max-cycles>
  python3 "$BUS_DIR/bridge/bridge.py" \
    --bus-url "$URL" --machine "$1" --token "$2" --workspace "$3" \
    --tag demo --delivery "file:$INBOX" --long-poll 1 --max-cycles "$4"
}

echo "== starting wrangler dev on $URL (work: $WORK)"
# Unique channel per run: wrangler persists DO state under worker/.wrangler between
# runs, and deterministic outbox ids legitimately dedup across runs on one channel.
CHANNEL_ID="demo-$(date +%s)-$RANDOM"
fuser -k "$PORT/tcp" 2>/dev/null || true
sleep 1
cd "$WORKER_DIR"
setsid "$NODE_MODULES/.bin/wrangler" dev --port "$PORT" --var "CHANNEL_ID:$CHANNEL_ID" \
  >"$WORK/wrangler.log" 2>&1 &
WRANGLER_PID=$!
cd - >/dev/null

ready=""
for _ in $(seq 1 90); do
  code="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $ALPHA_TOKEN" \
    "$URL/v1/messages?after=0&wait=0" || true)"
  if [[ "$code" == "200" ]]; then ready=yes; break; fi
  sleep 1
done
[[ -n "$ready" ]] || { tail -20 "$WORK/wrangler.log" >&2; fail "wrangler dev did not come up"; }

echo "== 1. bad token is rejected"
code="$(curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer wrong-token' \
  "$URL/v1/messages?after=0&wait=0")"
[[ "$code" == "401" ]] || fail "expected 401 for bad token, got $code"
pass "GET with wrong token -> 401"

echo "== 2+3. alpha sends while beta is offline; messages queue on the bus"
cat > "$ALPHA_HOME/.local/bus-outbox/m1.json" <<'JSON'
{"to": "zc-bus-design@beta", "kind": "note", "body": "first ping"}
JSON
cat > "$ALPHA_HOME/.local/bus-outbox/m2.json" <<'JSON'
{"to": "zc-bus-design@beta", "kind": "note", "body": "second ping"}
JSON
bridge alpha "$ALPHA_TOKEN" "$ALPHA_HOME" 1 | sed 's/^/  [alpha] /'
[[ -f "$ALPHA_HOME/.local/bus-outbox/sent/m1.json" ]] || fail "alpha outbox not drained"

beta_state="$BETA_HOME/.local/bus-bridge/state-beta.json"
bridge beta "$BETA_TOKEN" "$BETA_HOME" 1 | sed 's/^/  [beta]  /'
[[ "$(wc -l < "$INBOX")" == "2" ]] || fail "expected 2 delivered lines, got $(wc -l < "$INBOX")"
[[ "$(sed -n 1p "$INBOX" | jq -r .body)" == "[from demo@alpha] first ping" ]] \
  || fail "first line wrong: $(sed -n 1p "$INBOX")"
[[ "$(sed -n 2p "$INBOX" | jq -r .body)" == "[from demo@alpha] second ping" ]] \
  || fail "second line wrong: $(sed -n 2p "$INBOX")"
pass "A->B delivered in order while beta was offline (2 lines, [from demo@alpha] prefix)"

echo "== 4. dedup on resend"
BUS_ID="$(jq -r .bus_id "$ALPHA_HOME/.local/bus-outbox/sent/m1.json.sent.json")"
dup_payload="{\"id\":\"$BUS_ID\",\"to\":{\"machine\":\"beta\",\"tag\":\"zc-bus-design\"},\"kind\":\"note\",\"body\":\"first ping\",\"from\":{\"tag\":\"demo\"}}"
r1="$(curl -s -X POST -H "Authorization: Bearer $ALPHA_TOKEN" -H 'content-type: application/json' \
  -d "$dup_payload" "$URL/v1/messages")"
r2="$(curl -s -X POST -H "Authorization: Bearer $ALPHA_TOKEN" -H 'content-type: application/json' \
  -d "$dup_payload" "$URL/v1/messages")"
[[ "$(jq -r .duplicate <<<"$r2")" == "true" ]] || fail "resend not flagged duplicate: $r2"
[[ "$(jq -r .message.seq <<<"$r1")" == "$(jq -r .message.seq <<<"$r2")" ]] || fail "resend seq changed"
bridge beta "$BETA_TOKEN" "$BETA_HOME" 1 >/dev/null
bridge alpha "$ALPHA_TOKEN" "$ALPHA_HOME" 1 >/dev/null 2>&1 || true
[[ "$(wc -l < "$INBOX")" == "2" ]] || fail "resend produced duplicate delivery"
pass "resend got duplicate:true, same seq; no duplicate delivery downstream"

echo "== summary"
echo "beta inbox:"
sed 's/^/  /' "$INBOX"
echo "demo OK: bad-token rejection, A->B, offline queueing, dedup on resend"
