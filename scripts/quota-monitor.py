#!/usr/bin/env python3
"""Pause next Codex rounds at the reserve, without killing active work."""
import datetime, importlib.util, json, pathlib, subprocess, time
root=pathlib.Path('/home/alexey/git/cloudflare-agent-git')
spec=importlib.util.spec_from_file_location('gate',root/'scripts/quota-gate.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
prefix='QUOTA-POLICY-PAUSE: '
while not (root/'.local/quota-monitor.stop').exists():
 try:
  raw=subprocess.run(['quse','codex','--json'],capture_output=True,text=True,check=True,timeout=45)
  record=json.loads(raw.stdout).get('codex',{})
  allowed,reason=gate.decision(record)
 except Exception as exc:
  allowed,reason=False,f'quota unavailable ({type(exc).__name__})'
 status={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'provider':'codex','launch_allowed':allowed,'reason':reason}
 (root/'.local/codex-quota-status.json').write_text(json.dumps(status,indent=2))
 for suffix in ['done','stop']:
  flag=root/f'coordination/codex.{suffix}'
  if not allowed:
   if not flag.exists() or flag.read_text().startswith(prefix): flag.write_text(prefix+reason+'\n')
  elif flag.exists() and flag.read_text().startswith(prefix):
   flag.unlink()
 print(json.dumps(status),flush=True)
 time.sleep(60)
