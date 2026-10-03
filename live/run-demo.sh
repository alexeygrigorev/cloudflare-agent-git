#!/usr/bin/env bash
# Agent Branches — real end-to-end demo run (run 2, zc-live-2).
#
# Flow per prototype/CONTRACT.md v0.1 (L1 @ 762ff3d):
#   sidecar (L1 local-artifacts) + wrangler dev -> POST /setup -> canonical seed
#   push (per-repo write token) -> POST /tasks x3 -> agent pushes (reference
#   patches) -> radar matrix -> POST /checks (RUNNER_TOKEN) -> stale 409 probe
#   -> radar pass 2 -> UI screenshot -> assertions.
#
# Idempotency: data steps leave a marker under live/state/ and are skipped on
# re-runs; services are health-checked and started only when down.
# Server processes: started with </dev/null, output to log files, PID recorded
# in live/state/, cleaned up by the EXIT trap. Never pkill by pattern.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIVE="$ROOT/live"
STATE="$LIVE/state"; EVIDENCE="$LIVE/evidence"; WORK="$LIVE/work"; ART="$LIVE/artifacts"
mkdir -p "$STATE" "$EVIDENCE" "$WORK" "$ART"

# Tokens + ports come from the untracked live/.dev.vars (exported there).
# shellcheck disable=SC1091
source "$LIVE/.dev.vars"
SIDECAR="http://127.0.0.1:${SIDECAR_PORT:-8799}"
WORKER="http://127.0.0.1:${WORKER_PORT:-8787}"
UI_PORT="${UI_PORT:-8788}"
NODE_BIN="$(command -v node)"
export SIDECAR_PORT SIDECAR_HOST="127.0.0.1"
export SIDECAR_ROOT="$ART"
export SIDECAR_TOKEN
export SIDECAR_NOTIFY_URL="$WORKER/events/push"

SIDE_PIDS=()
cleanup() {
  for pid in "${SIDE_PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT

log() { echo "[run-demo $(date +%H:%M:%S)] $*"; }
step_done() { [ -f "$STATE/$1.done" ]; }
mark() { touch "$STATE/$1.done"; }

wait_for() { # url name tries
  local url="$1" name="$2" tries="${3:-60}"
  for _ in $(seq 1 "$tries"); do
    if curl -sf -o /dev/null "$url"; then return 0; fi
    sleep 1
  done
  echo "FATAL: $name did not come up at $url" >&2
  return 1
}

start_bg() { # logfile pidfile cmd...
  local logfile="$1" pidfile="$2"; shift
  nohup "$@" > "$logfile" 2>&1 < /dev/null &
  echo $! > "$pidfile"
  SIDE_PIDS+=("$(cat "$pidfile")")
}

mem_guard() {
  local avail_kb
  avail_kb=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
  if [ "$avail_kb" -lt $((2 * 1024 * 1024)) ]; then
    echo "FATAL: MemAvailable ${avail_kb}kB < 2GiB stop threshold" >&2
    exit 1
  fi
}

ADMIN_AUTH=(-H "Authorization: Bearer $ADMIN_TOKEN" -H "content-type: application/json")
SIDECAR_AUTH=(-H "Authorization: Bearer $SIDECAR_TOKEN")
RUNNER_AUTH=(-H "Authorization: Bearer $RUNNER_TOKEN" -H "content-type: application/json")

# ---------- 1. services (idempotent: skip if the port already serves) ----------

mem_guard

if curl -sf "$SIDECAR/api/health" -H "Authorization: Bearer $SIDECAR_TOKEN" >/dev/null 2>&1; then
  log "sidecar already up on :${SIDECAR_PORT}"
else
  log "starting L1 local-artifacts sidecar on :${SIDECAR_PORT}"
  start_bg "$LIVE/sidecar.log" "$STATE/sidecar.pid" \
    "$NODE_BIN" "$ROOT/prototype/local-artifacts/sidecar.mjs"
  wait_for "$SIDECAR/api/health" sidecar 30
fi

if curl -sf "$WORKER/status" >/dev/null 2>&1; then
  log "worker already up on :${WORKER_PORT}"
else
  log "starting wrangler dev on :${WORKER_PORT}"
  NPX_BIN="$(command -v npx)"
  start_bg "$LIVE/wrangler.log" "$STATE/wrangler.pid" \
    bash -c "cd '$ROOT/prototype' && exec '$NPX_BIN' wrangler dev --local --port '$WORKER_PORT' \
    --var ADMIN_TOKEN:'$ADMIN_TOKEN' \
    --var RUNNER_TOKEN:'$RUNNER_TOKEN' \
    --var LOCAL_ARTIFACTS_URL:'$SIDECAR' \
    --var LOCAL_ARTIFACTS_TOKEN:'$SIDECAR_TOKEN' \
    --var RADAR_IMPL:silent"
  wait_for "$WORKER/status" wrangler-dev 180
fi

# ---------- 2. canonical repo seeded from demo-target (L1 documented flow) ----------
# POST /setup returns the canonical name (suffix -<8hex>) and remote; the seed
# is pushed with a per-repo WRITE token minted on the sidecar admin API.

if step_done canonical-seeded; then
  log "skip: canonical seeded"
else
  log "POST /setup (admin)"
  SETUP_CODE="$(curl -s -o "$EVIDENCE/setup.json" -w "%{http_code}" \
    -X POST "$WORKER/setup" "${ADMIN_AUTH[@]}")"
  [ "$SETUP_CODE" = "201" ] || [ "$SETUP_CODE" = "200" ] || {
    echo "FATAL: /setup returned $SETUP_CODE" >&2; cat "$EVIDENCE/setup.json"; exit 1; }
  CANON="$(python3 -c 'import json; print(json.load(open("'"$EVIDENCE"'/setup.json"))["canonical"]["name"])')"
  CANON_REMOTE="$(python3 -c 'import json; print(json.load(open("'"$EVIDENCE"'/setup.json"))["canonical"]["remote"])')"
  log "canonical repo: $CANON at $CANON_REMOTE"

  log "minting canonical write token (sidecar admin API)"
  CANON_TOKEN="$(curl -sf -X POST "$SIDECAR/api/repos/$CANON/tokens" \
    "${SIDECAR_AUTH[@]}" -H "content-type: application/json" \
    -d '{"scope":"write","ttlSeconds":3600}' \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["plaintext"])')"
  [ -n "$CANON_TOKEN" ] || { echo "FATAL: no canonical write token" >&2; exit 1; }

  log "cloning empty canonical + seeding from demo-target (excluding .harness)"
  rm -rf "$WORK/seed"
  git clone -q "$CANON_REMOTE" "$WORK/seed" 2>/dev/null
  mkdir -p "$WORK/seed"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude .git --exclude .harness "$ROOT/demo-target/" "$WORK/seed/"
  else
    ( shopt -s dotglob; find "$ROOT/demo-target" -maxdepth 1 \
        ! -name .git ! -name .harness -exec cp -a {} "$WORK/seed/" \; )
  fi
  git -C "$WORK/seed" add -A
  git -C "$WORK/seed" \
    -c user.name="demo-seed" -c user.email="seed@demo.agents" \
    commit -q -m "chore: canonical baseline from demo-target (no .harness)"
  git -C "$WORK/seed" -c http.extraHeader="Authorization: Bearer $CANON_TOKEN" push -q origin main
  git -C "$WORK/seed" rev-parse HEAD > "$STATE/base.sha"
  python3 -c 'import json; d=json.load(open("'"$EVIDENCE"'/setup.json")); d["seedCommit"]="'$(cat "$STATE/base.sha")'"; json.dump(d, open("'"$EVIDENCE"'/setup.json","w"), indent=2)'
  mark canonical-seeded
  log "canonical seeded at $(cat "$STATE/base.sha")"
fi
BASE_SHA="$(cat "$STATE/base.sha")"
CANON="$(python3 -c 'import json; print(json.load(open("'"$EVIDENCE"'/setup.json"))["canonical"]["name"])')"

# ---------- 3. create tasks T1..T3 (admin) ----------

declare -A AGENT_ID FORK_URL TOKEN
for t in t1 t2 t3; do
  if [ ! -f "$STATE/task-$t.json" ]; then
    log "creating task $t"
    curl -sf -X POST "$WORKER/tasks" "${ADMIN_AUTH[@]}" \
      -d "{\"agent\":\"demo-$t\",\"intent\":\"reference solution $t\"}" > "$STATE/task-$t.json"
  fi
  AGENT_ID[$t]="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['agentId'])" "$STATE/task-$t.json")"
  FORK_URL[$t]="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['fork']['remote'])" "$STATE/task-$t.json")"
  TOKEN[$t]="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['token']['plaintext'])" "$STATE/task-$t.json")"
done

# ---------- 4. the 3 agents' pushes: apply reference patches ----------

for t in t1 t2 t3; do
  if step_done "pushed-$t"; then
    log "skip: $t pushed"
    continue
  fi
  log "agent ${AGENT_ID[$t]}: clone fork, apply $t patch, push"
  rm -rf "$WORK/$t"
  git clone -q "${FORK_URL[$t]}" "$WORK/$t"
  git -C "$WORK/$t" apply -p2 "$ROOT/demo-target/.harness/reference-solutions/$t.patch"
  git -C "$WORK/$t" add -A
  git -C "$WORK/$t" \
    -c user.name="demo-agent-$t" -c user.email="${t}@demo.agents" \
    commit -q -m "${t}: reference solution applied by agent harness"
  git -C "$WORK/$t" -c http.extraHeader="Authorization: Bearer ${TOKEN[$t]}" push -q origin main
  SHA="$(git -C "$WORK/$t" rev-parse HEAD)"
  echo "$SHA" > "$STATE/$t.sha"
  # belt and braces: the sidecar post-receive hook also notifies /events/push;
  # the coordinator dedupes (agent, sha).
  curl -sf -X POST "$WORKER/events/push" -H "content-type: application/json" \
    -d "{\"agent\":\"${AGENT_ID[$t]}\",\"sha\":\"$SHA\"}" > "$EVIDENCE/push-$t.json"
  mark "pushed-$t"
  log "$t pushed $SHA"
done

# ---------- helpers: radar run at a given vector ----------

run_radar() { # prefix head_t1 head_t2 head_t3
  local prefix="$1" h1="$2" h2="$3" h3="$4"
  rm -rf "$WORK/radar-repo"
  git init -q "$WORK/radar-repo"
  git -C "$WORK/radar-repo" fetch -q "$SIDECAR/git/$CANON.git" "main:refs/heads/base"
  git -C "$WORK/radar-repo" fetch -q "${FORK_URL[t1]}" "main:refs/heads/${AGENT_ID[t1]}"
  git -C "$WORK/radar-repo" fetch -q "${FORK_URL[t2]}" "main:refs/heads/${AGENT_ID[t2]}"
  git -C "$WORK/radar-repo" fetch -q "${FORK_URL[t3]}" "main:refs/heads/${AGENT_ID[t3]}"
  python3 -m radar \
    --repo "$WORK/radar-repo" \
    --base "$BASE_SHA" \
    --heads "${AGENT_ID[t1]}=$h1" "${AGENT_ID[t2]}=$h2" "${AGENT_ID[t3]}=$h3" \
    --test-cmd "$NODE_BIN --test" \
    --force-test --budget 120 --max-vmem 8192 \
    --l1 > "$EVIDENCE/$prefix-l1.json" 2> "$EVIDENCE/$prefix-radar.err"
  log "radar pass $prefix: $(python3 -c 'import json; d=json.load(open("'"$EVIDENCE"'/'"$prefix"'-l1.json")); print(" ".join(r["pair"][0]+"|"+r["pair"][1]+"="+r["status"]+(("/"+r["kind"]) if r.get("kind") else "") for r in d["results"]))')"
}

post_checks() { # payload_file out_file -> http code on stdout
  local code
  code="$(curl -s -o "$2" -w "%{http_code}" -X POST "$WORKER/checks" \
    "${RUNNER_AUTH[@]}" --data-binary "@$1")"
  echo "$code"
}

# ---------- 5. radar pass 1 + POST /checks (expect 200) ----------

if step_done radar-1; then
  log "skip: radar pass 1"
else
  log "running radar pass 1 at the 3-agent vector"
  run_radar radar1 "$(cat "$STATE/t1.sha")" "$(cat "$STATE/t2.sha")" "$(cat "$STATE/t3.sha")"
  CODE="$(post_checks "$EVIDENCE/radar1-l1.json" "$EVIDENCE/checks1-receipt.json")"
  echo "$CODE" > "$STATE/checks1.code"
  [ "$CODE" = "200" ] || { echo "FATAL: /checks pass1 returned $CODE" >&2; cat "$EVIDENCE/checks1-receipt.json"; exit 1; }
  mark radar-1
fi

# ---------- 6. assertions phase 1 ----------

if step_done assert-1; then
  log "skip: assertions 1"
else
  curl -sf "$WORKER/status" > "$EVIDENCE/status-1.json"
  for t in t1 t2 t3; do
    curl -sf "$WORKER/tasks/$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['taskId'])" "$STATE/task-$t.json")" \
      > "$EVIDENCE/task-$t.json" || true
  done
  python3 "$LIVE/assertions.py" phase1 \
    --live "$LIVE" --evidence "$EVIDENCE" --state "$STATE" --status status-1.json | tee "$EVIDENCE/assertions-1.txt"
  mark assert-1
fi

# ---------- 7. stale probe: churn push on t1, replay old payload -> 409 ----------

if step_done stale-409; then
  log "skip: stale-409"
else
  log "churn push on t1, then replay old radar payload expecting 409"
  printf '\n<!-- churn %s -->\n' "$(date -Is)" >> "$WORK/t1/README.md"
  git -C "$WORK/t1" add -A
  git -C "$WORK/t1" \
    -c user.name="demo-agent-t1" -c user.email="t1@demo.agents" \
    commit -q -m "docs: churn commit to invalidate stale checks"
  git -C "$WORK/t1" -c http.extraHeader="Authorization: Bearer ${TOKEN[t1]}" push -q origin main
  T1_NEW_SHA="$(git -C "$WORK/t1" rev-parse HEAD)"
  echo "$T1_NEW_SHA" > "$STATE/t1.sha"
  curl -sf -X POST "$WORKER/events/push" -H "content-type: application/json" \
    -d "{\"agent\":\"${AGENT_ID[t1]}\",\"sha\":\"$T1_NEW_SHA\"}" > "$EVIDENCE/push-t1-churn.json"
  CODE="$(post_checks "$EVIDENCE/radar1-l1.json" "$EVIDENCE/stale-409.json")"
  echo "$CODE" > "$STATE/stale409.code"
  [ "$CODE" = "409" ] || { echo "FATAL: stale replay expected 409 got $CODE" >&2; cat "$EVIDENCE/stale-409.json"; exit 1; }
  mark stale-409
  log "stale replay correctly rejected with 409"
fi

# ---------- 8. radar pass 2 at the new vector ----------

if step_done radar-2; then
  log "skip: radar pass 2"
else
  log "running radar pass 2 after churn push"
  run_radar radar2 "$(cat "$STATE/t1.sha")" "$(cat "$STATE/t2.sha")" "$(cat "$STATE/t3.sha")"
  CODE="$(post_checks "$EVIDENCE/radar2-l1.json" "$EVIDENCE/checks2-receipt.json")"
  echo "$CODE" > "$STATE/checks2.code"
  [ "$CODE" = "200" ] || { echo "FATAL: /checks pass2 returned $CODE" >&2; cat "$EVIDENCE/checks2-receipt.json"; exit 1; }
  mark radar-2
fi

# ---------- 9. UI evidence: /status JSON + headless screenshot ----------

if step_done ui; then
  log "skip: ui evidence"
else
  log "capturing /status + UI screenshot"
  curl -sf "$WORKER/status" > "$EVIDENCE/status.json"
  (cd "$ROOT/prototype/ui" && nohup python3 -m http.server "$UI_PORT" --bind 127.0.0.1 \
    > "$LIVE/ui-server.log" 2>&1 < /dev/null & echo $! > "$STATE/ui.pid")
  wait_for "http://127.0.0.1:$UI_PORT/index.html" ui-server 30
  SIDE_PIDS+=("$(cat "$STATE/ui.pid")")
  CHROME="$HOME/.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell"
  "$CHROME" --headless --no-sandbox --disable-gpu --window-size=1440,1100 \
    --virtual-time-budget=15000 \
    --screenshot="$EVIDENCE/ui-index.png" \
    "http://127.0.0.1:$UI_PORT/index.html?api=http://127.0.0.1:$WORKER_PORT" \
    > "$LIVE/screenshot.log" 2>&1 || echo "WARN: screenshot failed (see live/screenshot.log)"
  mark ui
fi

# ---------- 10. final assertions ----------

mem_guard
curl -sf "$WORKER/status" > "$EVIDENCE/status.json"
python3 "$LIVE/assertions.py" final \
  --live "$LIVE" --evidence "$EVIDENCE" --state "$STATE" --status status.json | tee "$EVIDENCE/summary.txt"
log "done. evidence in live/evidence/"
