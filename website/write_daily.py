#!/usr/bin/env python3
"""Launch one genuinely bound Opus writing executor; never publish a draft."""
import argparse,datetime,json,os,pathlib,shutil,subprocess,uuid,fcntl
from zoneinfo import ZoneInfo

ROOT=pathlib.Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--date',default=datetime.datetime.now(ZoneInfo('Europe/Berlin')).date().isoformat())
parser.add_argument('--fact-packet',default=None,help='Path to verified fact packet brief')
parser.add_argument('--correction-token',default=None,help='Authorized correction token to execute rewrite in dedicated directory')
parser.add_argument('--run',action='store_true')
args=parser.parse_args()
day=datetime.date.fromisoformat(args.date).isoformat()
private=ROOT/'.local/journal'/(f'correction-{day}' if args.correction_token else day)
private.mkdir(parents=True,exist_ok=True)
meta=ROOT/'website/content/daily'/f'{day}.json'
m=json.loads(meta.read_text()) if meta.exists() else {}
response=private/'response.json'
if not args.correction_token and m.get('published') and not m.get('early_update') and response.exists():
 try:
  runtime=json.loads(response.read_text())
  if not runtime.get('is_error') and any('opus' in str(x).lower() for x in runtime.get('modelUsage', {})):
   print(json.dumps({'status':'already_published','date':day}));raise SystemExit(0)
 except (json.JSONDecodeError, OSError):
  pass
if not args.run:
 quota=json.loads(subprocess.check_output(['quse','claude','--json'],text=True,timeout=45))['claude']
 remaining=[v['percent_remaining'] for v in quota.get('windows',{}).values() if v.get('percent_remaining') is not None]
 if quota.get('error') or quota.get('status')!='ok' or not remaining or min(remaining)<=0 or quota.get('details',{}).get('limit_reached'):
  raise SystemExit('Claude quota unknown/exhausted; retain last publication')
 (private/'quota.json').write_text(json.dumps(quota))
 lock_path=ROOT/'.local/journal'/(f'launch-corr-{day}.lock' if args.correction_token else 'launch.lock')
 with lock_path.open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  launch=private/'launch.json'
  if launch.exists():
   print(launch.read_text());raise SystemExit(0)
  tag=('journal-opus-corr-' if args.correction_token else 'journal-opus-')+day
  cmd_args=['python3',str(pathlib.Path(__file__).resolve()),'--date',day,'--run']
  if args.fact_packet: cmd_args.extend(['--fact-packet',str(args.fact_packet)])
  if args.correction_token: cmd_args.extend(['--correction-token',str(args.correction_token)])
  command=['aplexer','start','--workspace',str(ROOT),'--cwd',str(ROOT),'--engine','claude','--tag',tag,'--json','--']+cmd_args
  response=subprocess.check_output(command,cwd=ROOT,text=True,timeout=60)
  launch.write_text(response);print(response)
 raise SystemExit(0)

with (private/'writer.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 day_num=(datetime.date.fromisoformat(day)-datetime.date(2026,10,2)).days
 candidates=[
  pathlib.Path(args.fact_packet) if args.fact_packet else None,
  ROOT/'.local/journal/opus-writer'/f'{day}-FACT-PACKET.md',
  ROOT/'.local/journal/opus-writer'/f'DAY{day_num}-FACT-PACKET.md',
  private/'FACT-PACKET.md',
 ]
 fact_file=next((p for p in candidates if p and p.exists()), ROOT/'.local/journal/opus-writer'/f'DAY{day_num}-FACT-PACKET.md')
 fact_ref=str(fact_file.relative_to(ROOT)) if fact_file.is_relative_to(ROOT) else str(fact_file)
 standup_ref='the founder journal (_docs/founder-journal/) and the GitHub issues closed or updated that day'
 prompt=f'''You are the dedicated Claude Opus daily writer for Alexey's authorized public Agent Branches journal, not a principal. First read _docs/03-team/writer.md and follow it; it overrides any conflicting instruction below. Then read the AGENTS public journal section, the actual Substack voice guide in ../telegram-writing-assistant/articles/_meta/substack-writing-style.md and two relevant published archive articles. Read {fact_ref} for the verified factual brief and boundaries, and {standup_ref} for what happened that day. Use stylint --style-guide alexey/voice/formatting/polish, --prompt alexey-brief/alexey-draft/abstract-subject/noun-phrase-smell, and full stylint without ignores. Read the GitHub issues and agents bus history for that day and the latest actual owned project evidence. Compare the previous daily report. Date {day} Europe/Berlin. Produce one reader-facing first-person build log, 600–900 words, factual concrete short paragraphs, actual changes/failures/decisions/next experiments. If unchanged say so; don't invent success or drift into marketing. Attribute technical actions to agents. Keep source_cutoff in metadata only, never in the article. Bounded adoption != market validation; delivery != agreement; claims != independent verification. Link exact public source commit URLs. Private Telegram data is voice context only, never publish corpus or private paths/logs/session IDs/credentials. Output ONLY website/content/daily/{day}.md, {day}.json metadata, {day}.sharetext.txt <=350 chars, .local/journal/{day}/writer-status.json, the private X and LinkedIn summary .local/journal/{day}/social.md as the skill describes, section illustrations as website/assets/{day}-*.png/.svg (diagrams, charts, real screenshots) and their diagram sources under website/editorial/diagrams/{day}/. Metadata author Alexey Grigorev, actual model Opus identity, title/date/summary/source_cutoff/sources/image/image_alt/published:false. Choose existing illustration website/assets/{day}.png if desktop ImageGen provided it, otherwise approved agent-git-illustration.png, use ../../assets/ paths and embed team-workflow.svg or a truthful same-style dated diagram provided by desktop as an image, never as a link. Every section needs at least one embedded illustration; numbers go in charts. Full stylint must pass; fix prose without erasing meaning. No git commits/push/publication, no writes outside those paths, no worker launches, no social posts/purchases. Stop once artifacts/status exist.'''
 (private/'prompt.txt').write_text(prompt)
 claude=shutil.which('claude')
 if not claude:raise SystemExit('Claude CLI unavailable')
 with (private/'response.json').open('w') as out,(private/'stderr.log').open('w') as err:
  try: result=subprocess.run([claude,'--model','opus','--effort','high','--dangerously-skip-permissions','--print','--output-format','json',prompt],cwd=ROOT,stdout=out,stderr=err,timeout=1800)
  except subprocess.TimeoutExpired:
   (private/'exit.json').write_text(json.dumps({'returncode':124,'status':'timeout'}));raise
 (private/'exit.json').write_text(json.dumps({'returncode':result.returncode,'completed':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
 if result.returncode:raise SystemExit(result.returncode)
 response=json.loads((private/'response.json').read_text())
 if response.get('is_error') or not any('opus' in m.lower() for m in response.get('modelUsage',{})):
  raise SystemExit('Actual Opus completion not verified; draft remains unpublished')
 # Step 2: a fresh Opus session checks the draft and rewrites only what fails.
 check_prompt=f'''You are the Claude Opus check pass for the {day} daily report of Alexey's public Agent Branches journal. A separate Opus session just wrote website/content/daily/{day}.md, {day}.json and {day}.sharetext.txt. First read _docs/03-team/writer.md. Then check the draft against every rule in it and against the facts: open every source the article links or cites, plus {fact_ref} and {standup_ref}, and confirm each claim and number, including in .local/journal/{day}/social.md. Also check the story arc, problem/blocker/solution per section, at least one embedded illustration per section (render the page with python3 website/build.py --output into a scratch directory under .local/journal/{day}/ and look at the images), numbers shown as charts, no timestamps or meta, no bold, plain language for a newcomer. If you find problems, fix them yourself by rewriting the affected text, metadata, share text or illustrations, then run full stylint without ignores until it passes. If everything holds, change nothing. Write .local/journal/{day}/check.json with keys problems_found (list of short strings), rewritten (bool) and verdict ("pass" or "fixed"). Same write limits as the writer: only the daily files, website/assets/{day}-*, website/editorial/diagrams/{day}/ and .local/journal/{day}/. No git commits, push, publication or worker launches.'''
 (private/'check-prompt.txt').write_text(check_prompt)
 with (private/'check-response.json').open('w') as out,(private/'check-stderr.log').open('w') as err:
  check=subprocess.run([claude,'--model','opus','--effort','high','--dangerously-skip-permissions','--print','--output-format','json',check_prompt],cwd=ROOT,stdout=out,stderr=err,timeout=1200)
 if check.returncode:raise SystemExit(check.returncode)
 checked=json.loads((private/'check-response.json').read_text())
 if checked.get('is_error') or not any('opus' in m.lower() for m in checked.get('modelUsage',{})):
  raise SystemExit('Actual Opus check pass not verified; draft remains unpublished')
 if not (private/'check.json').exists():raise SystemExit('Check pass wrote no check.json; draft remains unpublished')
 subprocess.run(['stylint',str(ROOT/'website/content/daily'/f'{day}.md')],cwd=ROOT,timeout=60,check=True)
 print(json.dumps({'status':'written_and_checked_ready_to_publish','date':day,'actual_models':list(response['modelUsage']),'check_models':list(checked['modelUsage']),'check':json.loads((private/'check.json').read_text())}))
