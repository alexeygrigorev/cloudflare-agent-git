#!/usr/bin/env bash
# First real end-to-end run of Agent Branches on this host.
# Idempotent: each data step leaves a marker under live/state/ and is skipped
# on re-runs; services are health-checked and (re)started only when down.
# zcodex may execute a shell call twice — markers + health checks keep this safe.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIVE="$ROOT/live"
STATE="$LIVE/state"; EVIDENCE="$LIVE/evidence"; WORK="$LIVE/work"; ART="$LIVE/artifacts"
mkdir -p "$STATE" "$EVIDENCE" "$WORK" "$ART"

# shellcheck disable=SC1091
source "$LIVE/.dev.vars"
SIDECAR="http://127.0.0.1:${SIDECAR_PORT:-8799}"
WORKER="http://127.0.0.1:${WORKER_PORT:-8787}"
UI_PORT="${UI_PORT:-8788}"
API_AUTH=(-H "Authorization: Bearer $ADMIN_TOKEN" -H "content-type: application/json")
NODE_BIN="$(command -v node)"
export ARTIFACTS_ROOT="$ART" SIDECAR_PORT WORKER_PORT ADMIN_TOKEN RUNNER_TOKEN
# python3 -m radar resolves the radar package relative to cwd
cd "$ROOT"
if command -v rsync >/dev/null 2>&1; then
  sync_tree() { rsync -a --delete --exclude .git "$1/" "$2/"; }
else
  sync_tree() { rm -rf "$2"; mkdir -p "$2"; cp -a "$1/." "$2/"; }
fi

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

mem_guard() {
  local avail_kb
  avail_kb=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
  if [ "$avail_kb" -lt $((10 * 1024 * 1024)) ]; then
    echo "FATAL: MemAvailable ${avail_kb}kB < 10GiB stop threshold" >&2
    exit 1
  fi
}

# ---------- 1. services ----------

mem_guard
if curl -sf "$SIDECAR/api/health" -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null 2>&1; then
  log "sidecar already up"
else
  log "starting git sidecar on :${SIDECAR_PORT}"
  (cd "$ROOT" && nohup node "$LIVE/sidecar.mjs" > "$LIVE/sidecar.log" 2>&1 &)
  wait_for "$SIDECAR/api/health" sidecar
fi

if curl -sf "$WORKER/status" >/dev/null 2>&1; then
  log "worker already up"
else
  log "starting wrangler dev on :${WORKER_PORT}"
  (cd "$ROOT/prototype" && nohup npx wrangler dev --local --port "$WORKER_PORT" \
    --var ARTIFACTS_IMPL:sidecar \
    --var SIDECAR_URL:"$SIDECAR" \
    --var SIDECAR_TOKEN:"$ADMIN_TOKEN" \
    --var RADAR_IMPL:silent \
    > "$LIVE/wrangler.log" 2>&1 &)
  wait_for "$WORKER/status" wrangler-dev 120
fi

# ---------- 2. canonical repo seeded from demo-target ----------

if step_done canonical-seeded; then
  log "skip: canonical seeded"
else
  log "POST /setup + seeding canonical from demo-target/"
  curl -sf -X POST "$WORKER/setup" "${API_AUTH[@]}" > "$EVIDENCE/setup.json"
  rm -rf "$WORK/seed"
  git clone -q "$SIDECAR/git/agent-branches-canonical.git" "$WORK/seed"
  sync_tree "$ROOT/demo-target" "$WORK/seed"
  git -C "$WORK/seed" add -A
  git -C "$WORK/seed" \
    -c user.name="demo-seed" -c user.email="seed@demo.agents" \
    commit -q -m "chore: canonical baseline from demo-target at $(git -C "$ROOT" rev-parse --short origin/proto/l5-demo-target)"
  # pushes need a per-repo write token; admin mints one for the seed push
  CANON_TOKEN="$(curl -sf -X POST "$SIDECAR/api/repos/agent-branches-canonical/tokens" \
    -H "Authorization: Bearer $ADMIN_TOKEN" -H "content-type: application/json" \
    -d '{"scope":"write","ttlSeconds":3600}' \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["plaintext"])')"
  git -C "$WORK/seed" -c http.extraHeader="Authorization: Bearer $CANON_TOKEN" push -q origin main
  git -C "$WORK/seed" rev-parse HEAD > "$STATE/base.sha"
  mark canonical-seeded
  log "canonical seeded at $(cat "$STATE/base.sha")"
fi
BASE_SHA="$(cat "$STATE/base.sha")"

# ---------- 3. create tasks (T1..T3) ----------

declare -A TASK_JSON AGENT_ID FORK_URL TOKEN
for t in t1 t2 t3; do
  if [ -f "$STATE/task-$t.json" ]; then
    TASK_JSON[$t]="$(cat "$STATE/task-$t.json")"
  else
    log "creating task $t"
    curl -sf -X POST "$WORKER/tasks" "${API_AUTH[@]}" \
      -d "{\"agent\":\"demo-$t\"}" > "$STATE/task-$t.json"
    TASK_JSON[$t]="$(cat "$STATE/task-$t.json")"
  fi
  AGENT_ID[$t]="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['agentId'])" "$STATE/task-$t.json")"
  FORK_URL[$t]="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['fork']['remote'])" "$STATE/task-$t.json")"
  TOKEN[$t]="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['token']['plaintext'])" "$STATE/task-$t.json")"
done

# ---------- 4. apply reference solutions as real agent work ----------

for t in t1 t2 t3; do
  if step_done "pushed-$t"; then
    log "skip: $t pushed"
    continue
  fi
  log "cloning fork for $t, applying reference patch, pushing"
  rm -rf "$WORK/$t"
  git clone -q "${FORK_URL[$t]}" "$WORK/$t"
  git -C "$WORK/$t" apply -p2 "$ROOT/demo-target/reference-solutions/$t.patch"
  git -C "$WORK/$t" add -A
  git -C "$WORK/$t" \
    -c user.name="demo-agent-$t" -c user.email="${t}@demo.agents" \
    commit -q -m "T${t#t}: reference solution ${t}"
  git -C "$WORK/$t" -c http.extraHeader="Authorization: Bearer ${TOKEN[$t]}" push -q origin main
  SHA="$(git -C "$WORK/$t" rev-parse HEAD)"
  echo "$SHA" > "$STATE/$t.sha"
  curl -sf -X POST "$WORKER/events/push" "${API_AUTH[@]}" \
    -d "{\"agent\":\"${AGENT_ID[$t]}\",\"sha\":\"$SHA\"}" > "$EVIDENCE/push-$t.json"
  mark "pushed-$t"
  log "$t pushed $SHA"
done

# ---------- helpers: radar run at a given vector ----------

run_radar() { # out_prefix head_t1 head_t2 head_t3
  local prefix="$1" h1="$2" h2="$3" h3="$4"
  rm -rf "$WORK/radar-repo"
  git init -q "$WORK/radar-repo"
  git -C "$WORK/radar-repo" fetch -q "$SIDECAR/git/agent-branches-canonical.git" "main:refs/heads/base"
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
  python3 -m radar \
    --repo "$WORK/radar-repo" \
    --base "$BASE_SHA" \
    --heads "${AGENT_ID[t1]}=$h1" "${AGENT_ID[t2]}=$h2" "${AGENT_ID[t3]}=$h3" \
    --test-cmd "$NODE_BIN --test" \
    --force-test --budget 120 --max-vmem 8192 \
    > "$EVIDENCE/$prefix-verbose.txt" 2>> "$EVIDENCE/$prefix-radar.err"
}

post_checks() { # payload_file out_file
  local code
  code="$(curl -s -o "$2" -w "%{http_code}" -X POST "$WORKER/checks" \
    "${API_AUTH[@]}" --data-binary "@$1")"
  echo "$code"
}

# ---------- 5. radar pass 1 + POST /checks ----------

if step_done radar-1; then
  log "skip: radar pass 1"
else
  log "running radar pass 1 at base vector"
  run_radar radar1 "$(cat "$STATE/t1.sha")" "$(cat "$STATE/t2.sha")" "$(cat "$STATE/t3.sha")"
  CODE="$(post_checks "$EVIDENCE/radar1-l1.json" "$EVIDENCE/checks1-receipt.json")"
  echo "checks1_http=$CODE" > "$STATE/checks1.code"
  [ "$CODE" = "201" ] || { echo "FATAL: /checks pass1 returned $CODE" >&2; cat "$EVIDENCE/checks1-receipt.json"; exit 1; }
  mark radar-1
fi

# ---------- 6. assertions phase 1 (verdicts + status) ----------

if step_done assert-1; then
  log "skip: assertions 1"
else
  curl -sf "$WORKER/status" > "$EVIDENCE/status-1.json"
  for t in t1 t2 t3; do
    curl -sf "$WORKER/tasks/$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['taskId'])" "$STATE/task-$t.json")" \
      > "$EVIDENCE/task-$t.json" || true
  done
  python3 "$LIVE/assertions.py" phase1 \
    --live "$LIVE" --evidence "$EVIDENCE" --state "$STATE" | tee "$EVIDENCE/assertions-1.txt"
  mark assert-1
fi

# ---------- 7. stale check: new push then replay old payload -> 409 ----------

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
  curl -sf -X POST "$WORKER/events/push" "${API_AUTH[@]}" \
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
  [ "$CODE" = "201" ] || { echo "FATAL: /checks pass2 returned $CODE" >&2; cat "$EVIDENCE/checks2-receipt.json"; exit 1; }
  mark radar-2
fi

# ---------- 9. UI evidence: /status JSON + headless screenshot ----------

if step_done ui; then
  log "skip: ui evidence"
else
  log "capturing /status + UI screenshot"
  curl -sf "$WORKER/status" > "$EVIDENCE/status.json"
  curl -sf "$WORKER/checks" > "$EVIDENCE/checks-receipt.json"
  (cd "$ROOT/prototype/ui" && nohup python3 -m http.server "$UI_PORT" --bind 127.0.0.1 \
    > "$LIVE/ui-server.log" 2>&1 &)
  wait_for "http://127.0.0.1:$UI_PORT/index.html" ui-server 30
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
  --live "$LIVE" --evidence "$EVIDENCE" --state "$STATE" | tee "$EVIDENCE/summary.txt"
log "done. evidence in live/evidence/"
