#!/usr/bin/env python3
"""Export PRIVATE aggregate observation history, never raw transcripts."""
import argparse, collections, datetime, json, pathlib, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; STORE=ROOT/'.local/metrics'
METRICS_DIR = pathlib.Path(__file__).resolve().parent
if str(METRICS_DIR) not in sys.path:
    sys.path.insert(0, str(METRICS_DIR))
import tsdb
import state as state_store

VM_URL = tsdb.VM_URL
RETENTION_SECONDS = 400 * 86400


def _range_stats(matrix, step_seconds):
    """Aggregate a query_range matrix into per-series summaries.

    Gauge samples are treated as covering the step interval; unknown stays
    unknown (a series with no points yields None fields, never zero).
    """
    out = []
    for series in matrix:
        metric = series.get('metric', {})
        try:
            values = [(ts, float(v)) for ts, v in series.get('values', [])]
        except (TypeError, ValueError):
            values = []
        if not values:
            out.append({'metric': metric, 'points': 0, 'last': None,
                        'avg': None, 'min': None, 'max': None,
                        'covered_seconds': 0})
            continue
        nums = [v for _, v in values]
        out.append({'metric': metric, 'points': len(values), 'last': nums[-1],
                    'avg': sum(nums) / len(nums), 'min': min(nums), 'max': max(nums),
                    'covered_seconds': len(values) * step_seconds})
    return out


def _delta_in_window(matrix):
    """Per-series last-minus-first over the window; None when unknowable."""
    out = []
    for series in matrix:
        metric = series.get('metric', {})
        try:
            nums = [float(v) for _, v in series.get('values', [])]
        except (TypeError, ValueError):
            nums = []
        out.append({'metric': metric,
                    'delta': (nums[-1] - nums[0]) if len(nums) >= 2 else None,
                    'first': nums[0] if nums else None,
                    'last': nums[-1] if nums else None})
    return out


def summarize(vm_url=VM_URL, store=STORE, window_seconds='24h', end=None, step='5m',
              query_fn=None, range_fn=None):
    """Summarize observation history from VictoriaMetrics + SQLite state.

    window_seconds accepts the same shorthand as parse_window_seconds
    ('30m', '24h', 'all'); 'all'/None covers the 400d retention. Every
    section is marked with its source; anything VM or SQLite cannot answer
    is null, never zero or an estimate dressed as measurement.
    """
    query_fn = query_fn or (lambda expr, at: tsdb.query(vm_url, expr, at))
    range_fn = range_fn or (lambda expr, s, e, st: tsdb.query_range(vm_url, expr, s, e, st))
    store = pathlib.Path(store)
    end_dt = parse_iso_datetime(end)
    end_ts = int(end_dt.timestamp())
    parsed_window = parse_window_seconds(window_seconds, end_dt)
    if parsed_window is None:
        parsed_window = float(RETENTION_SECONDS)
    start_ts = int(end_ts - parsed_window)
    step_seconds = 300.0
    try:
        if isinstance(step, str) and step.endswith('m'):
            step_seconds = float(step[:-1]) * 60.0
        elif isinstance(step, str) and step.endswith('h'):
            step_seconds = float(step[:-1]) * 3600.0
        elif isinstance(step, str) and step.endswith('s'):
            step_seconds = float(step[:-1])
    except ValueError:
        pass

    result = {
        'schema_version': 2,
        'source': 'victoriametrics+sqlite',
        'vm_url': vm_url,
        'window_seconds': parsed_window,
        'window_start': datetime.datetime.fromtimestamp(start_ts, datetime.timezone.utc).isoformat(),
        'window_end': end_dt.isoformat(),
        'step': step,
        'vm_reachable': True,
        'vm_error': None,
    }

    def safe_range(expr):
        try:
            return range_fn(expr, start_ts, end_ts, step)
        except Exception as exc:
            result['vm_reachable'] = False
            result['vm_error'] = '%s: %s' % (type(exc).__name__, exc)
            return None

    def safe_query(expr):
        try:
            return query_fn(expr, end_ts)
        except Exception as exc:
            result['vm_reachable'] = False
            result['vm_error'] = '%s: %s' % (type(exc).__name__, exc)
            return None

    agents_live = safe_range('exp_agents_live')
    result['agents_live'] = _range_stats(agents_live, step_seconds) if agents_live is not None else None
    agents_working = safe_range('exp_agents_working')
    result['agents_working'] = _range_stats(agents_working, step_seconds) if agents_working is not None else None

    tasks_now = safe_query('exp_tasks')
    tasks_by_status = collections.Counter()
    if tasks_now is not None:
        for row in tasks_now:
            try:
                tasks_by_status[row['metric'].get('status', 'unknown')] += float(row['value'][1])
            except (KeyError, TypeError, ValueError):
                pass
    result['tasks_current_by_status'] = dict(sorted(tasks_by_status.items())) if tasks_now is not None else None

    transitions = safe_range('exp_task_transitions')
    transition_totals = collections.Counter()
    if transitions is not None:
        for series in transitions:
            metric = series.get('metric', {})
            try:
                total = sum(float(v) for _, v in series.get('values', []))
            except (TypeError, ValueError):
                continue
            transition_totals[(metric.get('from_status', 'unknown'),
                               metric.get('to_status', 'unknown'))] += total
    result['task_transitions_in_window'] = [
        {'from_status': k[0], 'to_status': k[1], 'events': v}
        for k, v in sorted(transition_totals.items())] if transitions is not None else None

    tokens = safe_range('exp_tokens_cumulative')
    token_deltas = collections.Counter()
    token_latest = collections.Counter()
    if tokens is not None:
        for row in _delta_in_window(tokens):
            provider = row['metric'].get('provider', 'unknown')
            model = row['metric'].get('model', 'unknown')
            if row['delta'] is not None and row['delta'] > 0:
                token_deltas[(provider, model)] += row['delta']
            if row['last'] is not None:
                token_latest[(provider, model)] += row['last']
    result['tokens_delta_by_provider_model'] = [
        {'provider': k[0], 'model': k[1], 'tokens': v}
        for k, v in sorted(token_deltas.items())] if tokens is not None else None
    result['tokens_cumulative_by_provider_model'] = [
        {'provider': k[0], 'model': k[1], 'tokens': v}
        for k, v in sorted(token_latest.items())] if tokens is not None else None

    quota_now = safe_query('exp_quota_remaining')
    quota = {}
    if quota_now is not None:
        for row in quota_now:
            try:
                quota.setdefault(row['metric'].get('provider', 'unknown'), {})[
                    row['metric'].get('window', 'unknown')] = float(row['value'][1])
            except (KeyError, TypeError, ValueError):
                pass
    result['quota_remaining'] = quota if quota_now is not None else None

    load = safe_range('exp_host_load')
    result['host_load'] = _range_stats(load, step_seconds) if load is not None else None
    disks = safe_range('exp_disk_free_bytes')
    result['disk_free'] = _range_stats(disks, step_seconds) if disks is not None else None

    try:
        tasks = state_store.read_tasks(store)
        evidence = state_store.read_evidence(store)
        changes = state_store.read_transitions(
            store, since=result['window_start'])
        result['sqlite'] = {
            'tasks_tracked': len(tasks),
            'tasks_by_status': dict(sorted(collections.Counter(
                (t.get('status') or 'unknown') for t in tasks).items())),
            'evidence_files_tracked': len(evidence),
            'transitions_in_window': len(changes),
        }
    except Exception as exc:
        result['sqlite'] = {'error': '%s: %s' % (type(exc).__name__, exc)}

    result['limits'] = [
        'Agent-minutes integrate 5-minute gauge samples; sparse coverage yields null, not zero.',
        'Token deltas are last-minus-first cumulative per conversation; resets or shrinks are excluded, not negatived.',
        'Per-tag cumulative history predates the TSDB migration and is not rebuilt; role/team aggregates are the history.',
        'Quota readings are account state, never usage or cost. Unknown telemetry is null.',
    ]
    return result

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

def parse_iso_datetime(as_of):
    if as_of is None:
        return datetime.datetime.now(datetime.timezone.utc)
    if isinstance(as_of, str):
        s = as_of.strip()
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    if isinstance(as_of, datetime.datetime):
        return as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=datetime.timezone.utc)
    return datetime.datetime.now(datetime.timezone.utc)

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

    as_of_dt = parse_iso_datetime(as_of)

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

DEFAULT_COMPETITION_REPOS = [
    ('cloudflare-agent-git', ROOT),
    ('agent-branches', ROOT.parent / 'agent-branches'),
    ('agent-dashboard', ROOT.parent / 'agent-dashboard'),
    ('agent-quota-launcher', ROOT.parent / 'agent-quota-launcher'),
    ('agent-bus', ROOT.parent / 'agent-bus'),
]

def summarize_running_agents(store_dir=STORE, as_of=None, latest_data=None):
    """Summarize currently observed live running agents, distinguishing registered vs unregistered."""
    if latest_data is None:
        latest_path = pathlib.Path(store_dir) / 'latest.json'
        latest_data = json.loads(latest_path.read_text()) if latest_path.exists() else {}

    ref_dt = parse_iso_datetime(as_of)
    aggregate = latest_data.get('aggregate', {})
    sessions = latest_data.get('sessions', [])

    live_sessions = [s for s in sessions if s.get('pid_live')]
    unregistered_live = [s for s in live_sessions if s.get('unregistered')]
    registered_live = [s for s in live_sessions if not s.get('unregistered')]

    by_role = collections.defaultdict(int)
    by_provider = collections.defaultdict(int)
    by_team = collections.defaultdict(int)
    by_state = collections.defaultdict(int)

    seen_ids = set()
    dedup_actors = []

    for s in live_sessions:
        sid = s.get('id') or s.get('tag')
        if sid and sid not in seen_ids:
            seen_ids.add(sid)
            dedup_actors.append(sid)

        role = s.get('role') or 'unknown'
        by_role[role] += 1

        team = s.get('team_id') or 'unassigned'
        by_team[team] += 1

        state = s.get('reported_state') or 'unknown'
        by_state[state] += 1

        engine = s.get('engine') or 'unknown'
        by_provider[engine] += 1

    active_working = sum(1 for s in live_sessions if s.get('reported_state') == 'working')
    idle_waiting = sum(1 for s in live_sessions if s.get('reported_state') in ('idle', 'waiting'))

    unregistered_count = len(unregistered_live) if unregistered_live else aggregate.get('unregistered_live', 0)
    total_running_agents = max(len(live_sessions), len(registered_live) + unregistered_count)

    return {
        'as_of': ref_dt.isoformat(),
        'total_running_agents': total_running_agents,
        'registered_live_count': len(registered_live),
        'unregistered_live_count': unregistered_count,
        'active_working_count': active_working,
        'idle_waiting_count': idle_waiting,
        'deduplicated_agent_ids': sorted(dedup_actors),
        'by_role': dict(sorted(by_role.items())),
        'by_provider': dict(sorted(by_provider.items())),
        'by_team': dict(sorted(by_team.items())),
        'by_state': dict(sorted(by_state.items())),
        'aggregate_summary': aggregate,
        'limits': [
            'Running agent counts are sampled point-in-time process/PTY observations, not verified continuous progress.',
            'Unregistered processes indicate external or untracked workers outside TEAM-REGISTRY.json.',
            'Reported working states require fresh activity validation before crediting as productive output.'
        ]
    }

def summarize_commits(window_seconds=86400, as_of=None, repos=None):
    """Summarize reachable git commits across core competition repositories within a time window."""
    parsed_window = parse_window_seconds(window_seconds, datetime.datetime.now(datetime.timezone.utc))
    if parsed_window is None:
        parsed_window = 86400.0

    ref_dt = parse_iso_datetime(as_of)
    window_start_dt = ref_dt - datetime.timedelta(seconds=parsed_window)
    window_start_iso = window_start_dt.isoformat()

    target_repos = repos if repos is not None else DEFAULT_COMPETITION_REPOS
    berlin_tz = datetime.timezone(datetime.timedelta(hours=2))

    per_repo = {}
    all_unique_shas = set()

    for name, path in target_repos:
        r_path = pathlib.Path(path).resolve()
        if not (r_path / '.git').exists():
            continue

        cmd = [
            'git', '-C', str(r_path), 'log',
            f'--since={window_start_iso}',
            '--format=%H|%an|%ae|%aI|%s'
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
        except Exception:
            lines = []

        repo_shas = set()
        hourly_berlin = collections.defaultdict(int)
        latest_sha = None

        for line in lines:
            parts = line.split('|', 4)
            if len(parts) >= 4:
                sha, author, email, commit_iso = parts[0], parts[1], parts[2], parts[3]
                if sha not in repo_shas:
                    repo_shas.add(sha)
                    all_unique_shas.add(sha)
                    if latest_sha is None:
                        latest_sha = sha
                    try:
                        c_dt = datetime.datetime.fromisoformat(commit_iso).astimezone(berlin_tz)
                        hour_str = c_dt.strftime('%Y-%m-%d %H:00 CEST')
                        hourly_berlin[hour_str] += 1
                    except Exception:
                        pass

        per_repo[name] = {
            'path': str(r_path),
            'unique_commit_count': len(repo_shas),
            'hourly_berlin': dict(sorted(hourly_berlin.items())),
            'latest_commit_sha': latest_sha
        }

    return {
        'as_of': ref_dt.isoformat(),
        'window_seconds': parsed_window,
        'window_start': window_start_iso,
        'total_unique_commits': len(all_unique_shas),
        'per_repo': per_repo,
        'limits': [
            'Reachable commits from repository working heads within the specified time window.',
            'Hourly breakdown is projected in Europe/Berlin time (CEST, UTC+2).',
            'Commit counts represent revision history progress, not independently accepted project outcomes.'
        ]
    }

if __name__=='__main__':
    ap = argparse.ArgumentParser(description="Export PRIVATE aggregate observation history, resolved tasks, running agents, and commits.")
    ap.add_argument('--output', help="Path to write output file (must be in .local/metrics)")
    ap.add_argument('--resolved-tasks', action='store_true', help="Run and output Continuation Runtime resolved tasks summary")
    ap.add_argument('--running-agents', action='store_true', help="Run and output live running agents summary")
    ap.add_argument('--commits', action='store_true', help="Run and output reachable commit metrics across competition repositories")
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
    elif args.running_agents:
        result = summarize_running_agents(as_of=args.as_of)
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
            print("Running Agents Summary:")
            print(f"  As of:                  {result['as_of']}")
            print(f"  Total running:          {result['total_running_agents']}")
            print(f"  Registered live:        {result['registered_live_count']}")
            print(f"  Unregistered live:      {result['unregistered_live_count']}")
            print(f"  Active working:         {result['active_working_count']}")
            print(f"  Idle/waiting:           {result['idle_waiting_count']}")
            print(f"  By role:                {json.dumps(result['by_role'])}")
            print(f"  By provider:            {json.dumps(result['by_provider'])}")
            print(f"  By team:                {json.dumps(result['by_team'])}")
    elif args.commits:
        result = summarize_commits(window_seconds=args.window, as_of=args.as_of)
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
            print("Competition Repositories Commit Metrics:")
            print(f"  As of:                  {result['as_of']}")
            print(f"  Window (seconds):       {result['window_seconds']}")
            print(f"  Window start:           {result['window_start']}")
            print(f"  Total unique commits:   {result['total_unique_commits']}")
            for repo, data in result['per_repo'].items():
                print(f"    - {repo}: {data['unique_commit_count']} commits (latest: {data['latest_commit_sha'][:8] if data['latest_commit_sha'] else 'none'})")
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
