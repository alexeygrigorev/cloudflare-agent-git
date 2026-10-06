#!/usr/bin/env bash
# Two-'machine' demo against one local `wrangler dev`:
#   1. bad token rejected            2. A->B delivery
#   3. offline queueing (B down while A sends)
#   4. dedup on resend (deterministic outbox id + bus duplicate receipt)
#   5. stored-then-lost reply: blind resend after a lost 200 dedups to the same seq
#   6. ACL: a forged from.machine is re-stamped from the token, never trusted
#   7. uncertain native send -> outcome=UNKNOWN; retry keeps the SAME id
#   8. network drop mid-poll: wrangler killed + restarted; no loss, no duplicates
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
BETA_STATE="$BETA_HOME/.local/bus-bridge/state-beta.json"
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

post() { # post <token> <json-payload> -> response body
  curl -s -X POST -H "Authorization: Bearer $1" -H 'content-type: application/json' \
    -d "$2" "$URL/v1/messages"
}

bridge() { # bridge <machine> <token> <home> <max-cycles> [extra bridge args...]
  python3 "$BUS_DIR/bridge/bridge.py" \
    --bus-url "$URL" --machine "$1" --token "$2" --workspace "$3" \
    --tag demo --delivery "file:$INBOX" --long-poll 1 --max-cycles "$4" "${@:5}"
}

wait_wrangler() { # wait_wrangler <log-file>
  for _ in $(seq 1 90); do
    code="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $ALPHA_TOKEN" \
      "$URL/v1/messages?after=0&wait=0" || true)"
    if [[ "$code" == "200" ]]; then return 0; fi
    sleep 1
  done
  tail -20 "$1" >&2
  fail "wrangler dev did not come up"
}

start_wrangler() { # start_wrangler <log-file>  (DO state persists across restarts per CHANNEL_ID)
  fuser -k "$PORT/tcp" 2>/dev/null || true
  sleep 1
  ( cd "$WORKER_DIR" && exec setsid "$NODE_MODULES/.bin/wrangler" dev --port "$PORT" \
      --var "CHANNEL_ID:$CHANNEL_ID" ) >"$1" 2>&1 &
  WRANGLER_PID=$!
  wait_wrangler "$1"
}

stop_wrangler() {
  [[ -n "$WRANGLER_PID" ]] || return 0
  kill -TERM -- "-$WRANGLER_PID" 2>/dev/null || kill "$WRANGLER_PID" 2>/dev/null || true
  WRANGLER_PID=""
}

echo "== starting wrangler dev on $URL (work: $WORK)"
# Unique channel per run: wrangler persists DO state under worker/.wrangler between
# runs, and deterministic outbox ids legitimately dedup across runs on one channel.
CHANNEL_ID="demo-$(date +%s)-$RANDOM"
start_wrangler "$WORK/wrangler.log"

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
bridge alpha "$ALPHA_TOKEN" "$ALPHA_HOME" 1 | tee "$WORK/alpha-23.log" | sed 's/^/  [alpha] /'
[[ -f "$ALPHA_HOME/.local/bus-outbox/sent/m1.json" ]] || fail "alpha outbox not drained"

beta_state="$BETA_STATE"
bridge beta "$BETA_TOKEN" "$BETA_HOME" 1 | tee "$WORK/beta-23.log" | sed 's/^/  [beta]  /'
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

echo "== 5. stored-then-lost reply: bus stored it, client never saw the 200"
LOST_ID="b-lost200-$(date +%s)"
lost_payload="{\"id\":\"$LOST_ID\",\"to\":{\"machine\":\"beta\",\"tag\":\"zc-bus-design\"},\"kind\":\"note\",\"body\":\"lost-200 ping\"}"
# The client posts; the bus commits... and the connection dies before the 200 arrives.
curl -s -o /dev/null -X POST -H "Authorization: Bearer $ALPHA_TOKEN" \
  -H 'content-type: application/json' -d "$lost_payload" "$URL/v1/messages"
# The client knows only its own id — it resends blind with the SAME id.
r2="$(post "$ALPHA_TOKEN" "$lost_payload")"
[[ "$(jq -r .duplicate <<<"$r2")" == "true" ]] || fail "lost-200 resend not flagged duplicate: $r2"
LOST_SEQ="$(jq -r .message.seq <<<"$r2")"
bridge beta "$BETA_TOKEN" "$BETA_HOME" 1 >/dev/null
[[ "$(jq -s --arg id "$LOST_ID" '[.[] | select(.bus_id==$id)] | length' "$INBOX")" == "1" ]] \
  || fail "lost-200 message did not land exactly once"
[[ "$(grep "$LOST_ID" "$INBOX" | jq -r .seq)" == "$LOST_SEQ" ]] \
  || fail "delivered seq differs from the deduped resend seq"
pass "blind resend after lost 200 -> duplicate:true, same seq $LOST_SEQ, exactly one delivery"

echo "== 6. ACL: alpha's token claiming to be beta is re-stamped, never trusted"
spoof='{"to":{"machine":"beta","tag":"zc-bus-design"},"kind":"note","body":"spoof attempt","from":{"machine":"beta","tag":"demo"}}'
sres="$(post "$ALPHA_TOKEN" "$spoof")"
[[ "$(jq -r .message.from.machine <<<"$sres")" == "alpha" ]] \
  || fail "bus stored a client machine claim: $sres"
beta_view="$(curl -s -H "Authorization: Bearer $BETA_TOKEN" "$URL/v1/messages?after=0&wait=0")"
[[ "$(jq -r '[.messages[] | select(.body=="spoof attempt")][0].from.machine' <<<"$beta_view")" == "alpha" ]] \
  || fail "beta stream shows a forged origin"
bridge beta "$BETA_TOKEN" "$BETA_HOME" 1 >/dev/null
grep -q '\[from demo@alpha\] spoof attempt' "$INBOX" || fail "inbox line does not show demo@alpha origin"
pass "forged from.machine=beta stamped to alpha on the bus and in the inbox line"

echo "== 7. uncertain native send -> outcome=UNKNOWN; retry keeps the SAME id"
stub="$WORK/stubbin"; mkdir -p "$stub"
printf '#!/usr/bin/env bash\nsleep 30\n' > "$stub/aplexer"
chmod +x "$stub/aplexer"
uk_res="$(post "$ALPHA_TOKEN" \
  '{"to":{"machine":"beta","tag":"zc-bus-design"},"kind":"note","body":"unknown-delivery ping"}')"
UK_ID="$(jq -r .message.id <<<"$uk_res")"
lines_before="$(wc -l < "$INBOX")"
cursor_before="$(jq -r .cursor "$BETA_STATE")"
# beta with the REAL aplexer path, but the stubbed binary hangs -> send times out.
PATH="$stub:$PATH" python3 "$BUS_DIR/bridge/bridge.py" \
  --bus-url "$URL" --machine beta --token "$BETA_TOKEN" --workspace "$BETA_HOME" \
  --tag demo --delivery aplexer --long-poll 1 --max-cycles 1 --send-timeout 2 \
  >"$WORK/beta-unknown.log" 2>&1 || true
grep -q "outcome=UNKNOWN" "$WORK/beta-unknown.log" || fail "no UNKNOWN outcome logged: $(cat "$WORK/beta-unknown.log")"
[[ "$(wc -l < "$INBOX")" == "$lines_before" ]] || fail "uncertain send must not count as delivered"
[[ "$(jq -r .cursor "$BETA_STATE")" == "$cursor_before" ]] || fail "cursor moved past an uncertain message"
[[ -z "$(jq -r --arg id "$UK_ID" '.delivered[$id] // empty' "$BETA_STATE")" ]] \
  || fail "uncertain message was marked delivered"
bridge beta "$BETA_TOKEN" "$BETA_HOME" 1 | sed 's/^/  [beta]  /'
[[ "$(tail -1 "$INBOX" | jq -r .bus_id)" == "$UK_ID" ]] || fail "redelivery minted a NEW id"
[[ "$(wc -l < "$INBOX")" == "$((lines_before + 1))" ]] || fail "expected exactly one new line"
pass "UNKNOWN left undelivered (cursor untouched); redelivery reused id ${UK_ID:0:16}…"

echo "== 8. network drop mid-poll: kill + restart wrangler; no loss, no duplicates"
lines_before="$(wc -l < "$INBOX")"
bridge beta "$BETA_TOKEN" "$BETA_HOME" 60 --poll-interval 1 --long-poll 3 \
  >"$WORK/beta-reconnect.log" 2>&1 &
BETA_BG_PID=$!
sleep 2  # beta is now inside a long-poll
cat > "$ALPHA_HOME/.local/bus-outbox/m3.json" <<'JSON'
{"to": "zc-bus-design@beta", "kind": "note", "body": "reconnect ping"}
JSON
bridge alpha "$ALPHA_TOKEN" "$ALPHA_HOME" 1 | tee "$WORK/alpha-8.log" | sed 's/^/  [alpha] /'
stop_wrangler
echo "  (wrangler dev killed while beta is mid-poll)"
sleep 1
code="$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $ALPHA_TOKEN" \
  "$URL/v1/messages?after=0&wait=0" || true)"
[[ "$code" != "200" ]] || fail "bus is still serving — the kill did not produce a real outage"
sleep 1
start_wrangler "$WORK/wrangler2.log"
for _ in $(seq 1 60); do
  [[ "$(wc -l < "$INBOX")" -ge "$((lines_before + 1))" ]] && break
  sleep 1
done
[[ "$(wc -l < "$INBOX")" == "$((lines_before + 1))" ]] \
  || fail "reconnect delivered $(wc -l < "$INBOX") lines, want $((lines_before + 1))"
[[ "$(tail -1 "$INBOX" | jq -r .body)" == "[from demo@alpha] reconnect ping" ]] \
  || fail "wrong message after reconnect"
sleep 6  # a few more beta cycles — a duplicate would show up here
[[ "$(wc -l < "$INBOX")" == "$((lines_before + 1))" ]] || fail "duplicate delivery after reconnect"
kill "$BETA_BG_PID" 2>/dev/null || true
wait "$BETA_BG_PID" 2>/dev/null || true
grep -q "outcome=queued" "$WORK/alpha-23.log" || fail "no outcome=queued in alpha log"
grep -q "outcome=transported" "$WORK/alpha-8.log" || fail "no outcome=transported in alpha log"
grep -q "outcome=received-into-inbox" "$WORK/beta-reconnect.log" || fail "no outcome=received-into-inbox in beta log"
grep -q "outcome=acked" "$WORK/beta-23.log" || fail "no outcome=acked in beta log"
pass "reconnect after kill: m3 delivered exactly once; typed outcomes all observed"

echo "== summary"
echo "beta inbox:"
sed 's/^/  /' "$INBOX"
echo "demo OK: bad-token rejection, A->B, offline queueing, dedup on resend,
  stored-then-lost reply, ACL re-stamping, UNKNOWN with same-id retry, reconnect after drop"
