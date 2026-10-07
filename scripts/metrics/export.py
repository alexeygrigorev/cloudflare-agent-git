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

def parse_window_seconds(val, ref_dt):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip().lower()
        if s in ('all', 'all-time', 'none', ''):
            return None
        if s in ('calendar-day', 'day', 'today'):
            start_of_day = ref_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            return max(0.0, (ref_dt - start_of_day).total_seconds())
        if s.endswith('m'):
            return float(s[:-1]) * 60.0
        if s.endswith('h'):
            return float(s[:-1]) * 3600.0
        if s.endswith('d'):
            return float(s[:-1]) * 86400.0
        if s.endswith('s'):
            return float(s[:-1])
        return float(s)
    return float(val)

def summarize_resolved_tasks(tasks=None, tasks_path=None, window_seconds=None, as_of=None, project=None, root_dir=None) -> dict:
    root_dir_path = pathlib.Path(root_dir).resolve() if root_dir else ROOT
    if tasks is None:
        target_path = pathlib.Path(tasks_path).resolve() if tasks_path else root_dir_path / 'coordination/TASKS.json'
        if target_path.exists():
            data = json.loads(target_path.read_text())
            tasks = data.get('tasks', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        else:
            tasks = []
    elif isinstance(tasks, dict):
        tasks = tasks.get('tasks', [])
    elif not isinstance(tasks, list):
        tasks = []

    if as_of is None:
        as_of_dt = datetime.datetime.now(datetime.timezone.utc)
    elif isinstance(as_of, str):
        s = as_of.strip()
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        as_of_dt = datetime.datetime.fromisoformat(s)
        if as_of_dt.tzinfo is None:
            as_of_dt = as_of_dt.replace(tzinfo=datetime.timezone.utc)
    elif isinstance(as_of, datetime.datetime):
        as_of_dt = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=datetime.timezone.utc)
    else:
        as_of_dt = datetime.datetime.now(datetime.timezone.utc)

    parsed_window = parse_window_seconds(window_seconds, as_of_dt)

    seen_resolved_ids = set()
    reopened_task_ids = set()
    unknown_timestamp_task_ids = set()
    by_project = collections.Counter()
    by_owner = collections.Counter()
    verified_evidence_tasks = 0
    missing_evidence_tasks = 0
    latest_accepted_dt = None

    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get('id', '')).strip()
        if not task_id:
            continue

        task_proj = task.get('project') or task.get('project_id') or task.get('team_id')
        if project is not None and task_proj != project:
            continue

        # Reopened detection:
        is_reopened = False
        if 'reopened' in task and task['reopened'] is not False and task['reopened'] != 0:
            is_reopened = True
        elif task.get('status') == 'reopened':
            is_reopened = True
        elif task.get('status') in ('todo', 'in_progress'):
            history = task.get('checkpoint_history') or task.get('delivery_checkpoints') or []
            for cp in history:
                if isinstance(cp, dict):
                    st = str(cp.get('status', '')).lower()
                    out = str(cp.get('outcome', '')).lower()
                    verd = str(cp.get('verdict', '')).lower()
                    if st in ('done', 'accepted') or out in ('done', 'accepted') or verd in ('accept', 'accepted', 'done'):
                        is_reopened = True
                        break
                elif isinstance(cp, str):
                    cp_lower = cp.lower()
                    if 'done' in cp_lower or 'accepted' in cp_lower:
                        is_reopened = True
                        break
            if not is_reopened and 'status_history' in task:
                for sh in task.get('status_history', []):
                    if isinstance(sh, dict) and sh.get('status') in ('done', 'accepted'):
                        is_reopened = True
                        break
        if is_reopened:
            reopened_task_ids.add(task_id)

        # Status check for resolution
        raw_status = str(task.get('status', '')).strip().lower()
        excluded_statuses = {
            'todo', 'in_progress', 'starting', 'running', 'failed',
            'cancelled', 'awaiting-review', 'completed-awaiting-review',
            'review', 'queued', 'blocked', 'held', 'ready'
        }
        if raw_status not in ('done', 'accepted') or raw_status in excluded_statuses:
            continue

        acceptance = task.get('acceptance')
        if not acceptance:
            continue
        if isinstance(acceptance, str) and not acceptance.strip():
            continue

        if str(task.get('acceptance_status', '')).lower() in ('rejected', 'fail', 'failed'):
            continue
        if str(task.get('reviewer_verdict', '')).lower() in ('rejected', 'fail', 'failed', 'reject'):
            continue
        if str(task.get('verdict', '')).lower() in ('rejected', 'fail', 'failed', 'reject'):
            continue

        # Extract timestamp
        raw_ts = None
        if task.get('accepted_at') == 'unknown':
            raw_ts = None
        elif task.get('accepted_at'):
            raw_ts = task['accepted_at']
        elif task.get('completed_at'):
            raw_ts = task['completed_at']
        elif task.get('updated_at'):
            raw_ts = task['updated_at']
        else:
            checkpoints = task.get('checkpoint_history') or task.get('delivery_checkpoints') or []
            for cp in reversed(checkpoints):
                if isinstance(cp, dict):
                    for cp_k in ('recorded_at', 'observed_at', 'timestamp', 'at', 'due_at_utc'):
                        if cp.get(cp_k):
                            raw_ts = cp[cp_k]
                            break
                elif isinstance(cp, str):
                    raw_ts = cp
                if raw_ts:
                    break

        task_dt = None
        if raw_ts and raw_ts not in ('unknown', 'null', 'None'):
            try:
                ts_str = str(raw_ts).strip()
                if ts_str.endswith('Z'):
                    ts_str = ts_str[:-1] + '+00:00'
                parsed_dt = datetime.datetime.fromisoformat(ts_str)
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=datetime.timezone.utc)
                task_dt = parsed_dt
            except Exception:
                task_dt = None

        if task_dt is None:
            unknown_timestamp_task_ids.add(task_id)

        # Window filtering
        if task_dt is not None:
            age_seconds = (as_of_dt - task_dt).total_seconds()
            if age_seconds < 0:
                continue
            if parsed_window is not None and age_seconds > parsed_window:
                continue
        else:
            if parsed_window is not None:
                continue

        # Deduplicate alias / multiple records
        if task_id in seen_resolved_ids:
            continue
        seen_resolved_ids.add(task_id)

        if task_dt is not None:
            if latest_accepted_dt is None or task_dt > latest_accepted_dt:
                latest_accepted_dt = task_dt

        proj_key = task_proj or 'unknown'
        by_project[proj_key] += 1

        owner_key = task.get('owner_tag') or task.get('owner') or 'unknown'
        by_owner[owner_key] += 1

        ev_paths = task.get('evidence_paths') or []
        has_valid_evidence = False
        for p in ev_paths:
            if not p:
                continue
            p_path = pathlib.Path(p)
            target = p_path if p_path.is_absolute() else (root_dir_path / p_path)
            if target.exists():
                has_valid_evidence = True
                break

        if has_valid_evidence:
            verified_evidence_tasks += 1
        else:
            missing_evidence_tasks += 1

    resolved_list = sorted(list(seen_resolved_ids))
    reopened_list = sorted(list(reopened_task_ids))
    unknown_ts_list = sorted(list(unknown_timestamp_task_ids))

    total_evidence = verified_evidence_tasks + missing_evidence_tasks
    coverage_ratio = float(verified_evidence_tasks / total_evidence) if total_evidence > 0 else 0.0

    freshness_seconds = max(0.0, (as_of_dt - latest_accepted_dt).total_seconds()) if latest_accepted_dt is not None else None
    latest_accepted_at_str = latest_accepted_dt.isoformat() if latest_accepted_dt is not None else None

    return {
        'as_of': as_of_dt.isoformat(),
        'window_seconds': parsed_window,
        'project': project,
        'resolved_unique_task_ids': resolved_list,
        'resolved_task_count': len(resolved_list),
        'reopened_task_ids': reopened_list,
        'reopened_count': len(reopened_list),
        'unknown_timestamp_task_ids': unknown_ts_list,
        'unknown_timestamp_count': len(unknown_ts_list),
        'latest_accepted_at': latest_accepted_at_str,
        'freshness_seconds': freshness_seconds,
        'evidence_coverage': {
            'verified_count': verified_evidence_tasks,
            'missing_count': missing_evidence_tasks,
            'coverage_ratio': coverage_ratio,
        },
        'by_project': dict(sorted(by_project.items())),
        'by_owner': dict(sorted(by_owner.items())),
    }

if __name__=='__main__':
    ap = argparse.ArgumentParser(description="Export PRIVATE aggregate observation history and resolved tasks.")
    ap.add_argument('--output', help="Path to write output file (must be in .local/metrics)")
    ap.add_argument('--resolved-tasks', action='store_true', help="Run and output Continuation Runtime resolved tasks summary")
    ap.add_argument('--window', default=None, help="Window in seconds or shorthand ('30m', '24h', 'all')")
    ap.add_argument('--project', default=None, help="Project name filter")
    ap.add_argument('--as-of', default=None, help="ISO-8601 UTC timestamp")
    ap.add_argument('--json', action='store_true', help="Emit JSON output")
    args = ap.parse_args()

    if args.resolved_tasks:
        result = summarize_resolved_tasks(
            window_seconds=args.window,
            as_of=args.as_of,
            project=args.project,
        )
        if args.output:
            path = pathlib.Path(args.output).resolve()
            if STORE.resolve() not in path.parents:
                raise SystemExit('export must stay in private .local/metrics')
            path.write_text(json.dumps(result, indent=2))
            path.chmod(0o600)
            print(str(path))
        elif args.json:
            print(json.dumps(result, indent=2))
        else:
            cov = result['evidence_coverage']
            cov_pct = cov['coverage_ratio'] * 100
            print("Continuation Runtime Resolved Tasks Summary:")
            print(f"  As of:                  {result['as_of']}")
            print(f"  Window (seconds):       {result['window_seconds']}")
            print(f"  Project filter:         {result['project']}")
            print(f"  Resolved task count:    {result['resolved_task_count']}")
            print(f"  Resolved task IDs:      {', '.join(result['resolved_unique_task_ids'])}")
            print(f"  Reopened count:         {result['reopened_count']}")
            print(f"  Reopened task IDs:      {', '.join(result['reopened_task_ids'])}")
            print(f"  Unknown timestamp count:{result['unknown_timestamp_count']}")
            print(f"  Unknown timestamp IDs:  {', '.join(result['unknown_timestamp_task_ids'])}")
            print(f"  Latest accepted at:     {result['latest_accepted_at']}")
            print(f"  Freshness (seconds):    {result['freshness_seconds']}")
            print(f"  Evidence coverage:      {cov_pct:.1f}% ({cov['verified_count']} verified, {cov['missing_count']} missing)")
            print(f"  By project:             {json.dumps(result['by_project'])}")
            print(f"  By owner:               {json.dumps(result['by_owner'])}")
    else:
        result = summarize()
        if args.output:
            path = pathlib.Path(args.output).resolve()
            if STORE.resolve() not in path.parents:
                raise SystemExit('export must stay in private .local/metrics')
            path.write_text(json.dumps(result, indent=2))
            path.chmod(0o600)
            print(str(path))
        else:
            print(json.dumps(result, indent=2))
