#!/usr/bin/env python3
"""Launch one genuinely bound Opus writing executor; never publish a draft."""
import argparse,datetime,json,os,pathlib,shutil,subprocess,uuid,fcntl
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--date',default=datetime.datetime.now(ZoneInfo('Europe/Berlin')).date().isoformat())
parser.add_argument('--run',action='store_true')
args=parser.parse_args()
day=datetime.date.fromisoformat(args.date).isoformat()
private=ROOT/'.local/journal'/day
private.mkdir(parents=True,exist_ok=True)
meta=ROOT/'website/content/daily'/f'{day}.json'
if meta.exists() and json.loads(meta.read_text()).get('published'):
 print(json.dumps({'status':'already_published','date':day}));raise SystemExit(0)
if not args.run:
 quota=json.loads(subprocess.check_output(['quse','claude','--json'],text=True,timeout=45))['claude']
 remaining=[v['percent_remaining'] for v in quota.get('windows',{}).values() if v.get('percent_remaining') is not None]
 if quota.get('error') or quota.get('status')!='ok' or not remaining or min(remaining)<=0 or quota.get('details',{}).get('limit_reached'):
  raise SystemExit('Claude quota unknown/exhausted; retain last publication')
 (private/'quota.json').write_text(json.dumps(quota))
 with (ROOT/'.local/journal/launch.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  launch=private/'launch.json'
  if launch.exists():
   print(launch.read_text());raise SystemExit(0)
  tag='journal-opus-'+day
  command=['aplexer','start','--workspace',str(ROOT),'--cwd',str(ROOT),'--engine','claude','--tag',tag,'--json','--','python3',str(pathlib.Path(__file__).resolve()),'--date',day,'--run']
  response=subprocess.check_output(command,cwd=ROOT,text=True,timeout=60)
  launch.write_text(response);print(response)
 raise SystemExit(0)

with (private/'writer.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 prompt=f'''You are the dedicated Claude Opus daily writer for Alexey's authorized public Agent Branches journal, not a principal. Read website/editorial/WORKFLOW.md and VISUALS.md, AGENTS public journal section, actual Substack voice guide in ../telegram-writing-assistant/articles/_meta/substack-writing-style.md and two relevant published archive articles. Use stylint --style-guide alexey/voice/formatting/polish, --prompt alexey-brief/alexey-draft/abstract-subject/noun-phrase-smell, and full stylint without ignores. Read latest public research/orchestrator/heartbeat reports, experiment events and latest actual owned project evidence. Compare the previous daily report. Date {day} Europe/Berlin. Produce one reader-facing first-person build log, 700–1100 words, factual concrete short paragraphs, actual changes/failures/corrections/decisions/next experiments. If unchanged say so; don't invent success or drift into marketing. Attribute technical actions to agents. Evidence and as-of/source cutoff explicit. Bounded adoption != market validation; delivery != agreement; claims != independent verification. Link exact public source commit URLs. Private Telegram data is voice context only, never publish corpus or private paths/logs/session IDs/credentials. Output ONLY website/content/daily/{day}.md, {day}.json metadata, {day}.sharetext.txt <=350 chars, and .local/journal/{day}/writer-status.json. Metadata author Alexey Grigorev, actual model Opus identity, title/date/summary/source_cutoff/sources/image/image_alt/published:false. Choose existing illustration website/assets/{day}.png if desktop ImageGen provided it, otherwise approved agent-git-illustration.png, use ../../assets/ paths and team-workflow.svg or a truthful same-style dated diagram provided by desktop. Illustrations conceptual, not measurements. Full stylint must pass; fix prose without erasing meaning. No git commits/push/publication, no other writes, no worker launches, no social posts/purchases. Stop once artifacts/status exist.'''
 (private/'prompt.txt').write_text(prompt)
 claude=shutil.which('claude')
 if not claude:raise SystemExit('Claude CLI unavailable')
 with (private/'response.json').open('w') as out,(private/'stderr.log').open('w') as err:
  try: result=subprocess.run([claude,'--model','opus','--effort','high','--dangerously-skip-permissions','--print','--output-format','json',prompt],cwd=ROOT,stdout=out,stderr=err,timeout=1200)
  except subprocess.TimeoutExpired:
   (private/'exit.json').write_text(json.dumps({'returncode':124,'status':'timeout'}));raise
 (private/'exit.json').write_text(json.dumps({'returncode':result.returncode,'completed':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
 if result.returncode:raise SystemExit(result.returncode)
 response=json.loads((private/'response.json').read_text())
 if response.get('is_error') or not any('opus' in m.lower() for m in response.get('modelUsage',{})):
  raise SystemExit('Actual Opus completion not verified; draft remains unpublished')
 subprocess.run(['stylint',str(ROOT/'website/content/daily'/f'{day}.md')],cwd=ROOT,timeout=60,check=True)
 print(json.dumps({'status':'draft_ready_for_evidence_visual_privacy_review','date':day,'actual_models':list(response['modelUsage'])}))
