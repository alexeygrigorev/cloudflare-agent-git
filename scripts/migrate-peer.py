import pathlib,json,subprocess,time,sys
r=pathlib.Path('/home/alexey/git/cloudflare-agent-git')
role=sys.argv[1]
spec={
 'grok':('grok-head','3b664830-1a4f-4f30-ba94-67828f32021c','grok',['grok','--cwd',str(r),'--resume','01a0fe00-6ecd-7c73-a852-e9862578d192']),
 'antigravity':('antigravity-head','2bb80c81-0c15-4577-8ba7-27e56a3c98ec','antigravity',['agy','--conversation','245c7bba-9a7b-45c1-87a7-4537f289f9a5','--dangerously-skip-permissions']),
 'zcode':('zcode-independent','d54c1e11-6ce5-4f5a-b989-15ea2f6b013d','zcodex',['zcodex','resume','01a0fdfd-a2aa-7200-bea3-b66a0e369078','--dangerously-bypass-approvals-and-sandbox'])}
tag,old,engine,args=spec[role]
prompt='Normal interactive session requested by human message14. Resume your checkpoint and genuinely bound peer identity; read USER-INSTRUCTIONS, USER-STEERING, RESOURCE-POLICY, your coordination and actual inbox. Continue independent comparative validation and peer challenge from saved evidence; broad20-to6 plus identical-digest principal approvals remain open, no invented agreement. Prefer scoped genuinely-bound z.ai execution teams.512MiB incremental spike budget, stop growth below8GiB free; no purchases, credentials changes, global installs, existing-worktree deletion or realCodex bypass. All five completed Pro reports already published. No more headless head loops/status injection. Stop marker is obsolete migration marker, not project completion. Work autonomously on next concrete falsification tests and help principals organize actual live-agent viability gates; do not defer useful local experiments toOct5 merely because planning dates exist. Record outcomes and send real progress/challenges to desktop-orchestrator; continue until assigned bounded milestone complete.'
(r/f'coordination/{role}.stop').write_text('Normal interactive migration; no headless relaunch.\n')
deadline=time.monotonic()+1200
while time.monotonic()<deadline:
 rows=json.loads(subprocess.check_output(['aplexer','list','--json']))
 active=[s for s in rows if s.get('workspace')==str(r) and s.get('tag')==tag and s.get('phase')=='running']
 if any(s['id']!=old for s in active): print('Replacement already running.',flush=True);break
 if active:
  pid=active[0]['workload_pid'];children=[]
  for p in pathlib.Path('/proc').glob('[0-9]*'):
   try:
    stat=(p/'stat').read_text().rsplit(')',1)[1].split()
    if int(stat[1])==pid and stat[0]!='Z':children.append((p/'comm').read_text().strip())
   except (OSError,ValueError):pass
  # Headless model has exited; only cached supervisor/sleep can be retired.
  if children and all(x=='sleep' for x in children):
   subprocess.run(['aplexer','kill',old,'--signal','TERM','--json'],check=True)
   time.sleep(1);continue
  time.sleep(10);continue
 quota=subprocess.run(['quse',{'antigravity':'gemini','zcode':'zai'}.get(role,role),'--json'],capture_output=True,text=True)
 try:q=json.loads(quota.stdout); obj=next(iter(q.values()));assert obj.get('status')=='ok' and not obj.get('error') and not obj.get('details',{}).get('limit_reached')
 except Exception:print('Fresh provider quota unknown/denied; no launch.',flush=True);break
 launch=args+(['--prompt-interactive',prompt] if role=='antigravity' else [prompt])
 out=subprocess.run(['aplexer','start','--workspace',str(r),'--cwd',str(r),'--tag',tag,'--engine',engine,'--json','--',*launch],text=True,capture_output=True)
 (r/f'.local/interactive-{role}-launch.json').write_text(out.stdout)
 (r/f'.local/interactive-{role}-error.log').write_text(out.stderr)
 print('Interactive launch dispatched; verify actual UI.' if not out.returncode else 'Launch failed.',flush=True);break
else:print('No safe checkpoint within20min. No forced kill or duplicate.',flush=True)
