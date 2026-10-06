#!/usr/bin/env python3
"""Export PRIVATE aggregate observation history, never raw transcripts."""
import argparse, collections, datetime, json, pathlib, gzip
ROOT=pathlib.Path(__file__).resolve().parents[2]; STORE=ROOT/'.local/metrics'
def summarize():
    totals=collections.defaultdict(lambda:{'snapshots':0,'pid_live_observed_seconds':0,'hook_working_observed_seconds':0,'hook_idle_observed_seconds':0,'cpu_seconds_observed_delta':0,'evidence_files_latest':None})
    conversations={}; previous={}; first=None; last=None; rows=0
    archive_dir = STORE / 'archive'
    all_files = list(STORE.glob('snapshots-*'))
    if archive_dir.is_dir():
        all_files.extend(archive_dir.glob('snapshots-*'))
    for file in sorted(all_files, key=lambda p:(p.name[:20], p.stat().st_mtime)):
        handle=gzip.open(file,'rt') if file.suffix=='.gz' else file.open()
        for line in handle:
            try: snap=json.loads(line); at=datetime.datetime.fromisoformat(snap['at']).timestamp()
            except (ValueError,KeyError): continue
            first=snap['at'] if first is None else first; last=snap['at']; rows+=1
            for r in snap.get('sessions',[]):
                tag=r.get('tag','unknown'); val=totals[tag]; val['team_id']=r.get('team_id'); val['role']=r.get('role'); val['snapshots']+=1
                old=previous.get(r.get('id')); interval=min(120,max(0,at-old[0])) if old else 0
                if r.get('pid_live'): val['pid_live_observed_seconds']+=interval
                if r.get('pid_live') and not r.get('stale_hook'):
                    if r.get('reported_state')=='working': val['hook_working_observed_seconds']+=interval
                    if r.get('reported_state') in ('idle','waiting'): val['hook_idle_observed_seconds']+=interval
                if old and old[1].get('proc_start_ticks')==r.get('proc_start_ticks') and isinstance(r.get('cpu_seconds'),(int,float)) and isinstance(old[1].get('cpu_seconds'),(int,float)):
                    val['cpu_seconds_observed_delta']+=max(0,r['cpu_seconds']-old[1]['cpu_seconds'])
                previous[r.get('id')]=(at,r)
                u=r.get('usage')
                if u and u.get('conversation_id') and isinstance(u.get('total_tokens'),int):
                    key=u['source']+':'+u['conversation_id']; c=conversations.setdefault(key,{'source':u['source'],'conversation_id':u['conversation_id'],'observed_tags':[],'first_observed_cumulative_tokens':u['total_tokens'],'latest_observed_cumulative_tokens':u['total_tokens'],'reported_list_price_cost_usd':u.get('cost_usd'),'cost_basis':u.get('cost_basis')})
                    if tag not in c['observed_tags']:c['observed_tags'].append(tag)
                    c['latest_observed_cumulative_tokens']=max(c['latest_observed_cumulative_tokens'],u['total_tokens'])
        handle.close()
    for c in conversations.values():c['tokens_delta_during_observation']=c['latest_observed_cumulative_tokens']-c['first_observed_cumulative_tokens']
    latest=json.loads((STORE/'latest.json').read_text()) if (STORE/'latest.json').exists() else {}
    tasks=latest.get('tasks',[])
    for tag,value in totals.items():
        registered=sorted({rel for task in tasks if task.get('owner_tag')==tag for rel in task.get('evidence_paths',[])})
        observed={};missing=[];unsupported=[];outside=[]
        for rel in registered:
            path=(ROOT/rel).resolve()
            if ROOT not in path.parents:outside.append(rel)
            elif path.is_file():observed[str(path)]={'path':rel,'bytes':path.stat().st_size,'mtime':path.stat().st_mtime}
            elif path.is_dir():unsupported.append(rel)
            else:missing.append(rel)
        value['evidence_files_latest']=len(observed) if observed or (registered and not (missing or unsupported or outside)) else None
        value['evidence_coverage']={'registered_distinct_paths':len(registered),'observed_distinct_files':len(observed),'missing_paths':missing,'unsupported_directory_paths':unsupported,'out_of_scope_paths':outside,'status':'unregistered' if not registered else ('partial' if missing or unsupported or outside else 'observed'),'scope':'Current registered file metadata, not validated outcomes or historical authorship','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    return {'schema_version':1,'first_observation':first,'last_observation':last,'snapshots':rows,'per_tag':dict(totals),'conversations':list(conversations.values()),'tasks_done_by_owner':dict(collections.Counter(t.get('owner_tag','unknown') for t in tasks if t.get('status')=='done')),'latest_task_states':latest.get('aggregate',{}).get('tasks_by_status',{}),'limits':['Observed hook seconds are sampling estimates, NOT useful work or billable time.','Conversation cumulative totals can include pre-observation history; only the difference is interval usage.','Unknown/missing telemetry is not zero. Reused conversations are counted once across session resumes.','Nested executor provider costs are not inferred from subscription quota or list-price metadata.','Task completion is registered status; independently accepted outcomes require task evidence and reviewer signoff.']}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output');args=ap.parse_args(); result=summarize()
    if args.output:
        path=pathlib.Path(args.output).resolve()
        if STORE.resolve() not in path.parents:raise SystemExit('export must stay in private .local/metrics')
        path.write_text(json.dumps(result,indent=2));path.chmod(0o600);print(str(path))
    else:print(json.dumps(result,indent=2))
