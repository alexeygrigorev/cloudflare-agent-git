#!/usr/bin/env python3
"""
Principal event watchdog candidate with product-aware entity routing.
Extends supervision to active products ('projects' in TEAM-REGISTRY.json)
alongside legacy research 'teams', supporting project aliases, deterministic
head completion tracking, and categorized ready vs running queues.
(C1629 / C1630 / C1444)
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import uuid

# Ensure scripts/supervision modules (ack_reconciliation, retention, terminal_consumer) are importable
_SUPERVISION_DIR = pathlib.Path(__file__).resolve().parent
if str(_SUPERVISION_DIR) not in sys.path:
    sys.path.insert(0, str(_SUPERVISION_DIR))

from ack_reconciliation import exact_ack
from retention import StorageFull, archive_operational, archive_verified, read_archived, storage_guard
from terminal_consumer import TerminalConsumer, is_safe_identifier

ROOT = pathlib.Path('/home/alexey/git/cloudflare-agent-git')
PRIVATE = ROOT / '.local/supervision'
BINARY = os.environ.get('SUPERVISION_APLEXER_BINARY', '/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer')
ALL_KNOWN_PRINCIPALS = ('codex-principal', 'claude-principal')
PRINCIPALS = ALL_KNOWN_PRINCIPALS  # backward-compatibility alias

# Known project aliases for symmetric routing and normalization
KNOWN_PROJECT_ALIASES = {
    'agent-quota-launcher': 'quota-launcher',
    'quota-launcher': 'quota-launcher',
    'launcher': 'quota-launcher',
    'agent-branches': 'agent-branches',
    'branches': 'agent-branches',
    'agent-dashboard': 'agent-dashboard',
    'dashboard': 'agent-dashboard',
    'agent-coordination': 'agent-coordination',
    'coordination': 'agent-coordination',
    'cross-computer-agent-coordination': 'agent-coordination',
    'cross-computer-coordination': 'agent-coordination',
}


def normalize_project_id(pid):
    """Normalize a project or team ID to its canonical product identifier."""
    if not pid or not isinstance(pid, str):
        return None
    p = pid.strip().lower()
    return KNOWN_PROJECT_ALIASES.get(p, p)


def extract_supervision_entities(registry_full):
    """
    Extract and normalize BOTH teams and projects from TEAM-REGISTRY.json.
    Ensures that active product projects (agent-branches, agent-dashboard,
    quota-launcher, agent-coordination) are fully represented as supervision
    entities with appropriate principal_tags, head_tag, and workspace.
    """
    entities = []
    seen_ids = set()

    if isinstance(registry_full, list):
        raw_teams = registry_full
        raw_projects = []
    elif isinstance(registry_full, dict):
        raw_teams = registry_full.get('teams', [])
        raw_projects = registry_full.get('projects', [])
    else:
        raw_teams = []
        raw_projects = []

    # 1. Process teams
    seen_entities = {}
    for team in raw_teams:
        tid = team.get('id')
        if not tid:
            continue
        norm_tid = normalize_project_id(tid) or tid
        aliases = {tid}
        if norm_tid:
            aliases.add(norm_tid)
        for k, v in KNOWN_PROJECT_ALIASES.items():
            if v == tid or v == norm_tid:
                aliases.add(k)

        team_entity = {
            'id': tid,
            'name': team.get('name', tid),
            'kind': 'team',
            'principal_tags': list(team.get('principal_tags', [])),
            'head_tag': team.get('head_tag'),
            'workspace': team.get('workspace'),
            'agents': team.get('agents', []),
            'aliases': sorted(aliases),
            'raw': team,
            'unowned': len(team.get('principal_tags', [])) == 0,
            'conflict': None,
        }
        entities.append(team_entity)
        seen_entities[norm_tid] = team_entity
        seen_ids.add(tid)

    # 2. Process projects
    for project in raw_projects:
        pid = project.get('id')
        if not pid:
            continue

        # Determine principal tags without invented fallbacks (C1634/C1636):
        # Distinguish explicit empty list ('principal_tags': []) from absent field!
        # If 'principal_tags' key is explicitly present in project, respect it directly (including []).
        if 'principal_tags' in project:
            val = project['principal_tags']
            principal_tags = list(val) if isinstance(val, (list, tuple)) else ([val] if val else [])
        else:
            owner = project.get('principal_owner')
            if isinstance(owner, dict) and owner.get('tag'):
                principal_tags = [owner['tag']]
            elif isinstance(owner, str) and owner.strip():
                principal_tags = [owner.strip()]
            elif isinstance(project.get('assignment_ack', {}).get('principal_owner'), dict):
                ack_owner = project['assignment_ack']['principal_owner'].get('tag')
                principal_tags = [ack_owner] if ack_owner else []
            else:
                principal_tags = []

        norm_pid = normalize_project_id(pid) or pid
        aliases = {pid}
        if norm_pid:
            aliases.add(norm_pid)
        for k, v in KNOWN_PROJECT_ALIASES.items():
            if v == pid or v == norm_pid:
                aliases.add(k)

        # Check for conflicts or existing matching entity
        conflict_info = None
        if norm_pid in seen_entities:
            existing = seen_entities[norm_pid]
            # Detect conflicting head_tag, workspace, or principal_tags
            head_mismatch = existing.get('head_tag') and project.get('head_tag') and existing.get('head_tag') != project.get('head_tag')
            ws_mismatch = existing.get('workspace') and project.get('workspace') and existing.get('workspace') != project.get('workspace')
            principal_mismatch = bool(existing.get('principal_tags') and principal_tags and set(existing['principal_tags']) != set(principal_tags))
            
            if head_mismatch or ws_mismatch or principal_mismatch:
                reasons = []
                if head_mismatch:
                    reasons.append(f"head_tag ({existing.get('head_tag')} vs {project.get('head_tag')})")
                if ws_mismatch:
                    reasons.append(f"workspace ({existing.get('workspace')} vs {project.get('workspace')})")
                if principal_mismatch:
                    reasons.append(f"principal_tags ({existing.get('principal_tags')} vs {principal_tags})")
                conflict_info = {
                    'detected': True,
                    'conflict_with': existing['id'],
                    'reasons': reasons,
                    'summary': f"Conflicting registration for {norm_pid}: " + "; ".join(reasons)
                }
                # Mutual conflict marking (C1636): flag both conflicting entities
                existing['conflict'] = conflict_info
            else:
                # Compatible duplicate: merge aliases, preserve nonempty head/workspace from project (C1636)
                merged_aliases = set(existing.get('aliases', [])) | aliases
                existing['aliases'] = sorted(merged_aliases)
                if not existing.get('head_tag') and project.get('head_tag'):
                    existing['head_tag'] = project['head_tag']
                if not existing.get('workspace') and project.get('workspace'):
                    existing['workspace'] = project['workspace']
                if not existing.get('principal_tags') and principal_tags:
                    existing['principal_tags'] = list(principal_tags)
                    existing['unowned'] = False
                existing['kind'] = 'team_and_project'
                continue

        project_entity = {
            'id': pid,
            'name': project.get('name', pid),
            'kind': 'project',
            'principal_tags': list(principal_tags),
            'head_tag': project.get('head_tag'),
            'workspace': project.get('workspace'),
            'agents': project.get('agents', []),
            'aliases': sorted(aliases),
            'raw': project,
            'unowned': len(principal_tags) == 0,
            'conflict': conflict_info,
        }
        entities.append(project_entity)
        if not conflict_info:
            seen_entities[norm_pid] = project_entity
        seen_ids.add(pid)

    return entities


def task_matches_entity(t, entity):
    """
    Task matching per C1629/C1630:
    A task matches an entity if:
    t.get('team_id') == entity['id'] or
    t.get('project_id') == entity['id'] or
    normalize_project_id(t.get('team_id')) == entity['id'] or
    normalize_project_id(t.get('project_id')) == entity['id']
    Also checks normalized entity ID and entity aliases.
    """
    eid = entity.get('id')
    if not eid:
        return False

    norm_eid = normalize_project_id(eid)
    team_id = t.get('team_id')
    proj_id = t.get('project_id')

    # Direct match on entity id
    if team_id == eid or proj_id == eid:
        return True

    norm_team = normalize_project_id(team_id) if team_id else None
    norm_proj = normalize_project_id(proj_id) if proj_id else None

    if norm_team and (norm_team == eid or norm_team == norm_eid):
        return True
    if norm_proj and (norm_proj == eid or norm_proj == norm_eid):
        return True

    aliases = entity.get('aliases', [])
    if team_id in aliases or proj_id in aliases:
        return True
    if norm_team and norm_team in aliases:
        return True
    if norm_proj and norm_proj in aliases:
        return True

    return False


def active_principals(teams_data=None, spool=None, registry_raw=None):
    """
    Dynamically determine active principals, honoring quiet/morning-only status,
    exclusion files, and environment overrides (C-1396).
    Accepts either legacy teams list or normalized supervision entities list.
    """
    excluded = set()
    env_ex = os.environ.get('SUPERVISION_EXCLUDE_PRINCIPALS', '')
    if env_ex:
        for item in env_ex.split(','):
            if item.strip():
                excluded.add(item.strip())
    if spool:
        for ex_file in (spool / 'excluded-principals.json', spool / 'excluded_principals.json'):
            if ex_file.exists():
                try:
                    loaded = json.loads(ex_file.read_text())
                    if isinstance(loaded, list):
                        excluded.update(loaded)
                    elif isinstance(loaded, dict) and 'excluded' in loaded:
                        excluded.update(loaded['excluded'])
                except Exception:
                    pass
    if registry_raw and isinstance(registry_raw, dict):
        if 'excluded_principals' in registry_raw and isinstance(registry_raw['excluded_principals'], list):
            excluded.update(registry_raw['excluded_principals'])
        for a in registry_raw.get('agents', []):
            tag = a.get('tag')
            if tag and (a.get('status') in ('quiet', 'morning-only', 'paused', 'inactive', 'offline', 'exited') or a.get('active') is False or a.get('supervision_excluded') is True):
                excluded.add(tag)
        for t in registry_raw.get('teams', []):
            for a in t.get('agents', []):
                tag = a.get('tag')
                if tag and (a.get('status') in ('quiet', 'morning-only', 'paused', 'inactive', 'offline', 'exited') or a.get('active') is False or a.get('supervision_excluded') is True):
                    excluded.add(tag)

    candidates = list(ALL_KNOWN_PRINCIPALS)
    if teams_data and isinstance(teams_data, list):
        for team in teams_data:
            for ptag in team.get('principal_tags', []):
                if ptag not in candidates:
                    candidates.append(ptag)
    return [tag for tag in candidates if tag not in excluded]


def active_heads(entities=None, spool=None, registry_raw=None):
    """
    Dynamically determine active project/team heads from supervision entities
    and TEAM-REGISTRY.json, honoring exclusion files, status, and environment overrides.
    """
    excluded = set()
    env_ex = os.environ.get('SUPERVISION_EXCLUDE_HEADS', '')
    if env_ex:
        for item in env_ex.split(','):
            if item.strip():
                excluded.add(item.strip())
    if spool:
        for ex_file in (spool / 'excluded-heads.json', spool / 'excluded_heads.json'):
            if ex_file.exists():
                try:
                    loaded = json.loads(ex_file.read_text())
                    if isinstance(loaded, list):
                        excluded.update(loaded)
                    elif isinstance(loaded, dict) and 'excluded' in loaded:
                        excluded.update(loaded['excluded'])
                except Exception:
                    pass
    if registry_raw and isinstance(registry_raw, dict):
        if 'excluded_heads' in registry_raw and isinstance(registry_raw['excluded_heads'], list):
            excluded.update(registry_raw['excluded_heads'])
        for a in registry_raw.get('agents', []):
            tag = a.get('tag')
            if tag and (a.get('status') in ('quiet', 'morning-only', 'paused', 'inactive', 'offline', 'exited') or a.get('active') is False or a.get('supervision_excluded') is True):
                excluded.add(tag)
        for t in registry_raw.get('teams', []):
            for a in t.get('agents', []):
                tag = a.get('tag')
                if tag and (a.get('status') in ('quiet', 'morning-only', 'paused', 'inactive', 'offline', 'exited') or a.get('active') is False or a.get('supervision_excluded') is True):
                    excluded.add(tag)
        for p in registry_raw.get('projects', []):
            for a in p.get('agents', []):
                tag = a.get('tag')
                if tag and (a.get('status') in ('quiet', 'morning-only', 'paused', 'inactive', 'offline', 'exited') or a.get('active') is False or a.get('supervision_excluded') is True):
                    excluded.add(tag)

    candidates = set()
    # Explicitly ensure active Bus327 recovery head is supervised
    candidates.add('zcode-bus-win35-recovery-head-20261006-resume')
    if entities and isinstance(entities, list):
        for e in entities:
            ht = e.get('head_tag')
            if ht and ht not in ALL_KNOWN_PRINCIPALS and is_safe_identifier(ht):
                candidates.add(ht)
    if registry_raw and isinstance(registry_raw, dict):
        for group in (registry_raw.get('teams', []), registry_raw.get('projects', [])):
            for item in group:
                ht = item.get('head_tag')
                if ht and ht not in ALL_KNOWN_PRINCIPALS and is_safe_identifier(ht):
                    candidates.add(ht)
                for a in item.get('agents', []):
                    if a.get('role') == 'head' and a.get('tag') and a['tag'] not in ALL_KNOWN_PRINCIPALS and is_safe_identifier(a['tag']):
                        candidates.add(a['tag'])
        for a in registry_raw.get('agents', []):
            if a.get('role') == 'head' and a.get('tag') and a['tag'] not in ALL_KNOWN_PRINCIPALS and is_safe_identifier(a['tag']):
                candidates.add(a['tag'])

    return sorted([tag for tag in candidates if tag not in excluded])


OBSOLETE_OWNER_PATTERNS = ('grok', 'claude')
LEGACY_ANT_TAGS = {
    'antigravity-head',
    'antigravity-head-legacy-a16',
    'ant-head-operational-resume-20261005',
    'antigravity-head-gemini-recovery',
    'ant-head-continuation-custody-20261006',
}
DORMANT_TEAMS = {'a06-a10', 'a01-harness', 'a05', 'a16-runtime-protocol'}
ACTIVE_CUSTODY_TAGS_DEFAULT = {
    'ant-head-never-timer-custody-20261006',
    'ql-head-feedback-custody-20261006',
    'coord-917-custody-resume-20261006',
    'public-journal-release-custody-20261006',
    'codex-principal',
    'agent-dashboard-head',
    'failover-primary',
    'zcode-bus-win35-recovery-head-20261006-resume',
}


def is_task_eligible_for_supervision(task, sessions=None, active_heads=None, active_principals=None):
    """
    Filter out obsolete owners (Grok, stopped Claude, legacy Ant) and ancient running labels
    from displacing genuine ready tasks in principal/head supervision payloads (C3025).

    Criteria:
    1. Obsolete / decommissioned owners:
       - Grok: any owner containing 'grok' (e.g. 'grok-head', 'grok')
       - Stopped Claude: any owner starting with 'claude' or 'claude-principal'
         (Claude is a monitoring principal peer, not an implementation worker per user26)
       - Legacy Ant: 'antigravity-head', 'antigravity-head-legacy-a16',
         'ant-head-operational-resume-20261005', 'antigravity-head-gemini-recovery',
         'ant-head-continuation-custody-20261006' (only current active custody session
         'ant-head-never-timer-custody-20261006' or live running session in sessions is eligible)
    2. Dormant older research teams:
       - 'a06-a10', 'a01-harness', 'a05', 'a16-runtime-protocol' (preserved history only,
         superseded by active delivery reset per human 4 Oct 2026)
    3. Ancient running labels:
       - Tasks marked ('running', 'in_progress', 'working') must have an owner in active custody
         or currently running aplexer sessions. If owner is missing, obsolete, or not actively running,
         the running label is stale and must not be prioritized as active work.
    4. Ready / queued tasks:
       - If owner is specified, it must not be an obsolete/stopped owner. If unowned (None or ''),
         it is eligible ready work awaiting dispatch.
    """
    owner = (task.get('owner_tag') or task.get('owner') or '').strip()
    status = task.get('status')
    team = task.get('team_id') or ''

    # 1. Obsolete owner prefix check (Grok, Claude)
    if any(owner.lower().startswith(p) for p in OBSOLETE_OWNER_PATTERNS):
        return False

    # 2. Legacy Ant tags check
    if owner in LEGACY_ANT_TAGS:
        return False

    # Build active custody set
    active_custody = set(ACTIVE_CUSTODY_TAGS_DEFAULT)
    if active_heads:
        active_custody.update(active_heads)
    if active_principals:
        active_custody.update(active_principals)
    if sessions and isinstance(sessions, list):
        for s in sessions:
            if s.get('reported_state') != 'exited':
                tag = s.get('tag')
                if tag:
                    active_custody.add(tag)

    # Sanitize active custody against obsolete tags
    active_custody = {
        t for t in active_custody
        if not any(t.lower().startswith(p) for p in OBSOLETE_OWNER_PATTERNS)
        and t not in LEGACY_ANT_TAGS
    }

    # 3. Dormant older research teams:
    # Preserved research history is suppressed unless the task has been explicitly
    # reacquired by a confirmed active custody session (reopened lane).
    if team in DORMANT_TEAMS:
        if not (owner and owner in active_custody):
            return False

    # 4. Ancient running labels:
    # If a task is marked running/in_progress/working, its owner must be in active custody.
    if status in ('running', 'in_progress', 'working'):
        if not owner or owner not in active_custody:
            return False

    # 5. Ready/queued tasks:
    # If owner is specified, it must not be obsolete or legacy.
    if status in ('ready', 'queued') and owner:
        if any(owner.lower().startswith(p) for p in OBSOLETE_OWNER_PATTERNS) or owner in LEGACY_ANT_TAGS:
            return False

    return True


def get_designated_head_owner(task, entities):
    """
    Determine the designated head owner for a task from its explicit fields
    or matching supervision entity.
    """
    def _is_eligible_head(candidate):
        if not candidate or not is_safe_identifier(candidate) or candidate in ALL_KNOWN_PRINCIPALS:
            return False
        if any(candidate.lower().startswith(p) for p in OBSOLETE_OWNER_PATTERNS) or candidate in LEGACY_ANT_TAGS:
            return False
        return True

    head = task.get('head_owner')
    if _is_eligible_head(head):
        return head
    owner = task.get('owner_tag') or task.get('owner')
    if _is_eligible_head(owner):
        for e in entities:
            if e.get('head_tag') == owner:
                return owner
        if owner.endswith('-head') or 'head' in owner:
            return owner
    for e in entities:
        if task_matches_entity(task, e):
            ht = e.get('head_tag')
            if _is_eligible_head(ht):
                return ht
    return None


def get_ql_db_candidates(root=None, private=None):
    """
    Return candidate launcher databases for ingestion and bridging.
    When running under a test harness or non-canonical ROOT, avoids touching
    live production agent-quota-launcher databases unless explicitly overridden.
    """
    if root is None:
        root = ROOT
    if private is None:
        private = PRIVATE
    env_override = os.environ.get('SUPERVISION_QL_DB_PATHS')
    if env_override:
        return [pathlib.Path(p.strip()) for p in env_override.split(',') if p.strip()]
    if pathlib.Path(root).resolve() != pathlib.Path('/home/alexey/git/cloudflare-agent-git').resolve():
        test_db = pathlib.Path(private) / 'launcher' / 'state.db'
        return [test_db] if test_db.exists() else []
    return [
        pathlib.Path('/home/alexey/git/agent-quota-launcher/.local/launcher-config/state.db'),
        pathlib.Path('/home/alexey/git/agent-quota-launcher/.local/scale50/wt-gemini-head/.config/ql/state.db'),
        pathlib.Path('/home/alexey/git/agent-quota-launcher/.local/state.db'),
    ]


def bridge_ready_task_to_launcher(task, head_owner, spool_dir, ql_db_candidates=None):
    """
    Bridge a task transitioning to READY with a designated head owner to a durable
    enqueue event and launcher enqueue rather than keeping it memory-only.
    Persists durable intent file under .local/supervision/enqueued/{task_id}.json.
    """
    spool_dir = pathlib.Path(spool_dir)
    enqueued_dir = spool_dir / 'enqueued'
    enqueued_dir.mkdir(parents=True, exist_ok=True)
    task_id = task['id']
    enqueue_file = enqueued_dir / f"{task_id}.json"

    payload = {
        "task_id": task_id,
        "goal": task.get("title") or task.get("goal") or task_id,
        "owner": head_owner,
        "cwd": task.get("workspace") or str(ROOT),
        "timeout": task.get("timeout", 3600),
        "project_id": task.get("project_id") or task.get("team_id"),
        "status": "ready",
        "model_requirements": task.get("model_requirements") or {"providers": ["antigravity", "zai"]},
    }
    raw_key = json.dumps(payload, sort_keys=True)
    idempotency_key = f"ql-enqueue-{task_id}-" + hashlib.sha256(raw_key.encode()).hexdigest()[:12]

    record = {
        "task_id": task_id,
        "head_owner": head_owner,
        "project_id": payload["project_id"],
        "idempotency_key": idempotency_key,
        "status": "enqueued",
        "enqueued_at": now(),
        "payload": payload,
        "launcher_submitted": False,
    }

    if ql_db_candidates is None:
        ql_db_candidates = get_ql_db_candidates(ROOT, spool_dir)

    if ql_db_candidates:
        import sqlite3
        for ql_db in ql_db_candidates:
            ql_path = pathlib.Path(ql_db)
            if ql_path.exists():
                try:
                    conn = sqlite3.connect(str(ql_path), timeout=5.0)
                    with conn:
                        cur = conn.cursor()
                        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
                        if cur.fetchone():
                            cur.execute("SELECT id FROM tasks WHERE id = ? OR idempotency_key = ?", (task_id, idempotency_key))
                            existing_row = cur.fetchone()
                            if not existing_row:
                                payload_str = json.dumps(payload, sort_keys=True)
                                cur.execute(
                                    "INSERT INTO tasks (id, idempotency_key, payload, state, created_at, updated_at) "
                                    "VALUES (?, ?, ?, 'queued', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                                    (task_id, idempotency_key, payload_str),
                                )
                                record["launcher_submitted"] = True
                                record["launcher_db"] = str(ql_path)
                    conn.close()
                    if record["launcher_submitted"]:
                        break
                except Exception as exc:
                    record["launcher_error"] = str(exc)

    atomic(enqueue_file, record)
    return record


def drain_launcher_queues(ql_db_candidates, report=None):
    """
    Runs watch_loop(drain_args, max_passes=1) with backend="task-units" and
    wait_for_review="dependencies" for each launcher candidate DB.
    Catches any exceptions gracefully and records action 'launcher-queue-drained'.
    """
    actions = []
    if not ql_db_candidates:
        return actions

    ql_repo = pathlib.Path('/home/alexey/git/agent-quota-launcher')
    if ql_repo.exists() and str(ql_repo) not in sys.path:
        sys.path.insert(0, str(ql_repo))

    try:
        from launcher.watch import watch_loop
    except Exception:
        watch_loop = None

    from types import SimpleNamespace

    for cand in ql_db_candidates:
        cand_path = pathlib.Path(cand)
        config_dir = cand_path.parent if (cand_path.is_file() or cand_path.suffix == '.db') else cand_path
        action_rec = {
            'kind': 'launcher-queue-drained',
            'action': 'launcher-queue-drained',
            'db': str(cand_path),
            'status': 'ok',
        }
        try:
            if watch_loop is None:
                raise RuntimeError("launcher.watch.watch_loop could not be imported")

            drain_args = SimpleNamespace(
                config_dir=str(config_dir),
                backend="task-units",
                wait_for_review="dependencies",
                once=True,
            )
            watch_loop(drain_args, max_passes=1)
        except Exception as exc:
            action_rec['status'] = 'error'
            action_rec['error'] = str(exc)

        actions.append(action_rec)
        if report is not None and isinstance(report.get('actions'), list):
            report['actions'].append(action_rec)

    return actions


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def process_due_callbacks(spool, binary, identity_id, supports_key, command, recorded_send, sessions):
    """Process durable scheduled due callbacks without separate timers or schedulers."""
    cb_path = spool / 'due_callbacks.json'
    if not cb_path.exists():
        return []
    try:
        data = json.loads(cb_path.read_text())
    except Exception:
        return []
    callbacks = data.get('callbacks', [])
    now_ts = time.time()
    updated = False
    delivered_list = []
    for cb in callbacks:
        if cb.get('delivered'):
            continue
        due_at_str = cb.get('due_at')
        if not due_at_str:
            continue
        try:
            dt_obj = datetime.datetime.fromisoformat(due_at_str)
            if dt_obj.tzinfo is None:
                dt_obj = dt_obj.replace(tzinfo=datetime.timezone.utc)
            due_ts = dt_obj.timestamp()
        except Exception:
            continue
        if now_ts >= due_ts:
            target_tag = cb.get('recipient_tag')
            expected_session_id = cb.get('recipient_session_id')

            # Anti-tag-reassignment check:
            # If expected_session_id is declared, reject any session where tag matches but session_id differs.
            if target_tag and expected_session_id:
                reassigned = [s for s in sessions if s.get('tag') == target_tag and s.get('id') != expected_session_id]
                if reassigned:
                    # Tag was rebound to a different session; reject delivery to imposter
                    continue

            matching = [s for s in sessions if (not target_tag or s.get('tag') == target_tag) and (not expected_session_id or s.get('id') == expected_session_id)]
            if not matching:
                continue
            sess = matching[0]
            pid = sess.get('workload_pid')
            if not (pid and pathlib.Path(f'/proc/{pid}').exists()):
                continue

            # Readiness & resting-state check: protect busy/working/draft states
            reported_state = sess.get('reported_state')
            if reported_state in ('busy', 'working', 'draft', 'menu-or-draft'):
                continue

            prompt = cb.get('prompt', '')
            cb_id = cb.get('id', 'anon-due')
            receipt = recorded_send(binary, target_tag or sess.get('tag'), f"due-{cb_id}", prompt, spool, identity_id, supports_key)
            atomic(spool / f"receipt-due-{cb_id}.json", receipt)
            cb['delivered'] = True
            cb['delivered_at'] = now()
            cb['receipt_id'] = receipt.get('message', receipt).get('id')
            updated = True
            delivered_list.append(cb_id)
    if updated:
        atomic(cb_path, data)
    return delivered_list


def atomic(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2))
    tmp.replace(path)


class MailboxBusy(Exception):
    """Aplexer workspace mailbox lock stayed busy through all bounded retries."""


class MutationUncertain(Exception):
    """A mutating call hit a busy-like failure after exactly one invocation; outcome UNKNOWN."""
    def __init__(self, cmd, stderr, returncode):
        self.cmd = list(cmd)
        self.stderr = stderr
        self.returncode = returncode
        super().__init__(f'{type(self).__name__}: single invocation, no retry, outcome UNKNOWN: {cmd[1:3]} rc={returncode}; stderr[:200]: {stderr[:200]}')

    def uncertain_record(self):
        return {'outcome': 'UNKNOWN', 'class': type(self).__name__, 'cmd': self.cmd, 'stderr': self.stderr[:200], 'returncode': self.returncode}


class DeliveryUncertain(MutationUncertain):
    """send/reply/deliver busy-like failure; never retried, never re-sent with a new id."""


class AckUncertain(MutationUncertain):
    """ack busy-like failure; acknowledgement state unknown, never retried."""


MAILBOX_BUSY = re.compile(r'is busy, retry|Resource temporarily unavailable')
BUSY_BACKOFF = (0.2, 0.4, 0.8, 1.6, 3.2)
# Explicit allowlist: only these aplexer subcommands are read-only observations.
READ_ONLY_VERBS = (
    ('list',), ('status',), ('whoami',), ('capture',), ('help',),
    ('message', 'inbox'), ('message', 'log'), ('message', 'show'),
)
UNCERTAIN_BY_VERB = {
    ('message', 'send'): DeliveryUncertain,
    ('message', 'reply'): DeliveryUncertain,
    ('message', 'deliver'): DeliveryUncertain,
    ('message', 'ack'): AckUncertain,
}


def aplexer_verb(args):
    """Leading positional subcommand words; binary name and options are skipped."""
    words = []
    for token in args[1:]:
        if token.startswith('-'):
            break
        words.append(token)
        if len(words) == 2:
            break
    return tuple(words)


def read_only(args):
    """Allowlist membership only: positional verb prefix (plus --help), never a substring guess."""
    if '--help' in args:
        return True
    words = aplexer_verb(args)
    return any(words[:len(entry)] == entry for entry in READ_ONLY_VERBS)


def command(args, timeout=20):
    """Read-only aplexer observations retry on busy; every mutating call runs exactly once."""
    retrying = read_only(args)
    backoff = BUSY_BACKOFF
    while True:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if not result.returncode:
            return result.stdout
        stderr = (result.stderr or '').strip()
        busy = MAILBOX_BUSY.search(stderr)
        if not busy:
            raise RuntimeError(f'command failed: {args[1:3]} rc={result.returncode}; stderr[:200]: {stderr[:200]}')
        if not retrying:
            raise UNCERTAIN_BY_VERB.get(aplexer_verb(args), MutationUncertain)(args, stderr, result.returncode)
        if not backoff:
            raise MailboxBusy(f'command failed: {args[1:3]} rc={result.returncode} mailbox busy after {len(BUSY_BACKOFF)} retries; stderr[:200]: {stderr[:200]}')
        time.sleep(backoff[0])
        backoff = backoff[1:]


def record_cycle_failure(report, exc):
    """Any failed cycle is degraded with an error-class observation, never a healthy all-clear."""
    report['errors'].append(str(exc))
    report['degraded'] = True
    report['observation'] = f'incomplete-cycle: {type(exc).__name__}'
    if isinstance(exc, MutationUncertain):
        report['uncertain_outcome'] = exc.uncertain_record()


ANSI_ESCAPE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub('', text)


COMPOSER_TAIL_CHROME_RE = re.compile(
    r'^\s*[─━_=-]+\s*$'
    r'|.*(?:Context|for shortcuts|auto mode|manage|monitor|agents|tokens|GPT-|Gemini|glm-|usage|workspace|warning|Worked for|Ask Codex)'
    r'|.*(?:Aplexer awareness|Before editing files|Declare your work|Check peer mail|participate in \d+ workspace|Workspace coordination|git:\s*worktree|you:\s*\S+|peers\s*\(\d+\)|shared paths|peer-provided data).*'
)

DEFAULT_PROMPT_PLACEHOLDERS = {'Ask Codex to do anything', '? for shortcuts'}


def composer(screen, tag=None):
    """Last prompt, never transcript prompts; unknown and menus deny input."""
    clean_screen = strip_ansi(screen)

    if re.search(r'How is Claude doing|Choose|Select|feedback', clean_screen, re.I):
        return 'menu-or-draft'
    if re.search(r'Working \(|esc to interrupt|esc interrupt', clean_screen, re.I):
        return 'busy'

    lines = clean_screen.splitlines()
    starts = [(i, re.sub(r'^\s*[›❯>]\s*', '', line).strip())
              for i, line in enumerate(lines) if re.match(r'^\s*(?:[›❯]|>(?:\s|$))', line)]
    if not starts:
        return 'unknown'

    index, content = starts[-1]

    for line in lines[index + 1:]:
        if not line.strip():
            continue
        if not COMPOSER_TAIL_CHROME_RE.search(line):
            return 'unknown'

    if content and content not in DEFAULT_PROMPT_PLACEHOLDERS and not content.startswith('? for shortcuts'):
        return 'draft'

    return 'empty'



def quota_allowed(data):
    try:
        provider = data['codex']
        if provider.get('status') != 'ok' or provider.get('error') or provider.get('details', {}).get('limit_reached'):
            return False
        windows = [x.get('percent_remaining') for x in provider['windows'].values()
                   if x.get('percent_remaining') is not None]
        return bool(windows) and all(float(x) > 15 for x in windows)
    except (KeyError, TypeError, ValueError):
        return False


class ActiveTaskList(list):
    """List of active tasks with structured attributes for completions and queues."""
    def __init__(self, items=(), completed=None, ready=None, running=None, recent_completed=None):
        super().__init__(items)
        self.completed = completed or []
        self.ready = ready or []
        self.running = running or []
        self.recent_completed = recent_completed or (completed or [])


class TaskEventResult(tuple):
    """
    Subclass of tuple: (active, digest, counts).
    Unpacks cleanly as (active, digest, counts) for 100% backward compatibility.
    Provides attributes:
    .active, .digest, .counts, .completed, .ready, .running, .recent_completed
    """
    def __new__(cls, active, digest, counts, completed=None, ready=None, running=None, recent_completed=None):
        return super().__new__(cls, (active, digest, counts))

    def __init__(self, active, digest, counts, completed=None, ready=None, running=None, recent_completed=None):
        self.active = active
        self.digest = digest
        self.counts = counts
        self.completed = completed or []
        self.ready = ready or []
        self.running = running or []
        self.recent_completed = recent_completed or (completed or [])


def task_event(tasks):
    """
    Extract active tasks, track recent completions deterministically,
    and compute stable task event digest and queue counts (C1629/C1630).
    """
    active = [t for t in tasks if t.get('status') not in ('completed', 'done', 'cancelled', 'rejected', 'parked', 'on_hold')]
    completed = [t for t in tasks if t.get('status') in ('completed', 'done')]
    # Stable sort completed by timestamp (newest first)
    completed.sort(key=lambda t: t.get('completed_at') or t.get('updated_at') or '', reverse=True)

    ready = [t for t in active if t.get('status') in ('ready', 'queued')]
    running = [t for t in active if t.get('status') in ('running', 'in_progress', 'working')]

    active_meaningful = sorted(
        [{
            'id': t.get('id'),
            'team_id': t.get('team_id'),
            'project_id': t.get('project_id'),
            'owner_tag': t.get('owner_tag') or t.get('owner'),
            'status': t.get('status'),
            'blocked_on': t.get('blocked_on'),
            'next_action': t.get('next_action'),
            'evidence_paths': t.get('evidence_paths'),
        } for t in active],
        key=lambda x: str(x.get('id', ''))
    )
    completed_meaningful = sorted(
        [{
            'id': t.get('id'),
            'team_id': t.get('team_id'),
            'project_id': t.get('project_id'),
            'owner_tag': t.get('owner_tag') or t.get('owner'),
            'status': t.get('status'),
        } for t in completed],
        key=lambda x: str(x.get('id', ''))
    )
    digest_payload = {
        'active': active_meaningful,
        'completed': completed_meaningful,
    }
    digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True).encode()).hexdigest()[:20]

    counts = {}
    for task in active:
        state = task.get('status', 'unknown')
        counts[state] = counts.get(state, 0) + 1
    for task in completed:
        state = task.get('status', 'completed')
        counts[state] = counts.get(state, 0) + 1

    active_list = ActiveTaskList(
        active,
        completed=completed,
        ready=ready,
        running=running,
        recent_completed=completed[:10]
    )

    return TaskEventResult(
        active_list,
        digest,
        counts,
        completed=completed,
        ready=ready,
        running=running,
        recent_completed=completed[:10]
    )


def format_supervision_body(event_key, selected_tasks, entities=None, recent_completions=None, is_delta=False, source_pointer='coordination/TASKS.json'):
    """
    Format supervision envelope body per C1629/C1630/C3003.
    Structures tasks clearly by project/team:
    - Delta mode:
      SUPERVISION-{event_key}: ... Changed actionable tasks (source: {source_pointer}): [project] task (status, owner); ...
    - Full/bounded mode:
      SUPERVISION-{event_key}: ... Tasks: [project] task (status, owner); ...
    """
    header_label = f"Changed actionable tasks (source: {source_pointer}): " if is_delta else "Tasks: "
    prefix = (
        f'SUPERVISION-{event_key}: User requests autonomous useful execution and clear roles. '
        'Read coordination/TEAM-REGISTRY.json, TASKS.json and SUPERVISION.md. '
        'As monitoring principal, inspect your teams, ask heads to claim ready owned work, '
        'verify first actual tool/output, review completion and choose next useful step. '
        'Diagnose blockers or arrange acknowledged repair and continue independent work. '
        'Do not create implementation teams yourself, invent busywork, overwrite drafts or bypass quotas. '
        'Reply with task IDs, accepted owners, first evidence, blocked reasons and next check; update TASKS.json with ownership. '
        + header_label
    )

    if entities is None:
        entities = []
    # If caller passed completed tasks list as 3rd positional argument (legacy / convenience):
    if isinstance(entities, list) and entities and 'status' in entities[0] and 'id' in entities[0] and not any('principal_tags' in x or 'kind' in x for x in entities):
        recent_completions = entities
        entities = []

    grouped = {}
    for t in selected_tasks:
        matched_eid = None
        for e in entities:
            if task_matches_entity(t, e):
                matched_eid = e['id']
                break
        if not matched_eid:
            matched_eid = normalize_project_id(t.get('project_id')) or normalize_project_id(t.get('team_id')) or t.get('project_id') or t.get('team_id') or 'unassigned'
        grouped.setdefault(matched_eid, []).append(t)

    group_strs = []
    for eid, grp in grouped.items():
        task_strs = [f"{t['id']} ({t.get('status', 'unknown')}, {t.get('owner_tag') or t.get('owner') or 'unowned'})" for t in grp]
        group_strs.append(f"[{eid}] " + ", ".join(task_strs))

    tasks_part = "; ".join(group_strs)

    completions_part = ""
    if recent_completions:
        comp_strs = [f"{t['id']} ({t.get('status', 'done')})" for t in recent_completions]
        completions_part = "; Recent completions: " + ", ".join(comp_strs)

    return prefix + tasks_part + completions_part


def idle_episode(active, ready, old, timestamp, threshold=180):
    """
    Check if an entity is in an unexplained idle episode beyond SLO (default 180s = 3 minutes).
    An episode is overdue if:
    - There is active ready work (active contains ready tasks or active items),
    - The entity has been observed continuously idle (since is not None),
    - Elapsed idle duration (timestamp - since) >= threshold (3 minutes),
    - The entity does NOT have an unacknowledged pending message.
    """
    since = (old.get('idle_since') if old.get('idle_since') is not None else timestamp) if ready else None
    has_ready = any(t.get('status', 'ready') in ('ready', 'queued') for t in active) if isinstance(active, (list, tuple)) else bool(active)
    overdue = bool(has_ready and since is not None and (timestamp - since >= threshold) and not old.get('pending'))
    return since, overdue


def eligible(state, screen, tag, previous, quota=True):
    if not state.get('alive'):
        return 0, 'missing-process'
    kind = composer(screen, tag)
    if state.get('reported_state') not in ('idle', 'waiting'):
        return 0, 'not-reported-ready'
    if kind != 'empty':
        return 0, kind
    if tag == 'codex-principal' and not quota:
        return 0, 'quota-denied-or-unknown'
    same = previous.get('session_id') == state.get('session_id')
    return (previous.get('ready_snapshot_count', 0) + 1 if same else 1), 'idle-empty'


AUTHORIZED_HOOK_ENGINES = {
    'zcodex', 'codex', 'claude', 'opencode', 'grok', 'gemini', 'antigravity', 'shell'
}


def check_pending_slo(pending, tag, item, now_ts=None):
    """
    Check if a pending request is beyond its retry SLO.
    Returns (is_beyond_slo, pending_age_seconds, slo_seconds, blocking_reason).
    Preserves pending tracking and refuses fake ACKs on timeout.
    Reports observed blocking reason without claiming new authority.
    Validates finite positive override and handles timezone-aware timestamps safely.
    """
    import math
    if not pending or not pending.get('created_at'):
        return False, 0.0, 0, None
    try:
        created_dt = datetime.datetime.fromisoformat(pending['created_at'])
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=datetime.timezone.utc)
        created_ts = created_dt.timestamp()
    except Exception:
        return False, 0.0, 0, None

    if now_ts is not None:
        current_ts = float(now_ts)
    else:
        current_ts = time.time()

    pending_age = max(0.0, current_ts - created_ts)
    slo_seconds = 1800 if tag == 'claude-principal' else 300
    env_slo = os.environ.get('SUPERVISION_RETRY_SLO_SECONDS')
    if env_slo:
        try:
            val = float(env_slo)
            if math.isfinite(val) and val > 0:
                slo_seconds = val
        except (ValueError, TypeError):
            pass

    if pending_age < slo_seconds:
        return False, pending_age, slo_seconds, None

    # Determine exact observed blocking reason without claiming new authority
    if not item.get('alive', True):
        blocking_reason = f"recipient process is missing or dead ({item.get('reason', 'missing-process')})"
    elif item.get('composer') in ('draft', 'menu-or-draft'):
        blocking_reason = f"recipient composer has an unsubmitted draft or menu ({item.get('composer')})"
    elif item.get('composer') == 'busy' or item.get('reported_state') == 'working':
        blocking_reason = f"recipient is actively busy (reported: {item.get('reported_state')}, composer: {item.get('composer')})"
    elif item.get('reason') == 'quota-denied-or-unknown':
        blocking_reason = "codex quota denied or unknown (<=15% remaining)"
    elif item.get('pending_reason'):
        blocking_reason = item['pending_reason']
    elif pending.get('delivery') == 'not-ready':
        blocking_reason = f"aplexer deliver refused: recipient not-ready ({item.get('reason', 'not-ready')})"
    elif pending.get('delivery') in ('send-uncertain', 'delivery-uncertain'):
        blocking_reason = f"delivery uncertain ({pending.get('delivery')})"
    else:
        blocking_reason = f"recipient not ready: {item.get('reason', 'unknown')} (composer: {item.get('composer', 'unknown')}, ready_snapshots: {item.get('ready_snapshot_count', 0)})"

    return True, pending_age, slo_seconds, blocking_reason


def parse_and_validate_turn_hook_event(raw_event, expected_session_id=None):
    """
    Parse and validate an authoritative turn-boundary hook event emitted by an engine.
    Syntax & schema validation only. Requires authenticated transport channel
    (e.g. 0700 UNIX domain socket owned by the session workload UID/GID).
    """
    if isinstance(raw_event, str):
        try:
            data = json.loads(raw_event)
        except Exception as e:
            raise ValueError(f"malformed JSON in hook event: {e}") from e
    elif isinstance(raw_event, dict):
        data = raw_event
    else:
        raise ValueError("hook event must be a JSON string or dict")

    event = data.get('hook_event', data)
    if not isinstance(event, dict):
        raise ValueError("hook_event payload must be a JSON object")

    event_type = event.get('type')
    if event_type not in ('turn_complete', 'turn_start'):
        raise ValueError(f"unsupported hook event type: {event_type!r}; expected 'turn_complete' or 'turn_start'")

    state = event.get('state')
    if event_type == 'turn_complete':
        if state not in ('idle-empty', 'idle'):
            raise ValueError(f"turn_complete event requires state 'idle-empty' or 'idle', got {state!r}")
    elif event_type == 'turn_start':
        if state not in ('working', 'busy'):
            raise ValueError(f"turn_start event requires state 'working' or 'busy', got {state!r}")

    prompt_seq = event.get('prompt_seq')
    if prompt_seq is None or not isinstance(prompt_seq, int) or prompt_seq < 0:
        raise ValueError(f"prompt_seq must be a non-negative integer, got {prompt_seq!r}")

    session_id = event.get('session_id')
    if not session_id or not isinstance(session_id, str):
        raise ValueError("missing or invalid session_id in hook event")
    try:
        parsed_uuid = str(uuid.UUID(session_id))
    except Exception as e:
        raise ValueError(f"session_id is not a valid UUID: {session_id!r}") from e

    if expected_session_id:
        try:
            expected_uuid = str(uuid.UUID(expected_session_id))
            if parsed_uuid != expected_uuid:
                raise ValueError(f"session_id mismatch: expected {expected_uuid}, got {parsed_uuid}")
        except ValueError:
            if session_id != expected_session_id:
                raise ValueError(f"session_id mismatch: expected {expected_session_id}, got {session_id}")

    engine = event.get('engine')
    if not engine or not isinstance(engine, str) or engine not in AUTHORIZED_HOOK_ENGINES:
        raise ValueError(f"engine {engine!r} not in authorized hook engines ({sorted(AUTHORIZED_HOOK_ENGINES)})")

    timestamp_ms = event.get('timestamp_ms')
    if timestamp_ms is None or not isinstance(timestamp_ms, (int, float)) or timestamp_ms <= 0:
        raise ValueError(f"timestamp_ms must be a positive number, got {timestamp_ms!r}")

    active_children = event.get('active_children', 0)
    if event_type == 'turn_complete' and isinstance(active_children, int) and active_children > 0:
        raise ValueError(f"turn_complete rejected: workload has {active_children} active child processes")

    composer_state = event.get('composer_state')
    if event_type == 'turn_complete' and composer_state in ('draft', 'menu-or-draft', 'busy'):
        raise ValueError(f"turn_complete rejected: composer state is {composer_state!r}, expected empty")

    return {
        'type': event_type,
        'state': state,
        'prompt_seq': prompt_seq,
        'session_id': parsed_uuid,
        'engine': engine,
        'timestamp_ms': int(timestamp_ms),
        'turn_id': event.get('turn_id'),
        'workload_pid': event.get('workload_pid'),
        'active_children': active_children,
        'composer_state': composer_state or ('empty' if event_type == 'turn_complete' else 'busy'),
        'syntax_valid': True,
        'authenticated_channel_required': True
    }


def records(path, name):
    value = json.loads(path.read_text())
    return value if isinstance(value, list) else value[name]


def recorded_send(binary, tag, key, body, spool, sender_id, supports_key, call=command):
    """Without native keys, a prewritten intent freezes ambiguous crashes rather than resending."""
    receiptpath = spool / f'receipt-{key}.json'
    intentpath = spool / f'intent-{key}.json'
    if receiptpath.exists():
        return json.loads(receiptpath.read_text())
    archived = read_archived(spool, receiptpath.name)
    if archived is not None:
        return archived
    if intentpath.exists():
        return {'delivery':'send-uncertain', 'id':None, 'sender_id':sender_id, 'reason':'existing send intent without durable receipt; manual reconciliation required'}
    atomic(intentpath, {'sender_id':sender_id, 'to':tag, 'event_key':key, 'created_at':now(), 'state':'send-may-have-started'})
    args = [binary, 'message', 'send', '--to', tag, '--json']
    if supports_key:
        args += ['--idempotency-key', key]
    try:
        receipt = json.loads(call(args + [body]))
    except MutationUncertain:
        # Intent file already freezes this key: outcome UNKNOWN, no retry, no new id.
        raise
    except Exception:
        return {'delivery':'send-uncertain', 'id':None, 'sender_id':sender_id, 'reason':'send failed or response lost; no automatic retry'}
    atomic(receiptpath, receipt)
    return receipt


def may_deliver(pending, own_id, spool=None, authorized_senders=None):
    if not (pending and pending.get('id') and pending.get('delivery') in ('inbox', 'not-ready')):
        return False
    sender_id = pending.get('sender_id')
    if not sender_id:
        return False
    if sender_id == own_id:
        return True
    if authorized_senders and sender_id in authorized_senders:
        return True

    spool_path = pathlib.Path(spool) if spool is not None else PRIVATE
    # Check against previous identity in PRIVATE / 'identity.json'
    ident_path = spool_path / 'identity.json'
    if ident_path.exists():
        try:
            ident_data = json.loads(ident_path.read_text())
            if ident_data.get('tag') == 'experiment-supervision':
                if ident_data.get('id') == sender_id:
                    return True
                if sender_id in ident_data.get('previous_ids', []):
                    return True
        except Exception:
            pass

    # Allow sender tag 'experiment-supervision' in this workspace
    if pending.get('sender_tag') == 'experiment-supervision':
        ws = pending.get('workspace')
        if not ws or ws == str(ROOT) or ws == str(spool_path.parent.parent):
            return True

    if pending.get('event'):
        for rpath in spool_path.glob(f"receipt-{pending['event']}*.json"):
            try:
                rdata = json.loads(rpath.read_text())
                rfrom = rdata.get('from', {})
                if rfrom.get('tag') == 'experiment-supervision':
                    rf_ws = rfrom.get('workspace')
                    if not rf_ws or rf_ws == str(ROOT) or rf_ws == str(spool_path.parent.parent):
                        return True
            except Exception:
                pass

    return False


def task_ready_fingerprint(t):
    return {
        'id': t.get('id'),
        'status': t.get('status'),
        'owner_tag': t.get('owner_tag') or t.get('owner'),
        'updated_at': t.get('updated_at'),
        'blocked_on': sorted(t.get('blocked_on', [])) if isinstance(t.get('blocked_on'), list) else t.get('blocked_on'),
        'next_action': t.get('next_action'),
        'evidence_paths': sorted(t.get('evidence_paths', [])) if isinstance(t.get('evidence_paths'), list) else t.get('evidence_paths'),
        'failure_count': t.get('failure_count'),
        'error': t.get('error'),
        'blocking_reason': t.get('blocking_reason'),
        'acceptance_status': t.get('acceptance_status'),
    }


def check_resting_state_contradicted(session: dict, idle_grace_ms: int = 1000) -> bool:
    """
    Check if recipient session's resting state is contradicted by subsequent PTY activity.
    Matches Rust native message_deferred check:
    last_activity_ms > reported_state_at_ms + IDLE_GRACE_MS
    """
    if not isinstance(session, dict):
        return False
    last_activity = session.get('last_activity_ms')
    reported_state_at = session.get('reported_state_at_ms')
    if last_activity is None or reported_state_at is None:
        return False
    try:
        return int(last_activity) > int(reported_state_at) + int(idle_grace_ms)
    except (ValueError, TypeError):
        return False


def run():
    os.chdir(ROOT)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    lease = (PRIVATE / 'service.lock').open('w')
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    identity = json.loads(command(['aplexer', 'whoami', '--json']))
    if identity.get('workspace') != str(ROOT) or identity.get('tag') != 'experiment-supervision':
        raise RuntimeError('real experiment-supervision binding required')
    expected_hash = hashlib.sha256(pathlib.Path(BINARY).read_bytes()).hexdigest()
    supports_key = '--idempotency-key' in command([BINARY, 'message', 'send', '--help'])
    prev_id_file = PRIVATE / 'identity.json'
    prev_ids = []
    if prev_id_file.exists():
        try:
            prev_data = json.loads(prev_id_file.read_text())
            if prev_data.get('id') and prev_data.get('id') != identity.get('id'):
                prev_ids.append(prev_data['id'])
            if isinstance(prev_data.get('previous_ids'), list):
                prev_ids.extend([x for x in prev_data['previous_ids'] if x != identity.get('id')])
        except Exception:
            pass
    seen_ids = set()
    prev_ids_dedup = [x for x in prev_ids if not (x in seen_ids or seen_ids.add(x))]
    identity_payload = {k: identity.get(k) for k in ('id', 'tag', 'workspace')}
    if prev_ids_dedup:
        identity_payload['previous_ids'] = prev_ids_dedup
    atomic(PRIVATE / 'identity.json', identity_payload)
    manifest = {'path':BINARY, 'sha256':expected_hash, 'selected_at':now(),
           'authority':'root-approved immutable copy of installed production CLI; no all-engine readiness guarantee',
           'supports_idempotency_key':supports_key, 'send_recovery':'native key when available; otherwise crash-safe local intent, ambiguous sends frozen'}
    atomic(PRIVATE / 'binary-manifest.json', manifest)

    # Source manifest for Python supervision runtime
    service_path = pathlib.Path(__file__).resolve()
    expected_source_hash = hashlib.sha256(service_path.read_bytes()).hexdigest()
    failover_path = service_path.parent / 'failover_integration.py'
    expected_failover_hash = hashlib.sha256(failover_path.read_bytes()).hexdigest() if failover_path.exists() else None
    source_manifest = {
        'service_path': str(service_path),
        'service_sha256': expected_source_hash,
        'failover_path': str(failover_path) if failover_path.exists() else None,
        'failover_sha256': expected_failover_hash,
        'loaded_at': now(),
        'authority': 'canonical supervision runtime source proof'
    }
    atomic(PRIVATE / 'source-manifest.json', source_manifest)
    statepath = PRIVATE / 'state.json'
    memory = json.loads(statepath.read_text()) if statepath.exists() else {}

    def event(kind, **fields):
        if storage_guard(PRIVATE)['state'] == 'paused-hard-limit':
            raise StorageFull('storage hard limit reached; all evidence preserved')
        logfile = PRIVATE / 'events.jsonl'
        if logfile.exists() and logfile.stat().st_size > 4 * 1024 * 1024:
            archive_verified(logfile, PRIVATE)
        legacy = PRIVATE / 'events.previous.jsonl'
        if legacy.exists():
            archive_verified(legacy,PRIVATE)
        with (PRIVATE / 'events.jsonl').open('a') as handle:
            handle.write(json.dumps({'timestamp': now(), 'kind': kind, **fields}) + '\n')

    if storage_guard(PRIVATE)['state'] != 'paused-hard-limit':
        event('service-started', session_id=identity['id'], binary_sha256=expected_hash,
              service_sha256=expected_source_hash, failover_sha256=expected_failover_hash)

    consumer = TerminalConsumer(PRIVATE)

    while not (PRIVATE / 'stop').exists():
        report = {'timestamp': now(), 'identity': identity['id'], 'principals': {}, 'heads': {}, 'errors': [], 'actions': [], 'degraded': False}
        try:
            report['storage'] = storage_guard(PRIVATE)
            if report['storage']['state'] == 'paused-hard-limit':
                raise StorageFull('storage hard limit reached; native messages and ACKs paused; evidence preserved')
            registry_full = json.loads((ROOT / 'coordination/TEAM-REGISTRY.json').read_text())
            entities = extract_supervision_entities(registry_full)
            tasks = records(ROOT / 'coordination/TASKS.json', 'tasks')

            # Ingest receipts and maintained task-unit launcher state
            ql_db_candidates = get_ql_db_candidates(ROOT, PRIVATE)
            ingested_launcher_tasks = 0
            for ql_db in ql_db_candidates:
                if ql_db.exists():
                    ingested_launcher_tasks += len(consumer.ingest_launcher_db(ql_db))

            # Reconcile dependencies and unblock ready tasks
            unblocked = consumer.reconcile_and_unblock_tasks(tasks)
            if unblocked:
                event('tasks-unblocked-by-review', unblocked_tasks=unblocked)

            active, digest, counts = task_event(tasks)
            report['task_counts'] = counts
            report['terminal_consumer_tasks'] = len(consumer.task_states)
            report['ingested_launcher_tasks'] = ingested_launcher_tasks

            # Durable owned READY bridge to launcher enqueue
            known_task_statuses = memory.get('task_statuses', {})
            enqueued_dir = PRIVATE / 'enqueued'
            enqueued_dir.mkdir(parents=True, exist_ok=True)
            new_task_statuses = {}
            for t in tasks:
                tid = t.get('id')
                if not tid:
                    continue
                current_st = t.get('status')
                new_task_statuses[tid] = current_st
                prev_st = known_task_statuses.get(tid)

                if current_st in ('ready', 'queued'):
                    enqueue_record_file = enqueued_dir / f"{tid}.json"
                    if prev_st not in ('ready', 'queued') or not enqueue_record_file.exists():
                        head_owner = get_designated_head_owner(t, entities)
                        if head_owner:
                            rec = bridge_ready_task_to_launcher(t, head_owner, PRIVATE, ql_db_candidates)
                            event('task-ready-enqueued', task_id=tid, head_owner=head_owner,
                                  project_id=t.get('project_id') or t.get('team_id'),
                                  idempotency_key=rec['idempotency_key'],
                                  launcher_submitted=rec.get('launcher_submitted', False))
                            report['actions'].append({
                                'kind': 'task-ready-enqueued',
                                'task_id': tid,
                                'head_owner': head_owner,
                                'launcher_submitted': rec.get('launcher_submitted', False),
                            })
            memory['task_statuses'] = new_task_statuses

            # Continuous launcher queue draining
            drained_actions = drain_launcher_queues(ql_db_candidates, report=report)
            for act in drained_actions:
                event('launcher-queue-drained', db=act.get('db'), status=act.get('status'))

            # Actionable event filtering
            actionable_events, actionable_digest = consumer.compute_actionable_events(tasks)
            report['actionable_events'] = actionable_events
            report['actionable_digest'] = actionable_digest
            active_tags = active_principals(entities, PRIVATE, registry_full)
            report['active_principals'] = active_tags
            head_tags = active_heads(entities, PRIVATE, registry_full)
            report['active_heads'] = head_tags
            sessions = json.loads(command(['aplexer', 'list', '--json']))
            same_source = hashlib.sha256(service_path.read_bytes()).hexdigest() == expected_source_hash
            if not same_source:
                sys.exit(42)
            if failover_path.exists() and expected_failover_hash:
                same_failover = hashlib.sha256(failover_path.read_bytes()).hexdigest() == expected_failover_hash
                if not same_failover:
                    sys.exit(42)
            sessions = [x for x in sessions if x.get('workspace') == str(ROOT)]
            # Process durable scheduled due callbacks
            due_delivered = process_due_callbacks(PRIVATE, BINARY, identity["id"], supports_key, command, recorded_send, sessions)
            for cb_id in due_delivered:
                event("due-callback-delivered", callback_id=cb_id)
            try:
                import importlib
                import scripts.supervision.failover_integration as failover_integration
                importlib.reload(failover_integration)
                failover_integration.run_failover_tick(PRIVATE, BINARY, supports_key, identity["id"], command, recorded_send, registry_full, sessions)
            except Exception as e:
                event("failover-error", error=str(e))
            same_binary = hashlib.sha256(pathlib.Path(BINARY).read_bytes()).hexdigest() == expected_hash
            if not same_binary:
                sys.exit(42)
            # Replies are inspected before ACK; arbitrary reply text is never executable.
            inbox = json.loads(command([BINARY, 'message', 'inbox', '--json']))
            atomic(PRIVATE / 'inbox.json', inbox)
            messages = inbox if isinstance(inbox, list) else inbox.get('messages', [])
            for message in messages:
                mid = message.get('id')
                if not mid:
                    continue
                sender = message.get('from', {})
                reply_to = message.get('reply_to', message.get('in_reply_to'))
                body = message.get('body', '')
                tags = [tag for tag in ALL_KNOWN_PRINCIPALS if sender.get('tag') == tag]
                for tag in tags:
                    pending = memory.get(tag, {}).get('pending')
                    correlated = bool(pending and (reply_to == pending.get('id') or f"SUPERVISION-{pending.get('event')}" in body))
                    if correlated:
                        memory[tag]['last_request'] = {**pending, 'reply_id':mid, 'acknowledged_at':now()}
                        memory[tag]['pending'] = None
                atomic(PRIVATE / f'reply-{mid}.json', message)
                event('reply-received', message_id=mid, sender_id=sender.get('session_id'), sender_tag=sender.get('tag'), reply_to=reply_to,
                      classification='coordination-reply; inspect evidence before agreement', body_sha256=hashlib.sha256(body.encode()).hexdigest())
                command([BINARY, 'message', 'ack', mid, '--json'])

            for tag in active_tags:
                match = [x for x in sessions if x.get('tag') == tag]
                old = memory.get(tag, {})
                if len(match) != 1:
                    # Preserve all existing durable fields from old state (sent_event, cooldown_until, last_request, pending, etc.)
                    item = dict(old)
                    item['event_key'] = digest
                    item['ready_snapshot_count'] = 0
                    item['reason'] = 'missing-or-ambiguous-principal'
                    item['alive'] = False
                    pending = old.get('pending')
                    if pending:
                        is_beyond, dur, slo_limit, block_reason = check_pending_slo(
                            pending, tag, item, time.time()
                        )
                        if is_beyond:
                            item['status'] = 'blocked_beyond_slo'
                            item['blocking_reason'] = block_reason
                            item['pending_duration_seconds'] = round(dur, 2)
                            item['retry_slo_seconds'] = slo_limit
                            report['degraded'] = True
                            report['errors'].append(f"principal {tag} pending message {pending['id']} blocked_beyond_slo ({round(dur, 1)}s >= {slo_limit}s): {block_reason}")
                            event('pending-blocked-beyond-slo', principal=tag, message_id=pending['id'],
                                  duration_seconds=round(dur, 2), slo_seconds=slo_limit, blocking_reason=block_reason)
                        else:
                            item['status'] = 'pending'
                        item['pending'] = pending
                        if not item.get('alive', True) or dur > 2 * slo_limit:
                            item['failover_candidate'] = True
                            failover_reason = f"leader {tag} role vacancy: {'un-alive (confirmed dead)' if not item.get('alive', True) else f'unACKed beyond 2x SLO ({round(dur, 1)}s > {2 * slo_limit}s)'}; candidate 43ea trigger condition met"
                            event('failover-candidate-action',
                                  role='principal',
                                  role_vacancy=True,
                                  entity=tag,
                                  principal=tag,
                                  message_id=pending['id'],
                                  duration_seconds=round(dur, 2),
                                  slo_seconds=slo_limit,
                                  alive=item.get('alive', True),
                                  trigger_condition='un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
                                  candidate_pin='43ea3400965e690206f823640173992a9ea0c7b4',
                                  candidate='43ea',
                                  reason=failover_reason)
                            report['actions'].append({
                                'kind': 'failover-candidate-action',
                                'role': 'principal',
                                'role_vacancy': True,
                                'entity': tag,
                                'recipient': tag,
                                'principal': tag,
                                'message_id': pending['id'],
                                'duration_seconds': round(dur, 2),
                                'slo_seconds': slo_limit,
                                'alive': item.get('alive', True),
                                'trigger_condition': 'un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
                                'candidate_pin': '43ea3400965e690206f823640173992a9ea0c7b4',
                                'candidate': '43ea',
                                'reason': failover_reason
                            })
                    else:
                        item['status'] = 'missing'
                        item.pop('failover_candidate', None)
                    memory[tag] = item
                    report['principals'][tag] = item
                    continue

                item = {'event_key': digest, 'ready_snapshot_count': 0}
                if old.get('diagnostic_hold'):
                    item['diagnostic_hold'] = old['diagnostic_hold']
                if old.get('failover_candidate'):
                    item['failover_candidate'] = old['failover_candidate']
                session = match[0]
                pid = session.get('workload_pid')
                item.update(session_id=session['id'], reported_state=session.get('reported_state'),
                            alive=bool(pid and pathlib.Path(f'/proc/{pid}').exists()))
                screen = command(['aplexer', 'capture', session['id'], '--screen', '--plain'])
                quota = True
                if tag == 'codex-principal' and item['reported_state'] in ('idle', 'waiting'):
                    quota = quota_allowed(json.loads(command(['quse', 'codex', '--json'], timeout=30)))
                count, reason = eligible(item, screen, tag, old, quota)
                item.update(composer=composer(screen, tag), ready_snapshot_count=count, reason=reason)
                principal_entities = [e for e in entities if tag in e.get('principal_tags', []) and not (e.get('conflict') and e['conflict'].get('detected'))]
                principal_tasks = [t for t in active if is_task_eligible_for_supervision(t, sessions=sessions, active_heads=head_tags, active_principals=active_tags) and any(task_matches_entity(t, e) for e in principal_entities)]
                idle_since, overdue = idle_episode(principal_tasks or active, count > 0, old, time.time(), threshold=180)
                item['idle_since'] = idle_since
                item['unexplained_idle_over_slo'] = overdue
                if overdue:
                    report['degraded'] = True
                    report['errors'].append(f"principal {tag} unexplained idle-with-READY over SLO ({round(time.time() - idle_since, 1)}s >= 180s)")
                    event('principal-unexplained-idle-over-slo', principal=tag, session_id=session['id'],
                          idle_since=idle_since, duration_seconds=round(time.time() - idle_since, 2))
                episode = int(time.time() // (1800 if tag == 'claude-principal' else 180)) if overdue else old.get('episode', 0)
                event_key = hashlib.sha256(f'{digest}:{session["id"]}:{episode}'.encode()).hexdigest()[:20]
                item.update(event_key=event_key, episode=episode)
                pending = old.get('pending')
                if pending and pending.get('diagnostic_hold'):
                    item['diagnostic_hold'] = pending['diagnostic_hold']
                if old.get('last_request'):
                    item['last_request'] = old['last_request']
                if pending:
                    evidence = exact_ack(pending, session['id'], tag, ROOT)
                    if evidence:
                        item['last_request'] = {**pending, 'acknowledged_at':now(), 'ack_evidence':evidence}
                        atomic(PRIVATE / ('native-ack-' + pending['id'] + '.json'), evidence)
                        event('pending-reconciled-native-ack', principal=tag, **evidence)
                        report['actions'].append({'kind':'pending-reconciled-native-ack', 'principal':tag, 'message_id':pending['id']})
                        pending = None
                    else:
                        target_recipient_id = pending.get('recipient_session_id') or old.get('session_id')
                        if not target_recipient_id:
                            receipt_file = PRIVATE / f"receipt-{pending.get('event')}-{tag}.json"
                            if receipt_file.exists():
                                try:
                                    rdata = json.loads(receipt_file.read_text())
                                    target_recipient_id = rdata.get('to', {}).get('session_id')
                                except Exception:
                                    pass
                        if target_recipient_id and target_recipient_id != session['id']:
                            event('pending-superseded-session-change', principal=tag, message_id=pending['id'],
                                  old_session_id=target_recipient_id, new_session_id=session['id'],
                                  reason='recipient session changed; previous message addressed to old session superseded')
                            report['actions'].append({
                                'kind': 'pending-superseded-session-change',
                                'principal': tag,
                                'message_id': pending['id'],
                                'old_session_id': target_recipient_id,
                                'new_session_id': session['id']
                            })
                            item['last_request'] = {**pending, 'superseded_at': now(), 'superseded_reason': 'recipient-session-change'}
                            pending = None

                # Determine authoritative and conflicting entities for this principal on every cycle (C1647)
                principal_entities = [e for e in entities if tag in e.get('principal_tags', []) and not (e.get('conflict') and e['conflict'].get('detected'))]
                conflicting_entities = [e for e in entities if tag in e.get('principal_tags', []) and e.get('conflict') and e['conflict'].get('detected')]
                if conflicting_entities:
                    report['conflicting_entities'] = [c['id'] for c in conflicting_entities]
                    report['degraded'] = True
                    report['errors'].append(f"principal {tag} has conflicting entity registrations: {', '.join(c['id'] for c in conflicting_entities)}")

                # At most one envelope per task revision, sparse Claude min 30m; no hourly busywork.
                cooldown = old.get('cooldown_until', 0)
                if active and not pending and (old.get('sent_event') != event_key) and time.time() >= cooldown:
                    if item.get('alive'):
                        selected = []
                        seen_selected = set()
                        for t in active:
                            tid = t.get('id')
                            if tid not in seen_selected:
                                if is_task_eligible_for_supervision(t, sessions=sessions, active_heads=head_tags, active_principals=active_tags):
                                    if any(task_matches_entity(t, e) for e in principal_entities):
                                        selected.append(t)
                                        seen_selected.add(tid)

                        if selected:
                            all_completed = getattr(active, 'completed', None)
                            if all_completed is None:
                                all_completed = [t for t in tasks if t.get('status') in ('completed', 'done')]
                            completed_for_principal = [t for t in all_completed if any(task_matches_entity(t, e) for e in principal_entities)]
                            completed_for_principal.sort(key=lambda t: t.get('completed_at') or t.get('updated_at') or '', reverse=True)
                            recent_completions = completed_for_principal[:5] if completed_for_principal else None

                            # Delta-payload computation (C3003)
                            last_task_fps = old.get('last_notified_task_fps')
                            session_changed = bool(old.get('session_id') and old.get('session_id') != session['id'])
                            current_fps = {t['id']: task_ready_fingerprint(t) for t in selected}

                            if last_task_fps is not None and not session_changed:
                                changed_tasks = [t for t in selected if current_fps.get(t['id']) != last_task_fps.get(t['id'])]
                                if changed_tasks:
                                    payload_tasks = changed_tasks[:10]
                                    is_delta = True
                                else:
                                    payload_tasks = selected[:5]
                                    is_delta = False
                            else:
                                prioritized = sorted(
                                    selected,
                                    key=lambda t: 0 if t.get('status') in ('ready', 'queued') else (
                                        1 if t.get('status') in ('running', 'in_progress', 'working') else (
                                            2 if t.get('status') == 'blocked' else 3
                                        )
                                    )
                                )
                                payload_tasks = prioritized[:10]
                                is_delta = False

                            body = format_supervision_body(
                                event_key=event_key,
                                selected_tasks=payload_tasks,
                                entities=principal_entities,
                                recent_completions=recent_completions,
                                is_delta=is_delta,
                                source_pointer='coordination/TASKS.json'
                            )
                            # Inbox first, then existing-ID delivery after independent fresh snapshots.
                            receipt = recorded_send(BINARY, tag, f'{event_key}-{tag}', body, PRIVATE, identity['id'], supports_key)
                            atomic(PRIVATE / f'receipt-{event_key}-{tag}.json', receipt)
                            if receipt.get('delivery') == 'send-uncertain':
                                # Frozen ambiguity: retain UNKNOWN outcome in the report, degraded cycle.
                                report['degraded'] = True
                                report['uncertain_outcome'] = {'outcome': 'UNKNOWN', 'class': 'send-uncertain', 'principal': tag, 'event_key': event_key, 'reason': receipt.get('reason')}
                            envelope = receipt.get('message', receipt)
                            pending = {'id': envelope.get('id', receipt.get('id')), 'sender_id':identity['id'],
                                       'sender_tag': identity.get('tag', 'experiment-supervision'),
                                       'recipient_session_id': session['id'], 'recipient_tag': tag,
                                       'workspace': identity.get('workspace', str(ROOT)), 'event': event_key,
                                       'delivery':receipt.get('delivery','inbox'), 'created_at': now()}
                            item['sent_event'] = event_key
                            item['last_notified_task_fps'] = current_fps
                            item['cooldown_until'] = cooldown
                            event('request-recorded', principal=tag, message_id=pending['id'], event_key=event_key)
                else:
                    item['sent_event'] = old.get('sent_event')
                    item['last_notified_task_fps'] = old.get('last_notified_task_fps')
                    item['cooldown_until'] = cooldown

                if pending and not may_deliver(pending, identity['id'], spool=PRIVATE):
                    item['pending_reason'] = 'original sender changed; original recipient ACK/reply required'
                elif item.get('pending_reason') == 'original sender changed; original recipient ACK/reply required':
                    item.pop('pending_reason', None)
                if may_deliver(pending, identity['id'], spool=PRIVATE) and count >= 2 and time.time() >= item.get('cooldown_until', 0) and not item.get('failover_candidate'):
                    if check_resting_state_contradicted(session):
                        item['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
                        pending['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
                        item['cooldown_until'] = time.time() + 180
                        event('delivery-precheck-held', principal=tag, message_id=pending['id'], reason='resting-state-contradicted-by-pty', last_activity_ms=session.get('last_activity_ms'), reported_state_at_ms=session.get('reported_state_at_ms'))
                    else:
                        if item.get('diagnostic_hold') == 'resting-state-contradicted-by-pty':
                            item.pop('diagnostic_hold', None)
                            pending.pop('diagnostic_hold', None)
                        # Third immediate check closes most polling races; native command still enforces readiness.
                        fresh_screen = command(['aplexer', 'capture', session['id'], '--screen', '--plain'])
                        if composer(fresh_screen, tag) == 'empty':
                            deliver_args = [BINARY, 'message', 'deliver', pending['id'], '--workspace', str(ROOT), '--json']
                            result = subprocess.run(deliver_args, capture_output=True, text=True, timeout=20)
                            deliver_stderr = (result.stderr or '').strip()
                            if result.returncode and MAILBOX_BUSY.search(deliver_stderr):
                                # Exactly one invocation; pending stays unreconciled with outcome UNKNOWN.
                                raise DeliveryUncertain(deliver_args, deliver_stderr, result.returncode)
                            try:
                                outcome = json.loads(result.stdout)
                            except json.JSONDecodeError:
                                outcome = {'status': 'delivery-uncertain', 'returncode': result.returncode}
                            # Fail-closed safety: no fallback to binaries lacking composer draft detection.
                            # Refusal from reviewed binary is preserved verbatim in delivery audit evidence.
                            atomic(PRIVATE / f"delivery-{pending['id']}.json", outcome)
                            status = outcome.get('status', outcome.get('delivery', 'delivery-uncertain'))
                            pending['delivery'] = status
                            event('delivery-attempt', principal=tag, message_id=pending['id'], outcome=status)
                            if status == 'not-ready':
                                detail = outcome.get('detail', '')
                                if 'contradicted resting state' in detail or 'subsequent PTY activity' in detail:
                                    item['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
                                    pending['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
                                    item['cooldown_until'] = time.time() + 180
                                elif (('Context' in detail or 'GPT-' in detail) and '·' in detail) or re.search(
                                    r'Aplexer awareness|Before editing files|Declare your work|Check peer mail|participate in \d+ workspace|Workspace coordination|worktree|peers|shared paths|peer-provided data',
                                    detail
                                ):
                                    item['diagnostic_hold'] = 'known-footer-classifier-mismatch'
                                    pending['diagnostic_hold'] = 'known-footer-classifier-mismatch'
                                if item.get('diagnostic_hold') == 'known-footer-classifier-mismatch':
                                    item['cooldown_until'] = time.time() + 180
                            if status == 'recipient-acked':
                                item['last_request'] = pending
                                item.pop('diagnostic_hold', None)
                                item.pop('failover_candidate', None)
                                item['cooldown_until'] = time.time() + (1800 if tag == 'claude-principal' else 180)
                                pending = None
                            # Submitted stays pending until genuine reply/read ACK, not repeated on timer.
                            # Unknown/uncertain outcomes prohibit automatic retry.

                if pending:
                    is_beyond, dur, slo_limit, block_reason = check_pending_slo(pending, tag, item, time.time())
                    if is_beyond:
                        if pending.get('sender_id') != identity['id']:
                            event('pending-superseded-session-change', principal=tag, message_id=pending['id'],
                                  old_sender_id=pending.get('sender_id'), new_sender_id=identity['id'],
                                  session_id=session['id'], duration_seconds=round(dur, 2), slo_seconds=slo_limit,
                                  reason='prior supervisor pending message stale beyond SLO; superseded')
                            report['actions'].append({
                                'kind': 'pending-superseded-session-change',
                                'principal': tag,
                                'message_id': pending['id'],
                                'old_sender_id': pending.get('sender_id'),
                                'new_sender_id': identity['id'],
                                'session_id': session['id']
                            })
                            item['last_request'] = {**pending, 'superseded_at': now(), 'superseded_reason': 'stale-beyond-slo-sender-change'}
                            item.pop('diagnostic_hold', None)
                            item.pop('failover_candidate', None)
                            pending = None
                            item['status'] = 'ok'
                        else:
                            item['status'] = 'blocked_beyond_slo'
                            if item.get('diagnostic_hold'):
                                item['blocking_reason'] = f"{block_reason} [diagnostic_hold: {item['diagnostic_hold']}]"
                            else:
                                item['blocking_reason'] = block_reason
                            item['pending_duration_seconds'] = round(dur, 2)
                            item['retry_slo_seconds'] = slo_limit
                            item['cooldown_until'] = max(item.get('cooldown_until', 0), time.time() + 300 if time.time() >= cooldown else cooldown)
                            report['degraded'] = True
                            report['errors'].append(f"principal {tag} pending message {pending['id']} blocked_beyond_slo ({round(dur, 1)}s >= {slo_limit}s): {item['blocking_reason']}")
                            event('pending-blocked-beyond-slo', principal=tag, message_id=pending['id'],
                                  duration_seconds=round(dur, 2), slo_seconds=slo_limit, blocking_reason=item['blocking_reason'])
                            report['actions'].append({
                                'kind': 'pending-blocked-beyond-slo-escalation',
                                'recipient': tag,
                                'message_id': pending['id'],
                                'duration_seconds': round(dur, 2),
                                'blocking_reason': item['blocking_reason'],
                                'diagnostic_hold': item.get('diagnostic_hold'),
                                'recovery_owner': 'ant-head-never-timer-custody-20261006'
                            })
                            if not item.get('alive', True) or dur > 2 * slo_limit:
                                item['failover_candidate'] = True
                                failover_reason = f"leader {tag} role vacancy: {'un-alive (confirmed dead)' if not item.get('alive', True) else f'unACKed beyond 2x SLO ({round(dur, 1)}s > {2 * slo_limit}s)'}; candidate 43ea trigger condition met"
                                event('failover-candidate-action',
                                      role='principal',
                                      role_vacancy=True,
                                      entity=tag,
                                      principal=tag,
                                      message_id=pending['id'],
                                      duration_seconds=round(dur, 2),
                                      slo_seconds=slo_limit,
                                      alive=item.get('alive', True),
                                      trigger_condition='un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
                                      candidate_pin='43ea3400965e690206f823640173992a9ea0c7b4',
                                      candidate='43ea',
                                      reason=failover_reason)
                                report['actions'].append({
                                    'kind': 'failover-candidate-action',
                                    'role': 'principal',
                                    'role_vacancy': True,
                                    'entity': tag,
                                    'recipient': tag,
                                    'principal': tag,
                                    'message_id': pending['id'],
                                    'duration_seconds': round(dur, 2),
                                    'slo_seconds': slo_limit,
                                    'alive': item.get('alive', True),
                                    'trigger_condition': 'un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
                                    'candidate_pin': '43ea3400965e690206f823640173992a9ea0c7b4',
                                    'candidate': '43ea',
                                    'reason': failover_reason
                                })
                    else:
                        item['status'] = 'pending'
                        if not item.get('alive', True):
                            item['failover_candidate'] = True
                            failover_reason = f"leader {tag} role vacancy: un-alive (confirmed dead); candidate 43ea trigger condition met"
                            event('failover-candidate-action',
                                  role='principal',
                                  role_vacancy=True,
                                  entity=tag,
                                  principal=tag,
                                  message_id=pending['id'],
                                  duration_seconds=round(dur, 2),
                                  slo_seconds=slo_limit,
                                  alive=item.get('alive', True),
                                  trigger_condition='un-alive',
                                  candidate_pin='43ea3400965e690206f823640173992a9ea0c7b4',
                                  candidate='43ea',
                                  reason=failover_reason)
                            report['actions'].append({
                                'kind': 'failover-candidate-action',
                                'role': 'principal',
                                'role_vacancy': True,
                                'entity': tag,
                                'recipient': tag,
                                'principal': tag,
                                'message_id': pending['id'],
                                'duration_seconds': round(dur, 2),
                                'slo_seconds': slo_limit,
                                'alive': item.get('alive', True),
                                'trigger_condition': 'un-alive',
                                'candidate_pin': '43ea3400965e690206f823640173992a9ea0c7b4',
                                'candidate': '43ea',
                                'reason': failover_reason
                            })
                else:
                    item['status'] = 'ok'
                    item.pop('failover_candidate', None)
                item['pending'] = pending
                report['principals'][tag] = item
                memory[tag] = item

            for head_tag in head_tags:
                match = [x for x in sessions if x.get('tag') == head_tag]
                old = memory.get(head_tag, {})
                if len(match) != 1:
                    item = dict(old)
                    item['event_key'] = digest
                    item['ready_snapshot_count'] = 0
                    item['reason'] = 'missing-or-ambiguous-head'
                    item['alive'] = False
                    pending = old.get('pending')
                    if pending:
                        is_beyond, dur, slo_limit, block_reason = check_pending_slo(
                            pending, head_tag, item, time.time()
                        )
                        if is_beyond:
                            item['status'] = 'blocked_beyond_slo'
                            item['blocking_reason'] = block_reason
                            item['pending_duration_seconds'] = round(dur, 2)
                            item['retry_slo_seconds'] = slo_limit
                            report['degraded'] = True
                            report['errors'].append(f"head {head_tag} pending message {pending['id']} blocked_beyond_slo ({round(dur, 1)}s >= {slo_limit}s): {block_reason}")
                            event('pending-blocked-beyond-slo', head=head_tag, message_id=pending['id'],
                                  duration_seconds=round(dur, 2), slo_seconds=slo_limit, blocking_reason=block_reason)
                        else:
                            item['status'] = 'pending'
                        item['pending'] = pending
                        if not item.get('alive', True) or dur > 2 * slo_limit:
                            item['failover_candidate'] = True
                            failover_reason = f"leader {head_tag} role vacancy: {'un-alive (confirmed dead)' if not item.get('alive', True) else f'unACKed beyond 2x SLO ({round(dur, 1)}s > {2 * slo_limit}s)'}; candidate 43ea trigger condition met"
                            event('failover-candidate-action',
                                  role='head',
                                  role_vacancy=True,
                                  entity=head_tag,
                                  head=head_tag,
                                  message_id=pending['id'],
                                  duration_seconds=round(dur, 2),
                                  slo_seconds=slo_limit,
                                  alive=item.get('alive', True),
                                  trigger_condition='un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
                                  candidate_pin='43ea3400965e690206f823640173992a9ea0c7b4',
                                  candidate='43ea',
                                  reason=failover_reason)
                            report['actions'].append({
                                'kind': 'failover-candidate-action',
                                'role': 'head',
                                'role_vacancy': True,
                                'entity': head_tag,
                                'recipient': head_tag,
                                'head': head_tag,
                                'message_id': pending['id'],
                                'duration_seconds': round(dur, 2),
                                'slo_seconds': slo_limit,
                                'alive': item.get('alive', True),
                                'trigger_condition': 'un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
                                'candidate_pin': '43ea3400965e690206f823640173992a9ea0c7b4',
                                'candidate': '43ea',
                                'reason': failover_reason
                            })
                    else:
                        item['status'] = 'missing'
                        item.pop('failover_candidate', None)
                    memory[head_tag] = item
                    report['heads'][head_tag] = item
                    continue

                item = {'event_key': digest, 'ready_snapshot_count': 0}
                if old.get('diagnostic_hold'):
                    item['diagnostic_hold'] = old['diagnostic_hold']
                if old.get('failover_candidate'):
                    item['failover_candidate'] = old['failover_candidate']
                session = match[0]
                pid = session.get('workload_pid')
                item.update(session_id=session['id'], reported_state=session.get('reported_state'),
                            alive=bool(pid and pathlib.Path(f'/proc/{pid}').exists()))
                screen = command(['aplexer', 'capture', session['id'], '--screen', '--plain'])
                count, reason = eligible(item, screen, head_tag, old, quota=True)
                item.update(composer=composer(screen, head_tag), ready_snapshot_count=count, reason=reason)

                head_entities = [e for e in entities if e.get('head_tag') == head_tag and not (e.get('conflict') and e['conflict'].get('detected'))]
                head_active = [
                    t for t in active
                    if is_task_eligible_for_supervision(t, sessions=sessions, active_heads=head_tags, active_principals=active_tags)
                    and (((t.get('owner_tag') or t.get('owner')) == head_tag) or any(task_matches_entity(t, e) for e in head_entities))
                ]
                head_ready = [t for t in head_active if t.get('status') in ('ready', 'queued')]

                idle_since, overdue = idle_episode(head_ready, count > 0, old, time.time(), threshold=180)
                item['idle_since'] = idle_since
                item['unexplained_idle_over_slo'] = overdue
                item['ready_task_count'] = len(head_ready)

                if overdue:
                    report['degraded'] = True
                    report['errors'].append(f"head {head_tag} unexplained idle-with-READY ({round(time.time() - idle_since, 1)}s >= 180s) with {len(head_ready)} ready tasks")
                    event('head-unexplained-idle-over-slo', head=head_tag, session_id=session['id'],
                          idle_since=idle_since, duration_seconds=round(time.time() - idle_since, 2),
                          ready_tasks=[t['id'] for t in head_ready])

                episode = int(time.time() // 180) if overdue else old.get('episode', 0)
                event_key = hashlib.sha256(f'{digest}:{session["id"]}:{episode}'.encode()).hexdigest()[:20]
                item.update(event_key=event_key, episode=episode)

                pending = old.get('pending')
                if pending and pending.get('diagnostic_hold'):
                    item['diagnostic_hold'] = pending['diagnostic_hold']
                if old.get('last_request'):
                    item['last_request'] = old['last_request']
                if pending:
                    evidence = exact_ack(pending, session['id'], head_tag, ROOT)
                    if evidence:
                        item['last_request'] = {**pending, 'acknowledged_at': now(), 'ack_evidence': evidence}
                        atomic(PRIVATE / ('native-ack-' + pending['id'] + '.json'), evidence)
                        event('pending-reconciled-native-ack', head=head_tag, **evidence)
                        report['actions'].append({'kind': 'pending-reconciled-native-ack', 'head': head_tag, 'message_id': pending['id']})
                        pending = None
                    else:
                        target_recipient_id = pending.get('recipient_session_id') or old.get('session_id')
                        if not target_recipient_id:
                            receipt_file = PRIVATE / f"receipt-{pending.get('event')}-{head_tag}.json"
                            if receipt_file.exists():
                                try:
                                    rdata = json.loads(receipt_file.read_text())
                                    target_recipient_id = rdata.get('to', {}).get('session_id')
                                except Exception:
                                    pass
                        if target_recipient_id and target_recipient_id != session['id']:
                            event('pending-superseded-session-change', head=head_tag, message_id=pending['id'],
                                  old_session_id=target_recipient_id, new_session_id=session['id'],
                                  reason='recipient session changed; previous message addressed to old session superseded')
                            report['actions'].append({
                                'kind': 'pending-superseded-session-change',
                                'head': head_tag,
                                'message_id': pending['id'],
                                'old_session_id': target_recipient_id,
                                'new_session_id': session['id']
                            })
                            item['last_request'] = {**pending, 'superseded_at': now(), 'superseded_reason': 'recipient-session-change'}
                            pending = None

                cooldown = old.get('cooldown_until', 0)
                ready_fps = [task_ready_fingerprint(t) for t in sorted(head_ready, key=lambda x: str(x.get('id')))]
                ready_fingerprint = hashlib.sha256(json.dumps(ready_fps, sort_keys=True).encode()).hexdigest()[:20]
                head_event_key = hashlib.sha256(f'{digest}:{session["id"]}:{episode}:{ready_fingerprint}'.encode()).hexdigest()[:20]
                item.update(event_key=head_event_key)

                last_notified_fp = old.get('last_notified_ready_fingerprint')
                session_changed = bool(old.get('session_id') and old.get('session_id') != session['id'])
                ready_delta = bool(head_ready) and ((last_notified_fp is None) or session_changed or (ready_fingerprint != last_notified_fp))

                item['ready_task_ids'] = [t['id'] for t in head_ready]
                item['ready_fingerprint'] = ready_fingerprint
                item['ready_delta'] = ready_delta

                if head_ready and not pending and ready_delta and (old.get('sent_event') != head_event_key) and time.time() >= cooldown:
                    if item.get('alive'):
                        task_ids_str = ", ".join(t['id'] for t in head_ready[:5])
                        body = (
                            f"SUPERVISION-{head_event_key}: Head {head_tag} has {len(head_ready)} ready tasks awaiting dispatch: {task_ids_str}. "
                            "Inspect queues, launch executors, verify first tool output. Update TASKS.json."
                        )
                        receipt = recorded_send(BINARY, head_tag, f'{head_event_key}-{head_tag}', body, PRIVATE, identity['id'], supports_key)
                        atomic(PRIVATE / f'receipt-{head_event_key}-{head_tag}.json', receipt)
                        if receipt.get('delivery') == 'send-uncertain':
                            report['degraded'] = True
                            report['uncertain_outcome'] = {'outcome': 'UNKNOWN', 'class': 'send-uncertain', 'head': head_tag, 'event_key': head_event_key, 'reason': receipt.get('reason')}
                        envelope = receipt.get('message', receipt)
                        pending = {'id': envelope.get('id', receipt.get('id')), 'sender_id': identity['id'],
                                   'sender_tag': identity.get('tag', 'experiment-supervision'),
                                   'recipient_session_id': session['id'], 'recipient_tag': head_tag,
                                   'workspace': identity.get('workspace', str(ROOT)), 'event': head_event_key,
                                   'delivery': receipt.get('delivery', 'inbox'), 'created_at': now()}
                        item['sent_event'] = head_event_key
                        item['last_notified_ready_fingerprint'] = ready_fingerprint
                        item['last_notified_ready_ids'] = [t['id'] for t in head_ready]
                        item['cooldown_until'] = cooldown
                        event('head-request-recorded', head=head_tag, message_id=pending['id'], event_key=head_event_key, ready_tasks=[t['id'] for t in head_ready])
                else:
                    item['sent_event'] = old.get('sent_event')
                    item['last_notified_ready_fingerprint'] = old.get('last_notified_ready_fingerprint') if head_ready else None
                    item['last_notified_ready_ids'] = old.get('last_notified_ready_ids', []) if head_ready else []
                    item['cooldown_until'] = cooldown
                    if head_ready and not ready_delta:
                        item['ready_deduped'] = True

                if pending and not may_deliver(pending, identity['id'], spool=PRIVATE):
                    item['pending_reason'] = 'original sender changed; original recipient ACK/reply required'
                elif item.get('pending_reason') == 'original sender changed; original recipient ACK/reply required':
                    item.pop('pending_reason', None)
                if may_deliver(pending, identity['id'], spool=PRIVATE) and count >= 2 and time.time() >= item.get('cooldown_until', 0) and not item.get('failover_candidate'):
                    if check_resting_state_contradicted(session):
                        item['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
                        pending['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
                        item['cooldown_until'] = time.time() + 180
                        event('head-delivery-precheck-held', head=head_tag, message_id=pending['id'], reason='resting-state-contradicted-by-pty', last_activity_ms=session.get('last_activity_ms'), reported_state_at_ms=session.get('reported_state_at_ms'))
                    else:
                        if item.get('diagnostic_hold') == 'resting-state-contradicted-by-pty':
                            item.pop('diagnostic_hold', None)
                            pending.pop('diagnostic_hold', None)
                        fresh_screen = command(['aplexer', 'capture', session['id'], '--screen', '--plain'])
                        if composer(fresh_screen, head_tag) == 'empty':
                            deliver_args = [BINARY, 'message', 'deliver', pending['id'], '--workspace', str(ROOT), '--json']
                            result = subprocess.run(deliver_args, capture_output=True, text=True, timeout=20)
                            deliver_stderr = (result.stderr or '').strip()
                            if result.returncode and MAILBOX_BUSY.search(deliver_stderr):
                                raise DeliveryUncertain(deliver_args, deliver_stderr, result.returncode)
                            try:
                                outcome = json.loads(result.stdout)
                            except json.JSONDecodeError:
                                outcome = {'status': 'delivery-uncertain', 'returncode': result.returncode}
                            atomic(PRIVATE / f"delivery-{pending['id']}.json", outcome)
                            status = outcome.get('status', outcome.get('delivery', 'delivery-uncertain'))
                            pending['delivery'] = status
                            event('head-delivery-attempt', head=head_tag, message_id=pending['id'], outcome=status)
                            if status == 'not-ready':
                                detail = outcome.get('detail', '')
                                if 'contradicted resting state' in detail or 'subsequent PTY activity' in detail:
                                    item['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
                                    pending['diagnostic_hold'] = 'resting-state-contradicted-by-pty'
                                    item['cooldown_until'] = time.time() + 180
                                elif (('Context' in detail or 'GPT-' in detail) and '·' in detail) or re.search(
                                    r'Aplexer awareness|Before editing files|Declare your work|Check peer mail|participate in \d+ workspace|Workspace coordination|worktree|peers|shared paths|peer-provided data',
                                    detail
                                ):
                                    item['diagnostic_hold'] = 'known-footer-classifier-mismatch'
                                    pending['diagnostic_hold'] = 'known-footer-classifier-mismatch'
                                if item.get('diagnostic_hold') == 'known-footer-classifier-mismatch':
                                    item['cooldown_until'] = time.time() + 180
                            if status == 'recipient-acked':
                                item['last_request'] = pending
                                item.pop('diagnostic_hold', None)
                                item.pop('failover_candidate', None)
                                item['cooldown_until'] = time.time() + 180
                                pending = None

                if pending:
                    is_beyond, dur, slo_limit, block_reason = check_pending_slo(pending, head_tag, item, time.time())
                    if is_beyond:
                        if pending.get('sender_id') != identity['id']:
                            event('pending-superseded-session-change', head=head_tag, message_id=pending['id'],
                                  old_sender_id=pending.get('sender_id'), new_sender_id=identity['id'],
                                  session_id=session['id'], duration_seconds=round(dur, 2), slo_seconds=slo_limit,
                                  reason='prior supervisor pending message stale beyond SLO; superseded')
                            report['actions'].append({
                                'kind': 'pending-superseded-session-change',
                                'head': head_tag,
                                'message_id': pending['id'],
                                'old_sender_id': pending.get('sender_id'),
                                'new_sender_id': identity['id'],
                                'session_id': session['id']
                            })
                            item['last_request'] = {**pending, 'superseded_at': now(), 'superseded_reason': 'stale-beyond-slo-sender-change'}
                            item.pop('diagnostic_hold', None)
                            item.pop('failover_candidate', None)
                            pending = None
                            item['status'] = 'ok'
                        else:
                            item['status'] = 'blocked_beyond_slo'
                            if item.get('diagnostic_hold'):
                                item['blocking_reason'] = f"{block_reason} [diagnostic_hold: {item['diagnostic_hold']}]"
                            else:
                                item['blocking_reason'] = block_reason
                            item['pending_duration_seconds'] = round(dur, 2)
                            item['retry_slo_seconds'] = slo_limit
                            item['cooldown_until'] = max(item.get('cooldown_until', 0), time.time() + 300 if time.time() >= cooldown else cooldown)
                            report['degraded'] = True
                            report['errors'].append(f"head {head_tag} pending message {pending['id']} blocked_beyond_slo ({round(dur, 1)}s >= {slo_limit}s): {item['blocking_reason']}")
                            event('pending-blocked-beyond-slo', head=head_tag, message_id=pending['id'],
                                  duration_seconds=round(dur, 2), slo_seconds=slo_limit, blocking_reason=item['blocking_reason'])
                            report['actions'].append({
                                'kind': 'pending-blocked-beyond-slo-escalation',
                                'recipient': head_tag,
                                'message_id': pending['id'],
                                'duration_seconds': round(dur, 2),
                                'blocking_reason': item['blocking_reason'],
                                'diagnostic_hold': item.get('diagnostic_hold'),
                                'recovery_owner': 'ant-head-never-timer-custody-20261006'
                            })
                            if not item.get('alive', True) or dur > 2 * slo_limit:
                                item['failover_candidate'] = True
                                failover_reason = f"leader {head_tag} role vacancy: {'un-alive (confirmed dead)' if not item.get('alive', True) else f'unACKed beyond 2x SLO ({round(dur, 1)}s > {2 * slo_limit}s)'}; candidate 43ea trigger condition met"
                                event('failover-candidate-action',
                                      role='head',
                                      role_vacancy=True,
                                      entity=head_tag,
                                      head=head_tag,
                                      message_id=pending['id'],
                                      duration_seconds=round(dur, 2),
                                      slo_seconds=slo_limit,
                                      alive=item.get('alive', True),
                                      trigger_condition='un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
                                      candidate_pin='43ea3400965e690206f823640173992a9ea0c7b4',
                                      candidate='43ea',
                                      reason=failover_reason)
                                report['actions'].append({
                                    'kind': 'failover-candidate-action',
                                    'role': 'head',
                                    'role_vacancy': True,
                                    'entity': head_tag,
                                    'recipient': head_tag,
                                    'head': head_tag,
                                    'message_id': pending['id'],
                                    'duration_seconds': round(dur, 2),
                                    'slo_seconds': slo_limit,
                                    'alive': item.get('alive', True),
                                    'trigger_condition': 'un-alive' if not item.get('alive', True) else 'blocked_beyond_2x_slo',
                                    'candidate_pin': '43ea3400965e690206f823640173992a9ea0c7b4',
                                    'candidate': '43ea',
                                    'reason': failover_reason
                                })
                    else:
                        item['status'] = 'pending'
                        if not item.get('alive', True):
                            item['failover_candidate'] = True
                            failover_reason = f"leader {head_tag} role vacancy: un-alive (confirmed dead); candidate 43ea trigger condition met"
                            event('failover-candidate-action',
                                  role='head',
                                  role_vacancy=True,
                                  entity=head_tag,
                                  head=head_tag,
                                  message_id=pending['id'],
                                  duration_seconds=round(dur, 2),
                                  slo_seconds=slo_limit,
                                  alive=item.get('alive', True),
                                  trigger_condition='un-alive',
                                  candidate_pin='43ea3400965e690206f823640173992a9ea0c7b4',
                                  candidate='43ea',
                                  reason=failover_reason)
                            report['actions'].append({
                                'kind': 'failover-candidate-action',
                                'role': 'head',
                                'role_vacancy': True,
                                'entity': head_tag,
                                'recipient': head_tag,
                                'head': head_tag,
                                'message_id': pending['id'],
                                'duration_seconds': round(dur, 2),
                                'slo_seconds': slo_limit,
                                'alive': item.get('alive', True),
                                'trigger_condition': 'un-alive',
                                'candidate_pin': '43ea3400965e690206f823640173992a9ea0c7b4',
                                'candidate': '43ea',
                                'reason': failover_reason
                            })
                else:
                    item['status'] = 'ok'
                    item.pop('failover_candidate', None)
                item['pending'] = pending
                report['heads'][head_tag] = item
                memory[head_tag] = item
            atomic(statepath, memory)
            # Bounded operational receipts; retain every currently unresolved/uncertain request.
            protected = {x.get('pending', {}).get('id') for x in memory.values() if x.get('pending')}
            protected |= {x.get('pending', {}).get('event') for x in memory.values() if x.get('pending')}
            archived_count = archive_operational(PRIVATE, protected)
            if archived_count:
                event('operational-archive', archived_files=archived_count, retained_live_newest=2048, unresolved_preserved=True)
        except StorageFull as exc:
            report['storage'] = {**storage_guard(PRIVATE), 'state':'paused-hard-limit', 'reason':str(exc)}
            record_cycle_failure(report, exc)
            # Preserve evidence; only overwrite bounded current status, never trim old archives.
        except Exception as exc:
            # Any failed cycle (busy, uncertain mutation, unexpected error) is degraded;
            # empty principals here are a missed observation, never a valid all-clear snapshot.
            record_cycle_failure(report, exc)
            event('error', error=str(exc), degraded=True, observation=report.get('observation'))
        atomic(PRIVATE / 'status.json', report)
        print(json.dumps({'timestamp': now(), 'degraded': report['degraded'], 'principals': {tag: x.get('reason') for tag,x in report['principals'].items()}, 'heads': {tag: x.get('reason') for tag,x in report.get('heads', {}).items()}, 'errors': report['errors']}), flush=True)
        for _ in range(60):
            if (PRIVATE / 'stop').exists():
                return
            time.sleep(1)


if __name__ == '__main__':
    run()
