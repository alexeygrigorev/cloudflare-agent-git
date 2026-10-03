#!/usr/bin/env python3
"""Register exact provider metadata for otherwise unobservable harness agents."""
import argparse, datetime, fcntl,json,os,pathlib
STORE=pathlib.Path(__file__).resolve().parents[2]/'.local/metrics';STORE.mkdir(parents=True,exist_ok=True)
ap=argparse.ArgumentParser();ap.add_argument('--event-id',required=True);ap.add_argument('--conversation-id',required=True);ap.add_argument('--tag',required=True);ap.add_argument('--team-id',required=True);ap.add_argument('--provider',required=True);ap.add_argument('--model',required=True);ap.add_argument('--input-tokens',type=int);ap.add_argument('--output-tokens',type=int);ap.add_argument('--cached-input-tokens',type=int);ap.add_argument('--total-tokens',type=int,required=True);args=ap.parse_args()
if any(v is not None and v<0 for k,v in vars(args).items() if k.endswith('tokens')):raise SystemExit('Token counters must be nonnegative')
row={**vars(args),'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'cumulative','source':'owner-registered provider metadata; not independently verified','cost_usd':None}
path=STORE/'usage-events.jsonl'
with (STORE/'usage-events.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 if path.exists():
  if path.stat().st_size>16*1024*1024:raise SystemExit('Usage metadata cap reached; preserve data and arrange reviewed archive')
  for line in path.open():
   try: old=json.loads(line)
   except ValueError:continue
   if old.get('event_id')==args.event_id:
    comparable={k:old.get(k) for k in vars(args)}
    if comparable!=vars(args):raise SystemExit('Stable event ID conflicts with different counters/identity')
    print('already-recorded');raise SystemExit(0)
 with path.open('a') as f:f.write(json.dumps(row)+'\n')
 path.chmod(0o600)
print('recorded')
