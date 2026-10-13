#!/usr/bin/env bash
# Interim headless Codex root: one bounded run (quota gate -> codex exec -> summary).
# Single-instance guard: flock on $STATE/root.lock + state.json (run id, pid, pgid,
# start, heartbeat, epoch). Healthy previous run -> skip and leave it a note.
# Stale/over-time previous run -> terminate its process group, record superseded,
# keep its handoff, bump the epoch, run. Replaced later by the agent-hub M4 scheduler
# (alexeygrigorev/agent-hub#6), which should keep these semantics server-side.
# Test knobs: HR_DRY_RUN=<secs> (sleep instead of codex), HR_FREEZE_HEARTBEAT=1.
set -euo pipefail

REPO=${HR_REPO:-$HOME/git/cloudflare-agent-git}
STATE=${HR_STATE:-$HOME/.local/state/headless-root}
RUNS=$STATE/runs
LOCK=$STATE/root.lock
SF=$STATE/state.json
LOG=$STATE/root.log
PROMPT=${HR_PROMPT:-$REPO/scripts/root/root-prompt.txt}
WINDOW=${HR_WINDOW_SEC:-1500}      # 25 min hard timeout
HB_STALE=${HR_HB_STALE_SEC:-180}   # heartbeat older than this = stale
GRACE=120

# Own process group so a successor can terminate the whole run.
if [[ -z ${HR_IN_PGRP:-} ]]; then
  export HR_IN_PGRP=1
  exec setsid -w "$0" "$@"
fi

mkdir -p "$RUNS"
ts() { date "+%Y-%m-%dT%H:%M:%S%z"; }
log() { printf "%s %s\n" "$(ts)" "$*" >>"$LOG"; }
now() { date +%s; }
jget() { python3 - "$SF" "$1" <<'PY' 2>/dev/null || true
import json,sys
try: print(json.load(open(sys.argv[1])).get(sys.argv[2],""))
except Exception: pass
PY
}
jset() { # jset key=value ... (atomic merge into state.json)
python3 - "$SF" "$@" <<'PY'
import json,os,sys
p=sys.argv[1]
try: d=json.load(open(p))
except Exception: d={}
for kv in sys.argv[2:]:
    k,v=kv.split("=",1)
    d[k]=int(v) if v.lstrip("-").isdigit() else v
t=p+".tmp%d"%os.getpid(); json.dump(d,open(t,"w"),indent=1); os.replace(t,p)
PY
}

RUN_ID=$(date +%Y%m%dT%H%M%S)-$$
exec 9>>"$LOCK"

if ! flock -n 9; then
  prev=$(jget run_id); ppid_=$(jget pid); pgid=$(jget pgid)
  hb=$(jget heartbeat); st=$(jget start)
  hb=${hb:-0}; st=${st:-0}; n=$(now)
  pst=$(jget status)
  if [[ $pst != running ]] || { (( n - hb < HB_STALE && n - st < WINDOW + GRACE )) && kill -0 "${ppid_:-0}" 2>/dev/null; }; then
    # Holder is healthy, or still starting up (state not yet written).
    [[ $pst == running ]] || prev=${prev:-starting}
    log "skip: previous root healthy run=$prev hb_age=$((n-hb))s age=$((n-st))s (new=$RUN_ID)"
    printf -- "- %s run %s started and skipped: you were healthy (hb %ss old).\n" "$(ts)" "$RUN_ID" "$((n-hb))" >>"$RUNS/$prev.inbox.md"
    exit 0
  fi
  log "takeover: previous run=$prev stale (hb_age=$((n-hb))s age=$((n-st))s) pgid=$pgid; terminating"
  if [[ -n $pgid && $pgid -gt 1 ]]; then
    kill -TERM -- "-$pgid" 2>/dev/null || true
    for _ in $(seq 20); do kill -0 -- "-$pgid" 2>/dev/null || break; sleep 1; done
    kill -KILL -- "-$pgid" 2>/dev/null || true
  fi
  flock -w 30 9 || { log "takeover failed: lock still held after kill (new=$RUN_ID)"; exit 1; }
  printf '{"run_id":"%s","status":"superseded","superseded_by":"%s","at":"%s"}\n' "$prev" "$RUN_ID" "$(ts)" >"$RUNS/$prev.superseded.json"
  log "superseded run=$prev by $RUN_ID"
else
  # Lock free: a previous run that never reached 'finished' crashed.
  prev=$(jget run_id); pst=$(jget status)
  if [[ -n $prev && $pst == running ]]; then
    log "previous run=$prev ended without finishing (crashed); handoff kept"
    printf '{"run_id":"%s","status":"crashed","seen_by":"%s"}\n' "$prev" "$RUN_ID" >"$RUNS/$prev.superseded.json"
  fi
fi

# We own the lock.
PREV_RUN=$(jget run_id)
EPOCH=$(( $(jget epoch || echo 0) + 1 )) 2>/dev/null || EPOCH=1
START=$(now)
jset run_id="$RUN_ID" pid=$$ pgid="$(ps -o pgid= $$ | tr -d ' ')" start="$START" heartbeat="$START" \
     epoch="$EPOCH" status=running prev_run="$PREV_RUN" host="$(hostname)"
log "start run=$RUN_ID epoch=$EPOCH prev=${PREV_RUN:-none}"

HANDOFF=$RUNS/$RUN_ID.handoff.md
AGENT_JSON=$RUNS/$RUN_ID.agent.json
SUMMARY=$RUNS/$RUN_ID.json
LAST=$RUNS/$RUN_ID.last.txt
OUT=$RUNS/$RUN_ID.codex.log

(
  while sleep 60; do
    [[ $(jget run_id) == "$RUN_ID" ]] || { log "fenced: state now owned by $(jget run_id); stopping run=$RUN_ID"; kill -TERM -- "-$(ps -o pgid= $$ | tr -d ' ')"; exit; }
    [[ -n ${HR_FREEZE_HEARTBEAT:-} ]] || jset heartbeat="$(now)"
  done
) 9>&- &
HB=$!
trap 'pkill -P $HB 2>/dev/null; kill $HB 2>/dev/null || true' EXIT

# Metrics liveness guard: latest.json older than 10 min -> report + restart the
# experiment-metrics systemd --user unit (scripts/metrics/experiment-metrics.service).
METRICS_LATEST=$REPO/.local/metrics/latest.json
metrics_note="ok"
if [[ -z ${HR_SKIP_METRICS_GUARD:-} ]]; then
  m_age=$(( $(now) - $(stat -c %Y "$METRICS_LATEST" 2>/dev/null || echo 0) ))
  if (( m_age > ${HR_METRICS_STALE_SEC:-600} )); then
    if systemctl --user restart experiment-metrics.service 2>>"$LOG"; then m_act=restarted; else m_act=restart-failed; fi
    metrics_note="STALE latest.json age=${m_age}s; experiment-metrics $m_act"
    log "metrics guard: $metrics_note (run=$RUN_ID)"
    printf -- "- %s metrics collector stale (latest.json %ss old); %s by headless root %s\n" "$(ts)" "$m_age" "$m_act" "$RUN_ID" >>"$STATE/NEEDS-ALEXEY.md"
  fi
fi

status=ok; rc=0; gate=""
if gate=$(python3 "$REPO/scripts/quota-gate.py" 2>&1); then :; else
  status=quota_held; rc=75
  log "quota gate refused run=$RUN_ID: $gate"
fi

if [[ $status == ok ]]; then
  ctx=$(mktemp)
  {
    cat "$PROMPT"
    printf '\n\n## This run\n\n- run_id: %s\n- epoch: %s\n- started: %s\n- hard stop: %s (finish and write files by then)\n' \
      "$RUN_ID" "$EPOCH" "$(ts)" "$(date -d @$((START+WINDOW-180)) '+%H:%M %Z')"
    printf -- '- write handoff notes to: %s\n- write summary JSON to: %s\n- NEEDS-ALEXEY file: %s/NEEDS-ALEXEY.md\n' "$HANDOFF" "$AGENT_JSON" "$STATE"
    printf -- '- quota gate: %s\n' "$gate"
    printf -- '- metrics collector: %s\n' "$metrics_note"
    printf '\n## Previous run handoff (%s)\n\n' "${PREV_RUN:-none}"
    if [[ -n $PREV_RUN && -f $RUNS/$PREV_RUN.handoff.md ]]; then cat "$RUNS/$PREV_RUN.handoff.md"; else echo "(none)"; fi
    [[ -f $RUNS/$PREV_RUN.superseded.json ]] && { echo; echo "Previous run outcome:"; cat "$RUNS/$PREV_RUN.superseded.json"; }
    [[ -f $RUNS/$PREV_RUN.inbox.md ]] && { echo; echo "Notes left for the previous run:"; cat "$RUNS/$PREV_RUN.inbox.md"; }
    printf '\n## Open NEEDS-ALEXEY items\n\n'
    [[ -s $STATE/NEEDS-ALEXEY.md ]] && tail -c 4000 "$STATE/NEEDS-ALEXEY.md" || echo "(none)"
  } >"$ctx"
  cp "$ctx" "$RUNS/$RUN_ID.prompt.md"
  set +e
  if [[ -n ${HR_DRY_RUN:-} ]]; then
    sleep "$HR_DRY_RUN" & wait $!; rc=$?
    echo "dry run" >"$LAST"
  else
    timeout --kill-after=30s "$WINDOW" \
      bash "$REPO/scripts/launch-codex.sh" exec --dangerously-bypass-approvals-and-sandbox \
        --skip-git-repo-check -C "$REPO" -o "$LAST" - <"$ctx" >"$OUT" 2>&1 9>&-
    rc=$?
  fi
  set -e
  rm -f "$ctx"
  case $rc in 0) status=ok ;; 124|137) status=timeout ;; 75) status=quota_held ;; *) status=error ;; esac
fi

END=$(now)
python3 - "$SUMMARY" "$AGENT_JSON" "$RUN_ID" "$EPOCH" "$status" "$rc" "$START" "$END" "$HANDOFF" "${PREV_RUN:-}" <<'PY'
import json,sys,os
out,agent,rid,ep,st,rc,s,e,ho,prev=sys.argv[1:]
d={"run_id":rid,"epoch":int(ep),"status":st,"exit_code":int(rc),"started":int(s),"ended":int(e),
   "duration_s":int(e)-int(s),"prev_run":prev or None,"handoff":ho if os.path.exists(ho) else None}
try: d["agent"]=json.load(open(agent))
except Exception: d["agent"]=None
json.dump(d,open(out,"w"),indent=1)
PY
if [[ $(jget run_id) == "$RUN_ID" ]]; then jset status=finished end="$END" result="$status"; fi
log "end run=$RUN_ID status=$status rc=$rc dur=$((END-START))s summary=$SUMMARY"
if [[ $status == timeout || $status == error ]] && [[ -z ${HR_DRY_RUN:-} ]]; then
  printf -- "- %s headless root run %s ended %s (rc=%s); see %s\n" "$(ts)" "$RUN_ID" "$status" "$rc" "$OUT" >>"$STATE/NEEDS-ALEXEY.md"
fi
exit 0
