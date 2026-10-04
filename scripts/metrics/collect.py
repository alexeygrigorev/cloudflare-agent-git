#!/usr/bin/env python3
"""Multi-workspace private experiment observation.
Discovers and attributes sessions, heads, and delegates across all product workspaces:
- /home/alexey/git/cloudflare-agent-git
- /home/alexey/git/agent-branches
- /home/alexey/git/agent-dashboard
- /home/alexey/git/agent-quota-launcher
- /home/alexey/git/agent-coordination
and any workspaces in TEAM-REGISTRY.json or live aplexer session catalog.
Never dispatches agents or changes hook state. Zero retroactive fake data.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import http.server
import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
import threading
import time
import warnings

logger = logging.getLogger('collect')
ROOT = pathlib.Path(__file__).resolve().parents[2]
METRICS_DIR = ROOT / 'scripts/metrics'
if str(METRICS_DIR) not in sys.path:
    sys.path.insert(0, str(METRICS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STORE = ROOT / '.local/metrics'
STORE.mkdir(parents=True, exist_ok=True)
try:
    os.chmod(STORE, 0o700)
except OSError:
    pass

from adapters import quotas, temporal, archive_history
from opencode_usage import read_usage as read_opencode_usage, SOURCE as OPENCODE_SOURCE

COUNT_ROLES = {'principal', 'head', 'executor', 'subagent'}
APLEXER_STATE = pathlib.Path.home() / '.local/state/aplexer/sessions'

DEFAULT_PRODUCT_WORKSPACES = [
    '/home/alexey/git/cloudflare-agent-git',
    '/home/alexey/git/agent-branches',
    '/home/alexey/git/agent-dashboard',
    '/home/alexey/git/agent-quota-launcher',
    '/home/alexey/git/agent-coordination',
]
PRODUCT_WORKSPACES = list(DEFAULT_PRODUCT_WORKSPACES)

CANONICAL_GIT_ROOT = ROOT.parent.resolve()

CANONICAL_PRODUCT_REPO_NAMES = {
    'cloudflare-agent-git',
    'agent-branches',
    'agent-dashboard',
    'agent-quota-launcher',
    'agent-coordination',
    'agent-bus',
    'aplexer',
    'cloudflare-aplexer-protocol',
}

CANONICAL_WORKTREE_PREFIXES = (
    'agent-branches-',
    'agent-dashboard-',
    'agent-coordination-',
    'quota-launcher-',
)


def get_product_workspaces(root=None, registry=None, catalog=None):
    """Resolve all active product workspaces including ROOT, configured defaults,
    workspaces in registry (teams, projects, delivery_executors, agents),
    and workspaces present in the live aplexer catalog.
    """
    ws = set()
    current_root = root if root is not None else ROOT
    if current_root:
        try:
            r_path = pathlib.Path(current_root).resolve()
            ws.add(str(r_path))
            for sib_name in ('agent-branches', 'agent-dashboard', 'agent-quota-launcher', 'agent-coordination'):
                sib = r_path.parent / sib_name
                if sib.exists():
                    ws.add(str(sib.resolve()))
        except Exception:
            ws.add(str(current_root))

    for p in PRODUCT_WORKSPACES:
        if p:
            try:
                ws.add(str(pathlib.Path(p).resolve()))
            except Exception:
                ws.add(str(p))

    if isinstance(registry, dict):
        for team in registry.get('teams', []):
            if team.get('workspace'):
                try: ws.add(str(pathlib.Path(team['workspace']).resolve()))
                except Exception: ws.add(str(team['workspace']))
            for a in team.get('agents', []):
                if a.get('workspace'):
                    try: ws.add(str(pathlib.Path(a['workspace']).resolve()))
                    except Exception: ws.add(str(a['workspace']))
        for proj in registry.get('projects', []):
            if proj.get('workspace'):
                try: ws.add(str(pathlib.Path(proj['workspace']).resolve()))
                except Exception: ws.add(str(proj['workspace']))
        for exe in registry.get('delivery_executors', []):
            if exe.get('workspace'):
                try: ws.add(str(pathlib.Path(exe['workspace']).resolve()))
                except Exception: ws.add(str(exe['workspace']))
        for a in registry.get('agents', []):
            if a.get('workspace'):
                try: ws.add(str(pathlib.Path(a['workspace']).resolve()))
                except Exception: ws.add(str(a['workspace']))


    if isinstance(catalog, list):
        for s in catalog:
            sw = s.get('workspace') or s.get('cwd')
            if not sw:
                continue
            try:
                sw_path = pathlib.Path(sw).resolve()
                if str(sw_path) in ws:
                    continue
                # Path authorization boundary:
                # Must be an authorized product workspace directly under CANONICAL_GIT_ROOT (/home/alexey/git/)
                if sw_path.parent == CANONICAL_GIT_ROOT or sw_path == ROOT:
                    name = sw_path.name
                    if name in CANONICAL_PRODUCT_REPO_NAMES or any(name.startswith(pfx) for pfx in CANONICAL_WORKTREE_PREFIXES):
                        # Worktree Provenance Gap fix (32b5 Review):
                        # If sw_path exists on disk, enforce authentic Git provenance.
                        # Reject non-git scratch directories or worktrees pointing to unauthorized repos.
                        if sw_path.exists():
                            if not verify_git_provenance(sw_path, CANONICAL_GIT_ROOT, CANONICAL_PRODUCT_REPO_NAMES):
                                continue
                        ws.add(str(sw_path))
            except Exception:
                pass
    return ws


def verify_git_provenance(sw_path: pathlib.Path, canonical_root: pathlib.Path = CANONICAL_GIT_ROOT, canonical_repos: set = None) -> bool:
    """Verify that sw_path has authentic Git provenance:
    1. If it has a .git directory containing HEAD, it is an authentic standalone repo.
       Its name must be in canonical_repos or sw_path == ROOT.
    2. If it has a .git file (linked worktree):
       - It must contain 'gitdir: <path>'.
       - That gitdir must contain a 'commondir' file.
       - That commondir must resolve to a .git directory of an authorized canonical repo.
       - The parent repository must reside under canonical_root and have a name in canonical_repos.
    Any non-git directory, corrupt pointer, or external gitdir is strictly rejected.
    """
    if canonical_repos is None:
        canonical_repos = CANONICAL_PRODUCT_REPO_NAMES
    try:
        git_entry = sw_path / '.git'
        if not git_entry.exists():
            return False
        if git_entry.is_dir():
            return (git_entry / 'HEAD').is_file() and (sw_path.name in canonical_repos or sw_path == ROOT)
        if git_entry.is_file():
            raw = git_entry.read_text(encoding='utf-8', errors='replace').strip()
            if not raw.startswith('gitdir:'):
                return False
            gitdir_str = raw[len('gitdir:'):].strip()
            gitdir_path = (sw_path / gitdir_str).resolve()
            if not gitdir_path.is_dir():
                return False
            commondir_file = gitdir_path / 'commondir'
            if not commondir_file.is_file():
                return False
            commondir_str = commondir_file.read_text(encoding='utf-8', errors='replace').strip()
            commondir_path = (gitdir_path / commondir_str).resolve()
            if not (commondir_path / 'HEAD').is_file():
                return False
            parent_repo = commondir_path.parent.resolve()
            if parent_repo.parent != canonical_root and parent_repo != ROOT:
                return False
            if parent_repo.name not in canonical_repos and parent_repo != ROOT:
                return False
            return True
    except Exception:
        return False
    return False


def read_json(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text())
    except (OSError, ValueError):
        return default


def atomic(p, obj):
    tmp = pathlib.Path(str(p) + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False))
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(p)


def disk_session(session_id, workspace=None):
    """Completed sessions pruned from the live aplexer catalog persist on disk.
    Matches session ID and optional workspace path. Liveness fields dropped."""
    base = APLEXER_STATE / str(session_id)
    for name in ('session.json', 'session_record.json'):
        row = read_json(base / name)
        if not isinstance(row, dict) or not row.get('id'):
            continue
        if str(row.get('id')) != str(session_id):
            continue
        record_workspace = row.get('workspace') or row.get('cwd')
        if workspace and record_workspace:
            try:
                if pathlib.Path(record_workspace).resolve() != pathlib.Path(workspace).resolve():
                    continue
            except Exception:
                if record_workspace != workspace:
                    continue
        row.pop('workload_pid', None)
        row.setdefault('workspace', record_workspace or str(ROOT))
        return row
    return None


def native_usage(session):
    """Codex cumulative native usage: cache categories already INCLUDED in input."""
    binding = read_json(APLEXER_STATE / session['id'] / 'transcript.json', {})
    path = pathlib.Path(binding.get('path', '/nonexistent'))
    if not path.is_file():
        return None
    if binding.get('engine') not in ('codex', 'zcodex'):
        return None
    try:
        with path.open('rb') as f:
            size = path.stat().st_size
            offset = max(0, size - 2 * 1024 * 1024)
            f.seek(offset)
            if offset:
                f.readline()
            data = f.read(2 * 1024 * 1024).decode('utf-8', errors='replace')
        result = None
        for line in data.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            payload = row.get('payload', {})
            if row.get('type') == 'event_msg' and payload.get('type') == 'token_count':
                total = (payload.get('info') or {}).get('total_token_usage')
                if total:
                    result = {
                        'conversation_id': binding.get('engine_session_id'),
                        'source': 'codex-native-cumulative',
                        'scope': 'Conversation cumulative; may include pre-observer history. NOT experiment expenditure.',
                        'input_tokens': total.get('input_tokens'),
                        'output_tokens': total.get('output_tokens'),
                        'total_tokens': total.get('total_tokens'),
                        'cached_input_tokens': total.get('cached_input_tokens'),
                        'reasoning_output_tokens': total.get('reasoning_output_tokens'),
                        'cost_usd': None,
                        'cost_basis': None,
                        'observed_at': row.get('timestamp')
                    }
        return result
    except OSError:
        return None


def rollout_tele_path(tele):
    kind = tele.get('type') or ''
    path = tele.get('path')
    if not isinstance(path, str) or not path:
        return None
    if kind.endswith('rollout'):
        return path
    name = pathlib.PurePath(path).name
    return path if name.endswith('.jsonl') and 'rollout' in name else None


def rollout_usage(path, conversation_id=None):
    p = pathlib.Path(path).expanduser()
    if not p.is_file():
        return None
    try:
        meta_id = None
        try:
            with p.open('rb') as hf:
                head = hf.read(256 * 1024).decode('utf-8', errors='replace')
        except OSError:
            head = ''
        for line in head.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('type') == 'session_meta':
                payload = row.get('payload') or {}
                meta_id = payload.get('id') or payload.get('session_id') or meta_id
                break
        with p.open('rb') as f:
            size = p.stat().st_size
            offset = max(0, size - 2 * 1024 * 1024)
            f.seek(offset)
            if offset:
                f.readline()
            data = f.read(2 * 1024 * 1024).decode('utf-8', errors='replace')
        result = None
        for line in data.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            payload = row.get('payload') or {}
            if row.get('type') == 'event_msg' and payload.get('type') == 'token_count':
                total = (payload.get('info') or {}).get('total_token_usage')
                if total:
                    result = {
                        'conversation_id': meta_id,
                        'source': 'codex-rollout',
                        'scope': 'Saved rollout cumulative; may include pre-observer history. NOT experiment expenditure.',
                        'input_tokens': total.get('input_tokens'),
                        'output_tokens': total.get('output_tokens'),
                        'total_tokens': total.get('total_tokens'),
                        'cached_input_tokens': total.get('cached_input_tokens'),
                        'reasoning_output_tokens': total.get('reasoning_output_tokens'),
                        'cost_usd': None,
                        'cost_basis': None,
                        'observed_at': row.get('timestamp'),
                        'rollout_path': str(p)
                    }
        if result:
            if conversation_id and meta_id and conversation_id != meta_id:
                result['conversation_id'] = None
                result['scope'] += ' Saved telemetry and rollout head disagree on the native conversation id; treated as unknown.'
            elif result['conversation_id'] is None and conversation_id:
                result['conversation_id'] = conversation_id
            elif result['conversation_id'] is None:
                result['scope'] += ' Native conversation id outside the bounded head/tail window; unknown and excluded from conversation totals.'
        return result
    except OSError:
        return None


def opencode_sid(item, tele):
    if tele.get('type') == 'opencode-db':
        candidates = [tele.get('conversation_id'), item.get('opencode_session_id'), item.get('resumed_conversation'), item.get('conversation')]
    else:
        candidates = [item.get('opencode_session_id'), item.get('resumed_conversation'), item.get('conversation')]
    return next((c for c in candidates if isinstance(c, str) and c.startswith('ses_')), None)


def proc(pid):
    try:
        raw = pathlib.Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        if fields[0] == 'Z':
            return {'alive': False}
        hz = os.sysconf('SC_CLK_TCK')
        pages = os.sysconf('SC_PAGE_SIZE')
        return {
            'alive': True,
            'cpu_seconds': (int(fields[11]) + int(fields[12])) / hz,
            'rss_bytes': int(fields[21]) * pages,
            'start_ticks': int(fields[19])
        }
    except (OSError, ValueError, IndexError, TypeError):
        return {'alive': False}


def count_status(rows):
    return {key: sum(bool(r.get(key)) for r in rows) for key in ['pid_live', 'hook_working', 'stale_hook', 'unregistered']}


def authentic_conversation_id(s, item):
    if not isinstance(item, dict): item = {}
    if not isinstance(s, dict): s = {}

    for val in (s.get('engine_session_id'), s.get('conversation_id')):
        if isinstance(val, str) and val.strip():
            return val.strip()

    sid = s.get('id') or item.get('session_id')
    if sid:
        binding = read_json(APLEXER_STATE / str(sid) / 'transcript.json', {}) or {}
        for val in (binding.get('engine_session_id'), binding.get('conversation_id')):
            if isinstance(val, str) and val.strip():
                return val.strip()
        disk = disk_session(sid, item.get('workspace'))
        if disk:
            for val in (disk.get('engine_session_id'), disk.get('conversation_id')):
                if isinstance(val, str) and val.strip():
                    return val.strip()

    for val in (item.get('harness_conversation_id'), item.get('conversation_id')):
        if isinstance(val, str) and val.strip():
            return val.strip()

    for val in (item.get('telemetry', {}).get('conversation_id') if isinstance(item.get('telemetry'), dict) else None,
                s.get('telemetry', {}).get('conversation_id') if isinstance(s.get('telemetry'), dict) else None):
        if isinstance(val, str) and val.strip():
            return val.strip()

    return None


def parse_entry_timestamp(entry):
    if not isinstance(entry, dict): return 0.0
    ts = entry.get('observed_at') or entry.get('at') or entry.get('timestamp')
    if ts is None: return 0.0
    if isinstance(ts, (int, float)): return float(ts)
    if isinstance(ts, str):
        try: return dt.datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
        except ValueError: return 0.0
    return 0.0


def match_usage_event(events_path, tag, team_id, session_cid=None):
    p = pathlib.Path(events_path)
    if not p.is_file() or p.stat().st_size > 16 * 1024 * 1024:
        return None, False

    if session_cid:
        session_cid = session_cid.strip() if session_cid else None
    if not session_cid:
        session_cid = None

    matches = []
    has_fallback = False
    try:
        with p.open('r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    entry = json.loads(line_str)
                except (json.JSONDecodeError, ValueError) as exc:
                    logger.warning("Skipping corrupted line in %s: %s", events_path, exc)
                    warnings.warn(f"Skipping corrupted line in {events_path}: {exc}", UserWarning)
                    continue
                if not isinstance(entry, dict):
                    logger.warning("Skipping non-dict JSON entry in %s: %r", events_path, entry)
                    warnings.warn(f"Skipping non-dict JSON entry in {events_path}: {entry}", UserWarning)
                    continue
                if entry.get('tag') != tag or entry.get('team_id') != team_id:
                    continue
                entry_cid = entry.get('conversation_id')
                if entry_cid:
                    entry_cid = entry_cid.strip() if isinstance(entry_cid, str) else None
                if not entry_cid:
                    entry_cid = None
                    if 'conversation_id' in entry:
                        entry['conversation_id'] = None
                if session_cid:
                    if entry_cid == session_cid:
                        matches.append(entry)
                else:
                    if not entry_cid:
                        matches.append(entry)
                        has_fallback = True
    except OSError:
        return None, False

    if not matches:
        return None, False

    matches.sort(key=lambda e: (parse_entry_timestamp(e), e.get('total_tokens', 0)))
    return matches[-1], has_fallback


def _collect():
    now = time.time()
    errors = []
    try:
        p = subprocess.run(['aplexer', 'list', '--all', '--json'], cwd=ROOT, capture_output=True, text=True, timeout=15)
        if p.returncode:
            raise ValueError('aplexer list failed')
        catalog = json.loads(p.stdout)
        if not isinstance(catalog, list):
            raise ValueError('unexpected session schema')
    except (ValueError, OSError, subprocess.TimeoutExpired) as e:
        catalog = []
        errors.append(str(e))

    registry = read_json(ROOT / 'coordination/TEAM-REGISTRY.json', {}) or {}
    tasks_obj = read_json(ROOT / 'coordination/TASKS.json', {}) or {}
    tasks = tasks_obj.get('tasks', []) if isinstance(tasks_obj, dict) else tasks_obj

    # Dynamically resolve product workspaces
    product_workspaces = get_product_workspaces(root=ROOT, registry=registry, catalog=catalog)

    # Ingest teams from registry.teams, registry.projects, registry.delivery_executors
    raw_teams = registry.get('teams', []) if isinstance(registry, dict) else []
    teams_by_id = {}
    for t in raw_teams:
        if isinstance(t, dict) and t.get('id'):
            teams_by_id[t['id']] = dict(t)

    # Ingest product projects as teams (e.g. quota-launcher, agent-coordination, agent-dashboard, agent-branches)
    raw_projects = registry.get('projects', []) if isinstance(registry, dict) else []
    for proj in raw_projects:
        if isinstance(proj, dict) and proj.get('id'):
            pid = proj['id']
            if pid not in teams_by_id:
                teams_by_id[pid] = {
                    'id': pid,
                    'name': proj.get('name', pid),
                    'head_tag': proj.get('head_tag'),
                    'head_session_id': proj.get('head_session_id'),
                    'workspace': proj.get('workspace'),
                    'agents': []
                }
            else:
                existing = teams_by_id[pid]
                if not existing.get('head_tag') and proj.get('head_tag'):
                    existing['head_tag'] = proj['head_tag']
                if not existing.get('head_session_id') and proj.get('head_session_id'):
                    existing['head_session_id'] = proj['head_session_id']
                if not existing.get('workspace') and proj.get('workspace'):
                    existing['workspace'] = proj['workspace']

    # Ingest delivery executors into their respective teams
    raw_executors = registry.get('delivery_executors', []) if isinstance(registry, dict) else []
    for exe in raw_executors:
        if isinstance(exe, dict):
            pid = exe.get('project_id')
            if pid and pid in teams_by_id:
                team_agents = teams_by_id[pid].setdefault('agents', [])
                if not any(a.get('tag') == exe.get('tag') for a in team_agents):
                    item = dict(exe)
                    item.setdefault('role', exe.get('role', 'executor'))
                    team_agents.append(item)

    declared = []
    seen_team_tags = set()
    seen_team_cids = set()
    seen_team_sids = set()
    team_by_session = {}

    for tid, team in teams_by_id.items():
        team_ws = team.get('workspace')
        head_tag = team.get('head_tag')
        head_sid = team.get('head_session_id')
        if head_sid:
            team_by_session[head_sid] = tid

        agents_list = team.get('agents', [])
        # If head_tag is defined on the team/project but missing from agents list, synthesize head item
        if head_tag and not any(a.get('tag') == head_tag for a in agents_list):
            head_item = {
                'tag': head_tag,
                'role': 'head',
                'session_id': head_sid,
                'workspace': team_ws
            }
            declared.append((tid, head_item))
            seen_team_tags.add(head_tag)
            if head_sid: seen_team_sids.add(head_sid)

        for item in agents_list:
            if team_ws and not item.get('workspace'):
                item['workspace'] = team_ws
            tag = item.get('tag')
            declared.append((tid, item))
            if tag: seen_team_tags.add(tag)
            cid = item.get('harness_conversation_id') or item.get('conversation_id')
            if cid: seen_team_cids.add(cid)
            sid = item.get('session_id')
            if sid:
                seen_team_sids.add(sid)
                team_by_session[sid] = tid

    # Also accept top-level agent list
    for item in registry.get('agents', []):
        tag = item.get('tag')
        cid = item.get('harness_conversation_id') or item.get('conversation_id')
        sid = item.get('session_id')
        if sid:
            team_by_session[sid] = item.get('team_id', 'oversight')
        is_distinct = (tag not in seen_team_tags) or (cid and cid not in seen_team_cids) or (sid and sid not in seen_team_sids)
        if is_distinct:
            declared.append((item.get('team_id', 'oversight'), item))

    selected = []
    seen = set()

    for team_id, item in declared:
        tag = item.get('tag')
        expected_ws = item.get('workspace', str(ROOT))
        expected_ws_path = str(pathlib.Path(expected_ws).resolve()) if expected_ws else None

        # Multi-workspace catalog matching:
        # Match by tag and registered workspace (or any product workspace if unconstrained)
        if expected_ws_path:
            matches = [
                s for s in catalog
                if s.get('tag') == tag and s.get('workspace') and str(pathlib.Path(s['workspace']).resolve()) == expected_ws_path
            ]
        else:
            matches = [
                s for s in catalog
                if s.get('tag') == tag and (not s.get('workspace') or str(pathlib.Path(s['workspace']).resolve()) in product_workspaces)
            ]

        # Exact session ID matching
        exact = [s for s in catalog if item.get('session_id') and s.get('id') == item.get('session_id')]
        if exact and exact[0] not in matches:
            matches.insert(0, exact[0])

        matches.sort(key=lambda s: s.get('created_at_ms', 0), reverse=True)
        live = [s for s in matches if proc(s.get('workload_pid')).get('alive')]

        if exact and proc(exact[0].get('workload_pid')).get('alive'):
            choice = exact[0]
            resolution = 'registered exact session'
        elif len(live) == 1:
            choice = live[0]
            resolution = 'single live same-workspace tag'
        elif len(live) > 1:
            choice = None
            resolution = 'ambiguous live tag'
        elif exact:
            choice = exact[0]
            resolution = 'registered dead session'
        else:
            choice = matches[0] if matches else None
            resolution = 'latest dead tag' if matches else 'missing'

        # Disk fallback for sessions pruned from catalog
        if resolution == 'missing' and item.get('session_id'):
            disk = disk_session(item['session_id'], expected_ws)
            if disk:
                choice = disk
                resolution = 'registered completed session on disk'

        if choice:
            seen.add(choice['id'])
            if not item.get('workspace') and choice.get('workspace'):
                item['workspace'] = choice['workspace']

        selected.append((choice, team_id, item, resolution))

    # Multi-workspace unregistered and delegate discovery across all PRODUCT_WORKSPACES
    for s in catalog:
        sw = s.get('workspace') or s.get('cwd')
        sw_resolved = None
        if sw:
            try: sw_resolved = str(pathlib.Path(sw).resolve())
            except Exception: sw_resolved = str(sw)

        if sw_resolved and sw_resolved in product_workspaces and s['id'] not in seen and proc(s.get('workload_pid')).get('alive'):
            parent_sid = s.get('parent_session')
            parent_team = team_by_session.get(parent_sid)
            if parent_team:
                # Delegate discovered for a known team/head
                del_item = {'tag': s.get('tag'), 'role': 'subagent', 'workspace': sw, 'session_id': s.get('id')}
                selected.append((s, parent_team, del_item, f'discovered delegate of head {parent_sid}'))
            else:
                # Unregistered session discovered in a product workspace
                unreg_item = {'tag': s.get('tag'), 'role': 'unknown', 'workspace': sw, 'session_id': s.get('id')}
                selected.append((s, 'unregistered', unreg_item, 'unregistered; launch parent does not imply team'))
            seen.add(s['id'])

    # Multi-workspace OpenCode usage attribution: group assignments by workspace
    opencode_assignments_by_ws = {}
    for team_id, item in declared:
        tag = item.get('tag')
        sid = opencode_sid(item, item.get('telemetry', {}))
        if sid:
            ws = item.get('workspace') or str(ROOT)
            opencode_assignments_by_ws.setdefault(ws, []).append({'conversation_id': sid, 'tag': tag, 'team_id': team_id})

    observer = read_json(STORE / 'observation-state.json', {}) or {}
    try:
        interval_ms = int(dt.datetime.fromisoformat(observer['first_observed_at'].replace('Z', '+00:00')).timestamp() * 1000)
    except (KeyError, ValueError, TypeError):
        interval_ms = int(now * 1000)

    merged_opencode_sessions = []
    merged_by_model = []
    merged_by_team = {}
    merged_stores = []
    opencode_status = 'observed'

    for ws, assigns in opencode_assignments_by_ws.items():
        try:
            ws_path = pathlib.Path(ws).resolve()
            res = read_opencode_usage(ws_path, assigns, interval_ms)
            if res and isinstance(res.get('sessions'), list):
                merged_opencode_sessions.extend(res['sessions'])
                merged_by_model.extend(res.get('by_model', []))
                merged_stores.extend(res.get('stores', []))
                for t, tb in res.get('by_team', {}).items():
                    merged_by_team[t] = tb
        except Exception as e:
            logger.warning("Error reading OpenCode usage for workspace %s: %s", ws, e)

    opencode = {
        'source': OPENCODE_SOURCE,
        'sessions': merged_opencode_sessions,
        'by_model': merged_by_model,
        'by_team': merged_by_team,
        'stores': merged_stores,
        'status': opencode_status if merged_opencode_sessions else 'unknown'
    }
    opencode_by_id = {r['conversation_id']: r for r in opencode['sessions']}

    def opencode_counter(row):
        counters = row['cumulative']
        return {
            **counters,
            'source': OPENCODE_SOURCE,
            'conversation_id': row['conversation_id'],
            'scope': 'Stored conversation cumulative; includes pre-observer history, NOT experiment spending.',
            'cost_usd': counters.get('reported_cost'),
            'cost_basis': 'OpenCode/provider reported estimate, not subscription billing',
            'models': row['models'],
            'interval': row['interval']
        }

    observations = []
    for s, team_id, item, resolution in selected:
        s = s or {}
        usage = native_usage(s) if s.get('id') else None
        tele = item.get('telemetry', {})
        sid = opencode_sid(item, tele)
        if sid in opencode_by_id:
            usage = opencode_counter(opencode_by_id[sid])
        if usage is None:
            rp = rollout_tele_path(tele)
            if rp:
                usage = rollout_usage(rp, tele.get('conversation_id'))
        if usage is None:
            sess_cid = authentic_conversation_id(s, item)
            found, is_fallback = match_usage_event(STORE / 'usage-events.jsonl', item.get('tag'), team_id, sess_cid)
            if found:
                scope = (
                    'Fallback tag-matched owner counters without conversation binding, not independent telemetry verification'
                    if is_fallback else
                    'Exact owner-registered cumulative counters, not independent telemetry verification'
                )
                usage = {**found, 'source': 'owner-metadata-' + found.get('provider', 'unknown') + '-' + found.get('model', 'unknown'), 'scope': scope}

        telemetry = item.get('telemetry', {})
        if telemetry.get('type') == 'claude-result':
            source = read_json(ROOT / telemetry.get('path', ''), {}) or {}
            model_usage = source.get('modelUsage', {})
            if model_usage:
                usage = {
                    'conversation_id': source.get('session_id'),
                    'source': 'claude-result-modelUsage',
                    'scope': 'completed writer result; list-price estimate is not a bill',
                    'models': model_usage,
                    'input_tokens': sum(v.get('inputTokens', 0) + v.get('cacheReadInputTokens', 0) + v.get('cacheCreationInputTokens', 0) for v in model_usage.values()),
                    'output_tokens': sum(v.get('outputTokens', 0) for v in model_usage.values()),
                    'cost_usd': source.get('total_cost_usd'),
                    'cost_basis': 'provider-reported list-price estimate, not actual subscription spend'
                }
                usage['total_tokens'] = usage['input_tokens'] + usage['output_tokens']

        ps = proc(s.get('workload_pid'))
        state = s.get('reported_state')
        stamp = s.get('reported_state_at_ms', s.get('state_reported_at_ms'))
        if not stamp:
            stamp = s.get('last_activity_ms')
        age = max(0, now - stamp / 1000) if isinstance(stamp, (int, float)) else None
        owned = [t for t in tasks if t.get('owner_tag') == item.get('tag')]
        role = item.get('role', 'unknown')
        evidence = []

        # Multi-workspace evidence path scoping:
        # Determine the effective workspace of the agent
        agent_ws_str = item.get('workspace') or (s.get('workspace') if s else None) or str(ROOT)
        try:
            agent_ws = pathlib.Path(agent_ws_str).resolve()
        except Exception:
            agent_ws = ROOT

        registered_paths = sorted({rel for task in owned for rel in task.get('evidence_paths', [])})
        coverage = {
            'registered_distinct_paths': len(registered_paths),
            'missing_paths': [],
            'unsupported_directory_paths': [],
            'out_of_scope_paths': [],
            'scope': 'Registered file metadata only, not accepted outcomes or authorship'
        }
        seen_paths = set()

        for rel in registered_paths:
            rel_p = pathlib.Path(rel)
            if rel_p.is_absolute():
                path = rel_p.resolve()
            else:
                # Prefer path relative to agent's own workspace, fallback to ROOT
                cand = (agent_ws / rel).resolve()
                if cand.exists() or agent_ws in cand.parents or cand == agent_ws:
                    path = cand
                else:
                    path = (ROOT / rel).resolve()

            # Path scoping check: must reside inside agent_ws, ROOT, or any registered product workspace
            in_scope = (
                (agent_ws in path.parents or path == agent_ws) or
                (ROOT in path.parents or path == ROOT) or
                any((pathlib.Path(pw).resolve() in path.parents or path == pathlib.Path(pw).resolve()) for pw in product_workspaces)
            )

            if not in_scope:
                coverage['out_of_scope_paths'].append(rel)
            elif path.is_file():
                if str(path) not in seen_paths:
                    st = path.stat()
                    evidence.append({'path': rel, 'bytes': st.st_size, 'mtime': st.st_mtime})
                    seen_paths.add(str(path))
            elif path.is_dir():
                coverage['unsupported_directory_paths'].append(rel)
            else:
                coverage['missing_paths'].append(rel)

        coverage['observed_distinct_files'] = len(evidence)
        coverage['status'] = (
            'unregistered' if not registered_paths else
            ('partial' if coverage['missing_paths'] or coverage['unsupported_directory_paths'] or coverage['out_of_scope_paths'] else 'observed')
        )

        harness_cid = item.get('harness_conversation_id') or item.get('conversation_id')
        effective_id = s.get('id') or item.get('session_id') or harness_cid
        effective_parent = s.get('parent_session') or item.get('parent_session_id')
        observations.append({
            'id': effective_id,
            'tag': item.get('tag'),
            'team_id': team_id,
            'role': role,
            'responsibility': item.get('responsibility'),
            'workspace': agent_ws_str,
            'counted_as_agent': role in COUNT_ROLES,
            'unregistered': team_id == 'unregistered',
            'resolution': resolution,
            'parent_session': effective_parent,
            'parent_tag': item.get('parent_tag'),
            'harness_conversation_id': harness_cid,
            'mode': item.get('mode'),
            'engine': s.get('engine'),
            'pid_live': ps['alive'],
            'phase': s.get('phase'),
            'reported_state': state,
            'hook_age_seconds': age,
            'hook_age_basis': 'reported_state timestamp if present; otherwise PTY activity proxy',
            'hook_working': ps['alive'] and state == 'working',
            'stale_hook': state is not None and (age is None or age > 300),
            'cpu_seconds': ps.get('cpu_seconds'),
            'rss_bytes': ps.get('rss_bytes'),
            'proc_start_ticks': ps.get('start_ticks'),
            'usage': usage,
            'tasks': [
                {'id': t.get('id'), 'status': t.get('status'), 'updated_at': t.get('updated_at'), 'blocked_on': t.get('blocked_on', []), 'next_action': t.get('next_action')}
                for t in owned
            ],
            'evidence': evidence,
            'evidence_coverage': coverage
        })

    counted = [s for s in observations if s['counted_as_agent']]
    unique_usage = {}
    for row in observations:
        u = row.get('usage')
        if u and u.get('conversation_id'):
            codex_native = u.get('source') in ('codex-native-cumulative', 'codex-rollout')
            key = u['conversation_id'] if codex_native else u['source'] + ':' + u['conversation_id']
            previous = unique_usage.get(key)
            if previous is None or (u.get('total_tokens') or 0) > (previous.get('total_tokens') or 0):
                unique_usage[key] = u

    for row in opencode['sessions']:
        usage = opencode_counter(row)
        unique_usage[OPENCODE_SOURCE + ':' + row['conversation_id']] = usage

    observed_totals = [u['total_tokens'] for u in unique_usage.values() if u.get('total_tokens') is not None]
    known_total = sum(observed_totals) if observed_totals else None

    aggregate = {
        'registered_agents': len(counted),
        'services_and_writers': sum(r['role'] in ('service', 'observer', 'writer', 'scribe') for r in observations),
        'agents_pid_live': sum(r['pid_live'] for r in counted),
        'agents_hook_working': sum(r['hook_working'] for r in counted),
        'unregistered_live': sum(r['unregistered'] and r['pid_live'] for r in observations),
        'known_conversation_tokens': known_total if unique_usage else None,
        'usage_observed_conversations': len(unique_usage),
        'agents_without_token_observation': sum(r['usage'] is None for r in counted),
        'tasks_by_status': {
            status: sum(t.get('status') == status for t in tasks)
            for status in sorted(set(('queued', 'ready', 'running', 'review', 'blocked', 'done', 'cancelled')) | {t.get('status', 'unknown') for t in tasks})
        }
    }
    aggregate['roles'] = {
        role: {
            'registered': sum(r['role'] == role for r in observations),
            'pid_live': sum(r['role'] == role and r['pid_live'] for r in observations),
            'reported_working': sum(r['role'] == role and r['hook_working'] for r in observations)
        }
        for role in ['principal', 'head', 'executor', 'subagent']
    }
    aggregate['reported_idle'] = sum(r['pid_live'] and r['reported_state'] in ('idle', 'waiting') for r in counted)
    aggregate['stale_hook'] = sum(r['stale_hook'] for r in counted)
    aggregate['state_unknown'] = sum(r['pid_live'] and r['reported_state'] is None for r in counted)
    aggregate['fresh_hook_working'] = sum(r['hook_working'] and not r['stale_hook'] for r in counted)

    observation = temporal(STORE, observations, tasks, dt.datetime.now(dt.timezone.utc).isoformat())
    aggregate['tokens_since_observer_known'] = observation['tokens_since_observer_known']
    aggregate['longest_observed_idle_seconds'] = max((r.get('observed_idle_seconds') or 0 for r in counted), default=0)

    disks = {}
    for name, path in [('root', '/'), ('tmp', '/tmp')]:
        try:
            v = os.statvfs(path)
            disks[name] = {'free_bytes': v.f_bavail * v.f_frsize, 'total_bytes': v.f_blocks * v.f_frsize}
        except OSError:
            pass

    snap = {
        'schema_version': 1,
        'at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'aggregate': aggregate,
        'teams': {tid: count_status([r for r in counted if r['team_id'] == tid]) for tid in sorted(set(r['team_id'] for r in observations))},
        'sessions': observations,
        'tasks': tasks,
        'observation': observation,
        'opencode_usage': opencode,
        'quota': quotas(STORE),
        'supervision': read_json(ROOT / '.local/supervision/status.json', {}),
        'host': {'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0), 'disks': disks},
        'errors': errors,
        'limits': [
            'PID live and hook working are observations, never proof of useful work.',
            'Missing token/cost telemetry remains null; known token total is a partial lower bound.',
            'Completed sessions pruned from the live catalog are attributed from on-disk aplexer records or saved rollout telemetry when available; otherwise they stay null.',
            'Cumulative native conversation usage deduplicated across resumed session IDs, rollout files and nested subagents with separate native identity.',
            'CPU/RSS currently workload root process only, excludes descendants.',
            'Services/writers excluded from agent execution totals.',
            'No market/productivity conclusion from agent count, tokens or commits.'
        ]
    }

    with (STORE / 'collector.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        daily = STORE / ('snapshots-' + dt.date.today().isoformat() + '.jsonl')
        retention = archive_history(STORE, daily)
        if retention['total_bytes'] > 256 * 1024 * 1024:
            errors.append('daily snapshot cap reached; latest continues, history paused')
        else:
            history = {
                'at': snap['at'],
                'aggregate': snap['aggregate'],
                'teams': snap['teams'],
                'opencode_usage': opencode,
                'errors': snap['errors'],
                'sessions': [
                    {k: r.get(k) for k in ['id', 'tag', 'team_id', 'role', 'workspace', 'pid_live', 'reported_state', 'hook_age_seconds', 'stale_hook', 'cpu_seconds', 'rss_bytes', 'proc_start_ticks', 'usage', 'observed_idle_seconds', 'evidence', 'evidence_coverage', 'tasks']}
                    for r in observations
                ],
                'tasks': [
                    {key: t.get(key) for key in ['id', 'status', 'owner_tag', 'team_id', 'next_action', 'acceptance', 'acceptance_status', 'reviewer_tag', 'evidence_paths', 'blocked_on', 'assignment_ack', 'updated_at']}
                    for t in tasks
                ]
            }
            with daily.open('a') as f:
                f.write(json.dumps(history) + '\n')
            try:
                os.chmod(daily, 0o600)
            except OSError:
                pass
        atomic(STORE / 'latest.json', snap)

    return snap


def collect(product_workspaces=None):
    if product_workspaces is not None:
        global PRODUCT_WORKSPACES
        PRODUCT_WORKSPACES = list(product_workspaces)
    with (STORE / 'sample.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _collect()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/api/latest', '/api/tasks'):
            value = read_json(STORE / 'latest.json', {})
            if self.path == '/api/tasks':
                value = value.get('tasks', [])
            data = json.dumps(value).encode()
            kind = 'application/json'
        elif self.path == '/':
            dashboard_path = ROOT / 'scripts/metrics/dashboard.html'
            data = dashboard_path.read_bytes() if dashboard_path.exists() else b'<h1>Dashboard</h1>'
            kind = 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--loop', action='store_true')
    ap.add_argument('--interval', type=int, default=60)
    ap.add_argument('--serve', action='store_true')
    ap.add_argument('--port', type=int, default=8766)
    args = ap.parse_args()
    if not args.loop:
        snap = collect()
        print(json.dumps({'at': snap['at'], 'aggregate': snap['aggregate'], 'errors': snap['errors']}))
        return
    with (STORE / 'service.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('metrics service already running')
        if args.serve:
            server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        stopping = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stopping.set())
        signal.signal(signal.SIGINT, lambda *_: stopping.set())
        while not stopping.is_set():
            try:
                collect()
            except Exception as exc:
                atomic(STORE / 'service-error.json', {'at': time.time(), 'error_type': type(exc).__name__})
            stopping.wait(max(30, args.interval))


if __name__ == '__main__':
    main()
