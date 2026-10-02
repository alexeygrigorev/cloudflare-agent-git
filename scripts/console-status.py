#!/usr/bin/env python3
"""Output-only progress mirror for headless sessions; never sends PTY input."""
import datetime, json, os, pathlib, subprocess, time
root=pathlib.Path('/home/alexey/git/cloudflare-agent-git')
roles={'claude-principal':'claude','codex-principal':'codex','grok-head':'grok','antigravity-head':'antigravity','space-bunny-head':'space-bunny','muse-reviewer':'muse','zcode-independent':'zcode'}
bindings={}
while not (root/'.local/console-status.stop').exists():
 try:
  rows=json.loads(subprocess.run(['aplexer','list','--json'],capture_output=True,text=True,check=True,timeout=15).stdout)
  stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
  dashboard=[f'Cloudflare agent experiment | {stamp}', 'Visible progress from durable artifacts; no input injection.']
  for row in rows:
   tag=row.get('tag');role=roles.get(tag)
   if not role or row.get('workspace')!=str(root): continue
   pid=row.get('workload_pid')
   proc=pathlib.Path(f'/proc/{pid}')
   # Record/check kernel starttime to prevent forwarding to a reused process ID.
   start=(proc/'stat').read_text().rsplit(')',1)[1].split()[19]
   if tag in bindings and bindings[tag]!=(pid,start): continue
   bindings[tag]=(pid,start)
   files=list((root/'research'/role).rglob('*.md')) if (root/'research'/role).exists() else []
   if role=='zcode': files=list((root/'research/zcode').rglob('*.md'))
   latest=max(files,key=lambda p:p.stat().st_mtime) if files else None
   owned=root/f'coordination/{role}.md'
   summary=[f'[{stamp}] {tag}: {row.get("phase")} / {row.get("reported_state") or "state unavailable"}',f'Research documents: {len(files)} | latest: {latest.relative_to(root) if latest else "none yet"}',f'Coordination: {owned.relative_to(root)}' if owned.exists() else 'Coordination output pending', 'Agent tool logs are private in .local/. This session runs headless; an empty composer is expected.']
   text='\n'.join(summary)+'\n\n'
   try:
    fd=os.open(proc/'fd/1',os.O_WRONLY|os.O_NOCTTY)
    try: os.write(fd,text.encode())
    finally: os.close(fd)
   except OSError: pass
   dashboard.append(summary[0]+f' | docs={len(files)}')
  print('\n'.join(dashboard)+'\n',flush=True)
 except Exception as exc:
  print(f'Status refresh failed: {type(exc).__name__}',flush=True)
 time.sleep(45)
