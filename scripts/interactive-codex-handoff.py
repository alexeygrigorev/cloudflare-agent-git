#!/usr/bin/env python3
"""Wait for the existing writer to finish, then resume its transcript in a real UI."""
import json,pathlib,subprocess,time,datetime
r=pathlib.Path('/home/alexey/git/cloudflare-agent-git')
old='338df944-a3fc-4973-9ed0-17708c73769c'
conversation='01a0fdd7-109e-7972-9199-e082a7a1383d'
def rows():return json.loads(subprocess.check_output(['aplexer','list','--json'],text=True))
deadline=time.monotonic()+1200
while time.monotonic()<deadline:
 active=[s for s in rows() if s.get('workspace')==str(r) and s.get('tag')=='codex-principal']
 if any(s['id']!=old for s in active):
  print('A replacement principal already exists; no duplicate launch.',flush=True);break
 if not active:
  prompt='The human clarified that these must be normal interactive aplexer sessions. Your previous headless turn has finished; this is the same resumed conversation. Read experiment/USER-INSTRUCTIONS.md message14, coordination/USER-STEERING.md, RESOURCE-POLICY.md, your coordination and native inbox. Continue from published research and all five completed Pro outputs. Preserve broad20-to6 exploration with real viability gates and separate principal digest approvals; no invented consensus. Claude principal now exists as a resumed interactive UI and is available for a compact focused challenge when evidence ready, not continuous Claude implementation. Prefer genuinely bound z.ai teams, disk budget512MiB/floor8GiB and Codex15%remaining gate. Coordinate autonomously with peers and save incremental work. Never reintroduce headless principal loops or status injection. coordination/codex.stop is obsolete headless-loop migration marker, not project completion. Advance pending tests and evidence now, then document the next autonomous milestone. No duplicate principals or inherited helper mailbox authority.'
  cmd=['aplexer','start','--workspace',str(r),'--cwd',str(r),'--tag','codex-principal','--engine','codex','--json','--','bash','scripts/launch-codex.sh','resume',conversation,'--dangerously-bypass-approvals-and-sandbox',prompt]
  done=subprocess.run(cmd,text=True,capture_output=True)
  (r/'.local/interactive-codex-launch.json').write_text(done.stdout)
  if done.returncode:print('Launch failed; inspect private diagnostics.',flush=True)
  else:print('Interactive Codex resume launched after old writer exited; confirm actual UI.',flush=True)
  (r/'.local/interactive-codex-launch-error.log').write_text(done.stderr)
  break
 time.sleep(10)
else:
 (r/'coordination/interactive-handoff-runtime.md').write_text('Old Codex writer did not exit within20minutes. No interrupt or duplicate launch was performed. Orchestrator must inspect checkpoint and finish safe interactive handoff.\n')
 print('Handoff remains pending; no duplicate writer.',flush=True)
