#!/usr/bin/env bash
# Interim headless Codex root: one bounded run (quota gate -> codex exec -> summary).
# Single-instance guard: flock on $STATE/root.lock + state.json (run id, pid, pgid,
# start, heartbeat, epoch). Healthy previous run -> skip and leave it a note.
# Stale/over-time previous run -> terminate its process group, record superseded,
# keep its handoff, bump the epoch, run. Replaced later by the agent-hub M4 scheduler
# (alexeygrigorev/agent-hub#6), which should keep these semantics server-side.
# Test knobs: HR_DRY_RUN=<secs> (sleep instead of codex), HR_FREEZE_HEARTBEAT=1.
# Additive Hub binding hooks (agent-hub M4 G8/G7b/G5): optional HR_RUN_ID (host
# pre-assigned, strict path-safe), optional HR_HUB_JOB_ID + HR_HUB_LEASE_EPOCH
# pair (+ HR_HUB_HOST_ID / HR_HUB_LAUNCHER_TASK_ID / HR_HUB_LAUNCHER_UNIT /
# HR_HUB_FIRST_ACTION_FILE / HR_HUB_START_ACK_FILE / HR_PID_NAMESPACE_EXPECTED,
# caller INVOCATION_ID recorded as unverified data). Invalid or half-specified binding fails
# closed (exit 78) before any lock/state mutation. The script stays the only
# owner of root.lock/state.json; hub_* keys are cleared on every run start/end.
# Evidence contract: runs/<id>.started.json is bootstrap evidence (never a first
# tool call); runs/<id>.first-action.json is written only by the native engine
# from its actual first action; runs/<id>.skipped.json marks a requested run
# that did not run because a healthy incumbent holds the lock.
# Hub start ack gate: a Hub-bound run (HR_HUB_JOB_ID set) REQUIRES
# HR_HUB_START_ACK_FILE (exit 78 otherwise). Caller INVOCATION_ID is never
# manager evidence: launcher_invocation_id stays UNKNOWN. The ack must be a
# regular (non-symlink, owner-only-writable) JSON
# object with kind=hub_start_ack carrying every bound field with the exact expected value and type:
# run_id, job_id, hub_lease_epoch, native_epoch plus launcher_task_id / host_id /
# launcher_unit / launcher_invocation_id for every one that is bound. Missing
# fields are 'unbound' (75) and wrong values are 'mismatch' (75). Neither starts
# business execution. Matching caller JSON is only binding evidence: issuer and
# manager authority are not implemented here, so Hub business execution stays
# held. Dry runs may inspect the binding without claiming verified authority.
# A stale takeover only signals a process group whose
# recorded pid namespace and pid start ticks still match the live process.
set -euo pipefail
# --scope inherits caller environment. Drop every raw Hub variable before any
# child starts; public job binding is supplied only through validated HR_HUB_*.
for hub_env_key in ${!HUB_@}; do unset "$hub_env_key"; done

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

CALLER_UMASK=$(umask)
umask 077  # Script-owned state, prompts and receipts stay private.
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
jclear() { # jclear key ... (delete keys from state.json; never leaves stale bindings)
python3 - "$SF" "$@" <<'PY'
import json,os,sys
p=sys.argv[1]
try: d=json.load(open(p))
except Exception: d={}
for k in sys.argv[2:]: d.pop(k,None)
t=p+".tmp%d"%os.getpid(); json.dump(d,open(t,"w"),indent=1); os.replace(t,p)
PY
}

# --- Hub binding / run id validation (additive; fails closed, no mutation) ---
die() { printf 'headless-root-run: %s\n' "$*" >&2; printf '%s refusal: %s\n' "$(ts)" "$*" >>"$LOG" 2>/dev/null || true; exit 78; }
safe_state_path() { # must stay under $STATE, absolute, .json, no '..', no control chars
python3 - "$STATE" "$1" <<'PY'
import os,sys
base=os.path.realpath(sys.argv[1]); p=sys.argv[2]
if p=="": raise SystemExit(0)
if not os.path.isabs(p) or any(ord(c)<32 for c in p) or not p.endswith(".json"): raise SystemExit(1)
if ".." in p.split(os.sep): raise SystemExit(1)
d=os.path.realpath(os.path.dirname(p))
if d!=base and not d.startswith(base+os.sep): raise SystemExit(1)
print(p)
PY
}
HUB_KEYS="hub_job_id hub_lease_epoch hub_host_id launcher_task_id launcher_unit launcher_invocation_id caller_env_invocation_id caller_env_invocation_id_authority"
HUB_JOB_ID=""; HUB_LEASE_EPOCH=""; HUB_HOST_ID=""; HUB_LAUNCHER_TASK_ID=""
HUB_LAUNCHER_UNIT=""; HUB_LAUNCHER_INVOCATION_ID=UNKNOWN
CALLER_ENV_INVOCATION_ID=${INVOCATION_ID:-}  # Unverified caller data under --scope.
unset INVOCATION_ID
HUB_FIRST_ACTION_FILE=""; HUB_START_ACK_FILE=""

RUN_ID=${HR_RUN_ID:-}
[[ -n $RUN_ID ]] || RUN_ID=$(date +%Y%m%dT%H%M%S)-$$
if [[ -n ${HR_RUN_ID:-} && ! $RUN_ID =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]; then
  die "invalid HR_RUN_ID (want ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\$): '$RUN_ID'"
fi
for receipt in "$RUNS/$RUN_ID.started.json" "$RUNS/$RUN_ID.skipped.json"; do
  [[ ! -e $receipt && ! -L $receipt ]] || die "run id collision: $receipt already exists"
done

if [[ -n ${HR_HUB_JOB_ID:-}${HR_HUB_LEASE_EPOCH:-}${HR_HUB_HOST_ID:-}${HR_HUB_LAUNCHER_TASK_ID:-}${HR_HUB_LAUNCHER_UNIT:-}${HR_HUB_FIRST_ACTION_FILE:-}${HR_HUB_START_ACK_FILE:-} ]]; then
  HUB_JOB_ID=${HR_HUB_JOB_ID:-}; HUB_LEASE_EPOCH=${HR_HUB_LEASE_EPOCH:-}
  [[ -n $HUB_JOB_ID ]] || die "hub binding needs HR_HUB_JOB_ID together with HR_HUB_LEASE_EPOCH"
  [[ -n $HUB_LEASE_EPOCH ]] || die "hub binding needs HR_HUB_LEASE_EPOCH together with HR_HUB_JOB_ID"
  [[ $HUB_JOB_ID =~ ^[A-Za-z0-9][A-Za-z0-9._:@+-]{0,127}$ ]] || die "invalid HR_HUB_JOB_ID: '$HUB_JOB_ID'"
  [[ $HUB_LEASE_EPOCH =~ ^[1-9][0-9]{0,18}$ ]] || die "invalid HR_HUB_LEASE_EPOCH (positive integer): '$HUB_LEASE_EPOCH'"
  HUB_HOST_ID=${HR_HUB_HOST_ID:-}
  [[ -z $HUB_HOST_ID || $HUB_HOST_ID =~ ^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$ ]] || die "invalid HR_HUB_HOST_ID: '$HUB_HOST_ID'"
  HUB_LAUNCHER_TASK_ID=${HR_HUB_LAUNCHER_TASK_ID:-}
  [[ -z $HUB_LAUNCHER_TASK_ID || $HUB_LAUNCHER_TASK_ID =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || die "invalid HR_HUB_LAUNCHER_TASK_ID: '$HUB_LAUNCHER_TASK_ID'"
  HUB_LAUNCHER_UNIT=${HR_HUB_LAUNCHER_UNIT:-}
  [[ -z $HUB_LAUNCHER_UNIT || $HUB_LAUNCHER_UNIT =~ ^[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$ ]] || die "invalid HR_HUB_LAUNCHER_UNIT: '$HUB_LAUNCHER_UNIT'"
  HUB_FIRST_ACTION_FILE=$(safe_state_path "${HR_HUB_FIRST_ACTION_FILE:-}") || die "invalid HR_HUB_FIRST_ACTION_FILE (absolute, .json, no '..', under state dir)"
  HUB_START_ACK_FILE=$(safe_state_path "${HR_HUB_START_ACK_FILE:-}") || die "invalid HR_HUB_START_ACK_FILE (absolute, .json, no '..', under state dir)"
  [[ ! -L $HUB_FIRST_ACTION_FILE ]] || die "symlinked HR_HUB_FIRST_ACTION_FILE is refused"
  [[ -n $HUB_START_ACK_FILE ]] || die "hub binding needs HR_HUB_START_ACK_FILE: business execution must wait for a validated Hub start ack"
  # ACK input must never alias script output or a native first-action path.
  if ! python3 - "$STATE" "$RUNS" "$HUB_START_ACK_FILE" "$HUB_FIRST_ACTION_FILE" <<'PY'
import os,sys
base,runs,path,first=map(os.path.realpath,sys.argv[1:])
if path==os.path.realpath(os.path.join(base,"state.json")) or path==runs or path.startswith(runs+os.sep) or (sys.argv[4] and path==first):
    raise SystemExit(1)
PY
  then die "HR_HUB_START_ACK_FILE aliases a reserved output path"; fi

  ACK_WAIT=${HR_HUB_START_ACK_WAIT_SEC:-120}
  [[ $ACK_WAIT =~ ^[0-9]{1,4}$ ]] || die "invalid HR_HUB_START_ACK_WAIT_SEC: '$ACK_WAIT'"
  [[ $WINDOW =~ ^[1-9][0-9]{0,8}$ ]] || die "invalid HR_WINDOW_SEC for Hub ACK bound"
  ACK_WAIT=$((10#$ACK_WAIT))
  (( ACK_WAIT <= WINDOW + GRACE )) || die "HR_HUB_START_ACK_WAIT_SEC exceeds WINDOW+GRACE"
fi
# Caller data is interpolated nowhere; still refuse an odd value before state/receipts.
if [[ -n $CALLER_ENV_INVOCATION_ID && ! $CALLER_ENV_INVOCATION_ID =~ ^[0-9A-Za-z._-]{1,64}$ ]]; then
  die "invalid INVOCATION_ID"
fi

SELF=$(readlink -f "$0" 2>/dev/null || printf '%s' "$0")
PID_NS=$(readlink /proc/self/ns/pid 2>/dev/null || echo unknown)
if [[ -n ${HR_PID_NAMESPACE_EXPECTED:-} && $PID_NS != "${HR_PID_NAMESPACE_EXPECTED}" ]]; then
  die "pid namespace mismatch: expected '$HR_PID_NAMESPACE_EXPECTED', actual '$PID_NS' (private/inner namespace is not host custody safe)"
fi
PID_START_TICKS=$(cut -d')' -f2 "/proc/$$/stat" 2>/dev/null | awk '{print $20}' | tr -d ' ')
[[ $PID_START_TICKS =~ ^[0-9]+$ ]] || PID_START_TICKS=""
DRY=0
if [[ -n ${HR_DRY_RUN:-} ]]; then DRY=1; fi

# Receipts are written 0600, atomically, symlink denied, canonical JSON digest.
fsha() { python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1" 2>/dev/null || echo ""; }

skipped_receipt() { # $1 incumbent run_id $2 hb_age $3 age $4 incumbent status
python3 - "$RUNS/$RUN_ID.skipped.json" "$RUN_ID" "$1" "$2" "$3" "$4" "$SF" "$(ts)" \
    "$HUB_JOB_ID" "$HUB_LEASE_EPOCH" "$HUB_HOST_ID" "$HUB_LAUNCHER_TASK_ID" "$HUB_LAUNCHER_UNIT" "$HUB_LAUNCHER_INVOCATION_ID" "$CALLER_ENV_INVOCATION_ID" <<'PY'
import hashlib,json,os,sys
out,rid,prev,hbage,age,pst,sf,now,job,lep,hid,task,unit,inv,caller_inv=sys.argv[1:]
sb=None
try: sb=hashlib.sha256(open(sf,"rb").read()).hexdigest()
except Exception: pass
p={"schema_version":"1.0","kind":"observed_skip_request","outcome":"skipped",
   "reason":"healthy_incumbent" if pst=="running" else "starting_incumbent",
   "requested_run_id":rid,"requested_at_utc":now,"is_root_cycle":False,"native_epoch":None,
   "job_id":job or None,"hub_lease_epoch":int(lep) if lep else None,
   "host_id":hid or None,"launcher_task_id":task or None,
   "launcher_unit":unit or None,"launcher_invocation_id":inv,
   "caller_env_invocation_id":caller_inv or None,"caller_env_invocation_id_authority":"unverified",
   "incumbent":{"run_id":prev or None,"status":pst,"hb_age_s":int(hbage),"age_s":int(age)},
   "incumbent_state_sha256":sb}
p["digest_algo"]="sha256-canonical-json-v1"
p["digest"]=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(",",":")).encode()).hexdigest()
if os.path.islink(out): raise SystemExit("refusing symlinked receipt path: %s"%out)
t=out+".tmp%d"%os.getpid()
fd=os.open(t,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,"w") as f: json.dump(p,f,indent=1)
try: os.link(t,out,follow_symlinks=False)
finally: os.unlink(t)
PY
}

started_receipt() { # after lock ownership + state write, before any business action
python3 - "$RUNS/$RUN_ID.started.json" "$RUN_ID" "$EPOCH" "$$" "$PGID" "$PID_NS" "$PID_START_TICKS" \
    "${PREV_RUN:-}" "$(hostname)" "$HUB_JOB_ID" "$HUB_LEASE_EPOCH" "$HUB_HOST_ID" "$HUB_LAUNCHER_TASK_ID" \
    "$HUB_LAUNCHER_UNIT" "$HUB_LAUNCHER_INVOCATION_ID" "$START" "$(ts)" "$DRY" "$FIRST_ACTION_FILE" \
    "$SF" "$SELF" "$CALLER_ENV_INVOCATION_ID" <<'PY'
import hashlib,json,os,sys
out,rid,nep,pid,pgid,pns,pst,prev,host,job,lep,hid,task,unit,inv,st,now,dry,fa,sf,selfp,caller_inv=sys.argv[1:]
try: cg=open("/proc/self/cgroup").read()
except Exception: cg=None
p={"schema_version":"1.0","kind":"observed_root_bootstrap","outcome":"started",
   "is_native_first_tool":False,"evidence_class":"bootstrap_only",
   "run_id":rid,"job_id":job or None,"hub_lease_epoch":int(lep) if lep else None,"native_epoch":int(nep),
   "host_id":hid or None,"pid":int(pid),"pgid":int(pgid),"pid_namespace":pns,
   "pid_start_ticks":int(pst) if pst else None,"prev_run":prev or None,"host":host,
   "launcher_task_id":task or None,"launcher_unit":unit or None,"launcher_invocation_id":inv,
   "caller_env_invocation_id":caller_inv or None,"caller_env_invocation_id_authority":"unverified",
   "launcher_unit_in_cgroup":any(line.split(":",2)[-1].rstrip("/").rsplit("/",1)[-1]==unit+".scope"
                                  for line in cg.splitlines()) if (unit and cg is not None) else None,
   "started_at":int(st),"started_at_utc":now,"dry_run":bool(int(dry)),
   "first_action_receipt":fa,
   "first_action_note":"written only by the native engine from its actual first action; never synthesized here",
   "state_sha256":hashlib.sha256(open(sf,"rb").read()).hexdigest(),
   "script_sha256":hashlib.sha256(open(selfp,"rb").read()).hexdigest(),
   "digest_algo":"sha256-canonical-json-v1"}
p["digest"]=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(",",":")).encode()).hexdigest()
if os.path.islink(out): raise SystemExit("refusing symlinked receipt path: %s"%out)
t=out+".tmp%d"%os.getpid()
fd=os.open(t,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,"w") as f: json.dump(p,f,indent=1)
try: os.link(t,out,follow_symlinks=False)
finally: os.unlink(t)
PY
}

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
    skipped_receipt "${prev:-}" "$((n-hb))" "$((n-st))" "${pst:-starting}" || die "skip receipt refused for run=$RUN_ID"
    log "skip: structured skipped outcome for requested run=$RUN_ID -> $RUNS/$RUN_ID.skipped.json"
    exit 0
  fi
  log "takeover: previous run=$prev stale (hb_age=$((n-hb))s age=$((n-st))s) pgid=$pgid; terminating"
  # Never signal a group we cannot prove is the stale run's: same pid namespace,
  # same pid start ticks (no pid reuse) and never our own group or the host's.
  rec_ns=$(jget pid_namespace); rec_ticks=$(jget pid_start_ticks)
  guard=ok
  if [[ -z $rec_ns || ! $rec_ticks =~ ^[0-9]+$ || ! ${ppid_:-} =~ ^[0-9]+$ ]]; then
    # Legacy incumbents lack this evidence. Hold until their own bounded
    # engine timeout releases root.lock; never infer identity or kill Root.
    guard="missing process identity evidence; legacy upgrade held until incumbent self-timeout"
  elif [[ $rec_ns != "$PID_NS" ]]; then
    guard="foreign pid namespace '$rec_ns'"
  elif [[ ! -r /proc/${ppid_}/stat ]]; then
    guard="recorded process identity no longer available"
  else
    live_ns=$(readlink "/proc/${ppid_}/ns/pid" 2>/dev/null || true)
    live_ticks=$(cut -d')' -f2 "/proc/${ppid_}/stat" 2>/dev/null | awk '{print $20}' | tr -d ' ')
    live_pgid=$(ps -o pgid= -p "$ppid_" 2>/dev/null | tr -d ' ')
    if [[ $live_ns != "$PID_NS" ]]; then guard="live process namespace mismatch";
    elif [[ $live_ticks != "$rec_ticks" ]]; then guard="pid ${ppid_} reused (start ticks $live_ticks != $rec_ticks)";
    elif [[ $live_pgid != "$pgid" ]]; then guard="recorded process group mismatch"; fi
  fi
  if [[ $guard == ok ]] && [[ $pgid =~ ^[0-9]+$ ]] && (( pgid > 1 )) && (( pgid != $(ps -o pgid= $$ | tr -d ' ') )); then
    kill -TERM -- "-$pgid" 2>/dev/null || true
    for _ in $(seq 20); do kill -0 -- "-$pgid" 2>/dev/null || break; sleep 1; done
    kill -KILL -- "-$pgid" 2>/dev/null || true
  elif [[ $guard != ok ]]; then
    log "takeover refused to signal pgid=$pgid: $guard (new=$RUN_ID)"
    exit 1
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
for receipt in "$RUNS/$RUN_ID.started.json" "$RUNS/$RUN_ID.skipped.json"; do
  [[ ! -e $receipt && ! -L $receipt ]] || die "run id collision: $receipt already exists"
done
PREV_RUN=$(jget run_id)
EPOCH=$(( $(jget epoch || echo 0) + 1 )) 2>/dev/null || EPOCH=1
START=$(now)
PGID=$(ps -o pgid= $$ | tr -d ' ')
jclear $HUB_KEYS
jset run_id="$RUN_ID" pid=$$ pgid="$PGID" start="$START" heartbeat="$START" \
     epoch="$EPOCH" status=running prev_run="$PREV_RUN" host="$(hostname)" \
     pid_namespace="$PID_NS" pid_start_ticks="$PID_START_TICKS" \
     hub_job_id="$HUB_JOB_ID" hub_lease_epoch="$HUB_LEASE_EPOCH" hub_host_id="$HUB_HOST_ID" \
     launcher_task_id="$HUB_LAUNCHER_TASK_ID" launcher_unit="$HUB_LAUNCHER_UNIT" \
     launcher_invocation_id="$HUB_LAUNCHER_INVOCATION_ID" \
     caller_env_invocation_id="$CALLER_ENV_INVOCATION_ID" caller_env_invocation_id_authority=unverified
log "start run=$RUN_ID epoch=$EPOCH prev=${PREV_RUN:-none} hub_job=${HUB_JOB_ID:-none} lease_epoch=${HUB_LEASE_EPOCH:-none}"

FIRST_ACTION_FILE=${HUB_FIRST_ACTION_FILE:-$RUNS/$RUN_ID.first-action.json}
HUB_ACK_STATE=not_required; HUB_ACK_SHA=""
started_receipt || die "bootstrap receipt refused for run=$RUN_ID"
log "start: structured bootstrap receipt -> $RUNS/$RUN_ID.started.json"

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
# A heartbeat descendant must never keep the caller's stdout/stdin pipes open.
) 9>&- </dev/null >>"$LOG" 2>&1 &
HB=$!
stop_heartbeat() {
  pkill -P "$HB" 2>/dev/null || true
  kill "$HB" 2>/dev/null || true
  wait "$HB" 2>/dev/null || true
}
trap stop_heartbeat EXIT

# Hub-bound runs wait for a genuine validated start acknowledgement before any
# business execution or side effect (fail closed; the timer path never waits).
status=ok; rc=0; gate=""
if [[ -n $HUB_START_ACK_FILE ]]; then
  waited=0; limit=$ACK_WAIT; ack_deadline=$((START+WINDOW+GRACE))
  while [[ ! -f $HUB_START_ACK_FILE && $waited -lt $limit ]] && (( $(now) < ack_deadline )); do
    sleep 1; waited=$((waited+1))
  done
  if [[ ! -f $HUB_START_ACK_FILE ]]; then
    HUB_ACK_STATE=missing; status=hub_start_ack_missing; rc=75
  else
    ack_rc=0
    HUB_ACK_SHA=$(python3 - "$HUB_START_ACK_FILE" "$RUN_ID" "$EPOCH" "$HUB_JOB_ID" "$HUB_LEASE_EPOCH" \
        "$HUB_HOST_ID" "$HUB_LAUNCHER_TASK_ID" "$HUB_LAUNCHER_UNIT" "$HUB_LAUNCHER_INVOCATION_ID" "$STATE" "$RUNS" "$FIRST_ACTION_FILE" <<'PY'

import hashlib,json,os,stat,sys
path,rid,nep,job,lep,hid,task,unit,inv,state,runs,first=sys.argv[1:]
resolved=os.path.realpath(path); runs=os.path.realpath(runs)
if resolved==os.path.realpath(os.path.join(state,"state.json")) or resolved==runs or resolved.startswith(runs+os.sep) or resolved==os.path.realpath(first):
    raise SystemExit(4)
try:
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as f:
        st=os.fstat(f.fileno())
        # File privacy is required; ownership is not proof of a genuine issuer.
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o600: raise SystemExit(4)
        raw=f.read()
        d=json.loads(raw.decode("utf-8"))
except SystemExit: raise
except Exception: raise SystemExit(4)
if not isinstance(d,dict): raise SystemExit(4)
# An ack is only valid when every bound field is PRESENT, of the exact type and
# equal. Checking only the fields that happen to be present would accept {}, an
# unrelated document, or a partial ack as "verified" and let business execution
# start against a start acknowledgement that is bound to nothing.
want=[("kind","hub_start_ack"),("run_id",rid),("job_id",job),("hub_lease_epoch",int(lep)),("native_epoch",int(nep))]
for k,v in (("host_id",hid),("launcher_task_id",task),("launcher_unit",unit),("launcher_invocation_id",inv)):
    if v: want.append((k,v))
for k,v in want:
    if k not in d: raise SystemExit(6)   # unbound/partial acknowledgement
for k,v in want:
    if type(d[k]) is not type(v) or d[k]!=v: raise SystemExit(5)   # present but wrong binding/type
print(hashlib.sha256(raw).hexdigest())
PY
    ) || ack_rc=$?
    case $ack_rc in
      0)
        HUB_ACK_STATE=binding_matched_authority_held
        if [[ $DRY == 0 ]]; then status=hub_start_ack_authority_held; rc=75; fi
        ;;
      5) HUB_ACK_STATE=mismatch; status=hub_start_ack_mismatch; rc=75 ;;
      6) HUB_ACK_STATE=unbound; status=hub_start_ack_unbound; rc=75 ;;
      *) HUB_ACK_STATE=unreadable; status=hub_start_ack_unreadable; rc=75 ;;
    esac
  fi
  if [[ $status != ok ]]; then
    log "hub start ack $HUB_ACK_STATE for run=$RUN_ID job=${HUB_JOB_ID:-none}: refusing business execution"
    printf -- "- %s headless root run %s refused: hub start ack %s (job %s lease %s)\n" "$(ts)" "$RUN_ID" "$HUB_ACK_STATE" "${HUB_JOB_ID:-none}" "${HUB_LEASE_EPOCH:-none}" >>"$STATE/NEEDS-ALEXEY.md"
  fi
fi

# Metrics liveness guard: latest.json older than 10 min -> report + restart the
# experiment-metrics systemd --user unit (scripts/metrics/experiment-metrics.service).
METRICS_LATEST=$REPO/.local/metrics/latest.json
metrics_note="ok"
if [[ -z ${HR_SKIP_METRICS_GUARD:-} && $status == ok ]]; then
  m_age=$(( $(now) - $(stat -c %Y "$METRICS_LATEST" 2>/dev/null || echo 0) ))
  if (( m_age > ${HR_METRICS_STALE_SEC:-600} )); then
    if systemctl --user restart experiment-metrics.service 2>>"$LOG"; then m_act=restarted; else m_act=restart-failed; fi
    metrics_note="STALE latest.json age=${m_age}s; experiment-metrics $m_act"
    log "metrics guard: $metrics_note (run=$RUN_ID)"
    printf -- "- %s metrics collector stale (latest.json %ss old); %s by headless root %s\n" "$(ts)" "$m_age" "$m_act" "$RUN_ID" >>"$STATE/NEEDS-ALEXEY.md"
  fi
fi

if [[ $status == ok ]]; then
  if gate=$(python3 "$REPO/scripts/quota-gate.py" 2>&1); then :; else
    status=quota_held; rc=75
    log "quota gate refused run=$RUN_ID: $gate"
  fi
else
  gate=""
fi

if [[ $status == ok ]]; then
  ctx=$(mktemp)
  {
    cat "$PROMPT"
    printf '\n\n## This run\n\n- run_id: %s\n- epoch: %s\n- started: %s\n- hard stop: %s (finish and write files by then)\n' \
      "$RUN_ID" "$EPOCH" "$(ts)" "$(date -d @$((START+WINDOW-180)) '+%H:%M %Z')"
    printf -- '- write handoff notes to: %s\n- write summary JSON to: %s\n- NEEDS-ALEXEY file: %s/NEEDS-ALEXEY.md\n' "$HANDOFF" "$AGENT_JSON" "$STATE"
    printf -- '- job_id: %s | hub_lease_epoch: %s | native_epoch: %s | pid: %s | pgid: %s | pid_namespace: %s\n' \
      "${HUB_JOB_ID:-none}" "${HUB_LEASE_EPOCH:-none}" "$EPOCH" "$$" "$PGID" "$PID_NS"
    printf -- '- first-action receipt (0600, write it YOURSELF from your real first action): %s\n' "$FIRST_ACTION_FILE"
    printf '  fields: schema_version, kind ("observed_root_bootstrap" if your first action was only reading/bootstrap state, "observed_native_tool" ONLY for a real model tool call), job_id, host_id, hub_lease_epoch, native_epoch, run_id, launcher_task_id, launcher_unit, launcher_invocation_id, observed_at_utc, actual_action, actual_action_digest (sha256 of the actual action text), native_session_id ("UNKNOWN" until your provider really emits it), source_entrypoint_sha256, plus "digest" = sha256 over canonical JSON (sorted keys, "," and ":" separators) of the object without "digest".\n'
    printf '  %s is bootstrap evidence, NOT a first tool call. Never copy a PID into it. This script never writes it for you. If you made no tool call, do not claim kind=observed_native_tool.\n' "$RUNS/$RUN_ID.started.json"
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
    # Keep private output files private, but restore caller code-creation modes.
    : >"$LAST"; : >"$OUT"
    (
      for hub_env_key in ${!HUB_@}; do unset "$hub_env_key"; done
      unset INVOCATION_ID
      umask "$CALLER_UMASK"
      timeout --kill-after=30s "$WINDOW" \
        bash "$REPO/scripts/launch-codex.sh" exec --dangerously-bypass-approvals-and-sandbox \
          --skip-git-repo-check -C "$REPO" -o "$LAST" - <"$ctx" >"$OUT" 2>&1 9>&-
    )
    rc=$?
  fi
  set -e
  rm -f "$ctx"
  case $rc in 0) status=ok ;; 124|137) status=timeout ;; 75) status=quota_held ;; *) status=error ;; esac
fi

END=$(now)
python3 - "$SUMMARY" "$AGENT_JSON" "$RUN_ID" "$EPOCH" "$status" "$rc" "$START" "$END" "$HANDOFF" "${PREV_RUN:-}" \
    "$HUB_JOB_ID" "$HUB_LEASE_EPOCH" "$HUB_HOST_ID" "$HUB_LAUNCHER_TASK_ID" "$HUB_LAUNCHER_UNIT" "$HUB_LAUNCHER_INVOCATION_ID" \
    "$DRY" "$FIRST_ACTION_FILE" "$$" "$PGID" "$PID_NS" "$PID_START_TICKS" "$HUB_ACK_STATE" "$HUB_ACK_SHA" "$CALLER_ENV_INVOCATION_ID" <<'PY'
import json,sys,os
(out,agent,rid,ep,st,rc,s,e,ho,prev,job,lep,hid,task,unit,inv,dry,fa,pid,pgid,pns,pst,acks,acksha,caller_inv)=sys.argv[1:]
d={"run_id":rid,"epoch":int(ep),"status":st,"exit_code":int(rc),"started":int(s),"ended":int(e),
   "duration_s":int(e)-int(s),"prev_run":prev or None,"handoff":ho if os.path.exists(ho) else None,
   "outcome":st,"native_epoch":int(ep),
   "hub_binding":({"job_id":job or None,"hub_lease_epoch":int(lep) if lep else None,"host_id":hid or None,
                   "launcher_task_id":task or None,"launcher_unit":unit or None,
                   "launcher_invocation_id":inv or None} if job else None),
   "pid":int(pid),"pgid":int(pgid),"pid_namespace":pns,"pid_start_ticks":int(pst) if pst else None,
   "launcher_invocation_id":"UNKNOWN","caller_env_invocation_id":caller_inv or None,
   "caller_env_invocation_id_authority":"unverified",
   "dry_run":bool(int(dry)),"genuine_root_cycle":(False if int(dry) else "UNKNOWN"),
   "native_session":None,"first_action_receipt":fa if os.path.exists(fa) else None,
   "first_action_observed":False,"first_action_receipt_present":os.path.exists(fa),
   "hub_start_ack":({"path":None,"state":acks,"verified":False,"binding_matched":acks=="binding_matched_authority_held",
                     "issuer_authority":"UNKNOWN","manager_authority":"UNKNOWN","sha256":acksha or None}
                     if acks!="not_required" else None)}
try: d["agent"]=json.load(open(agent))
except Exception: d["agent"]=None
json.dump(d,open(out,"w"),indent=1)
PY
if [[ $(jget run_id) == "$RUN_ID" ]]; then
  jset status=finished end="$END" result="$status"
  jclear $HUB_KEYS   # never leave a stale hub binding behind (G7b)
fi
log "end run=$RUN_ID status=$status rc=$rc dur=$((END-START))s summary=$SUMMARY"
if [[ $status == timeout || $status == error ]] && [[ -z ${HR_DRY_RUN:-} ]]; then
  printf -- "- %s headless root run %s ended %s (rc=%s); see %s\n" "$(ts)" "$RUN_ID" "$status" "$rc" "$OUT" >>"$STATE/NEEDS-ALEXEY.md"
fi
exit 0
