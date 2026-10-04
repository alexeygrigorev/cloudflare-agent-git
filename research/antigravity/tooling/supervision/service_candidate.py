#!/usr/bin/env python3
"""Principal event watchdog. Never implements work or fabricates session readiness."""
import argparse, datetime, fcntl, hashlib, json, os, pathlib, re, subprocess, sys, time, uuid
_sup_dir = str(pathlib.Path(__file__).resolve().parents[4] / 'scripts/supervision')
if _sup_dir not in sys.path:
    sys.path.insert(0, _sup_dir)
from ack_reconciliation import exact_ack
from retention import StorageFull, archive_operational, archive_verified, read_archived, storage_guard

ROOT = pathlib.Path('/home/alexey/git/cloudflare-agent-git')
PRIVATE = ROOT / '.local/supervision'
BINARY = os.environ.get('SUPERVISION_APLEXER_BINARY', '/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer')
ALL_KNOWN_PRINCIPALS = ('codex-principal', 'claude-principal')
PRINCIPALS = ALL_KNOWN_PRINCIPALS  # backward-compatibility alias

def active_principals(teams_data=None, spool=None, registry_raw=None):
    """
    Dynamically determine active principals, honoring quiet/morning-only status,
    exclusion files, and environment overrides (C-1396).
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


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

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

def composer(screen, tag):
    """Last prompt, never transcript prompts; unknown and menus deny input."""
    lines = screen.splitlines()
    starts = [(i, re.sub(r'^\s*[›❯]\s*', '', line).strip())
              for i, line in enumerate(lines) if re.match(r'^\s*[›❯]', line)]
    if not starts:
        return 'unknown'
    index, content = starts[-1]
    tail = '\n'.join(lines[index + 1:])
    # A multiline prompt cannot be distinguished safely from arbitrary content.
    if any(line.strip() and not re.match(r'^\s*[─━]|.*(?:Context|for shortcuts|auto mode|manage|monitor|agents|tokens|GPT-|usage|workspace|warning)', line)
           for line in lines[index + 1:]):
        return 'unknown'
    if re.search(r'How is Claude doing|Choose|Select|feedback', screen, re.I):
        return 'menu-or-draft'
    if content and not (tag == 'codex-principal' and content == 'Ask Codex to do anything'):
        return 'draft'
    if re.search(r'Working \(|esc to interrupt|esc interrupt', screen, re.I):
        return 'busy'
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

def task_event(tasks):
    active = [t for t in tasks if t.get('status') not in ('completed', 'done', 'cancelled', 'rejected', 'parked', 'on_hold')]
    meaningful = [{k:t.get(k) for k in ('id','team_id','owner_tag','status','blocked_on','next_action','evidence_paths')} for t in active]
    digest = hashlib.sha256(json.dumps(meaningful, sort_keys=True).encode()).hexdigest()[:20]
    counts = {}
    for task in active:
        state = task.get('status', 'unknown')
        counts[state] = counts.get(state, 0) + 1
    return active, digest, counts

def idle_episode(active, ready, old, timestamp):
    since = (old.get('idle_since') if old.get('idle_since') is not None else timestamp) if ready else None
    overdue = bool(active and since is not None and timestamp - since >= 300 and not old.get('pending'))
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

    current_ts = now_ts if now_ts is not None else time.time()
    if not isinstance(current_ts, (int, float)) or not math.isfinite(current_ts) or current_ts <= 0:
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
    Parse and validate the syntax/structure of an authoritative turn-boundary hook event.
    NOTE (C1532): Syntax validation alone does NOT authenticate the producer or authorize
    untrusted socket injection. Producer provenance requires transport-level authentication
    (e.g. 0700 UNIX domain socket owned by the session workload UID/GID).
    - Validates event type ('turn_complete' or 'turn_start')
    - Enforces state ('idle-empty' for turn_complete, 'working' for turn_start)
    - Validates monotonic prompt_seq >= 0
    - Enforces session UUID format and optional expected_session_id match
    - Enforces engine in authorized set
    - Rejects invalid resting states (e.g. active child processes or unsubmitted drafts)
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

def may_deliver(pending, own_id):
    return bool(pending and pending.get('id') and pending.get('sender_id') == own_id and pending.get('delivery') in ('inbox','not-ready'))

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
    atomic(PRIVATE / 'identity.json', {k: identity.get(k) for k in ('id', 'tag', 'workspace')})
    manifest = {'path':BINARY, 'sha256':expected_hash, 'selected_at':now(),
           'authority':'root-approved immutable copy of installed production CLI; no all-engine readiness guarantee',
           'supports_idempotency_key':supports_key, 'send_recovery':'native key when available; otherwise crash-safe local intent, ambiguous sends frozen'}
    atomic(PRIVATE / 'binary-manifest.json', manifest)
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
        event('service-started', session_id=identity['id'], binary_sha256=expected_hash)
    while not (PRIVATE / 'stop').exists():
        report = {'timestamp': now(), 'identity': identity['id'], 'principals': {}, 'errors': [], 'actions': [], 'degraded': False}
        try:
            report['storage'] = storage_guard(PRIVATE)
            if report['storage']['state'] == 'paused-hard-limit':
                raise StorageFull('storage hard limit reached; native messages and ACKs paused; evidence preserved')
            registry_full = json.loads((ROOT / 'coordination/TEAM-REGISTRY.json').read_text())
            teams = registry_full if isinstance(registry_full, list) else registry_full.get('teams', [])
            tasks = records(ROOT / 'coordination/TASKS.json', 'tasks')
            active, digest, counts = task_event(tasks)
            report['task_counts'] = counts
            active_tags = active_principals(teams, PRIVATE, registry_full)
            report['active_principals'] = active_tags
            sessions = json.loads(command(['aplexer', 'list', '--json']))
            sessions = [x for x in sessions if x.get('workspace') == str(ROOT)]
            same_binary = hashlib.sha256(pathlib.Path(BINARY).read_bytes()).hexdigest() == expected_hash
            if not same_binary:
                raise RuntimeError('scoped binary changed: re-review and restart service explicitly')
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
                    else:
                        item['status'] = 'missing'
                    memory[tag] = item
                    report['principals'][tag] = item
                    continue
                item = {'event_key': digest, 'ready_snapshot_count': 0}
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
                idle_since, overdue = idle_episode(active, count > 0, old, time.time())
                item['idle_since'] = idle_since
                item['unexplained_idle_over_slo'] = overdue
                episode = int(time.time() // (1800 if tag == 'claude-principal' else 300)) if overdue else old.get('episode', 0)
                event_key = hashlib.sha256(f'{digest}:{session["id"]}:{episode}'.encode()).hexdigest()[:20]
                item.update(event_key=event_key, episode=episode)
                pending = old.get('pending')
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
                # At most one envelope per task revision, sparse Claude min 30m; no hourly busywork.
                cooldown = old.get('cooldown_until', 0)
                if active and not pending and (old.get('sent_event') != event_key) and time.time() >= cooldown:
                    if item.get('alive'):
                        selected = [t for t in active if any(tag in team.get('principal_tags', []) and team['id'] == t.get('team_id') for team in teams)]
                        if selected:
                            body = (f'SUPERVISION-{event_key}: User requests autonomous useful execution and clear roles. '
                                    'Read coordination/TEAM-REGISTRY.json, TASKS.json and SUPERVISION.md. '
                                    'As monitoring principal, inspect your teams, ask heads to claim ready owned work, '
                                    'verify first actual tool/output, review completion and choose next useful step. '
                                    'Diagnose blockers or arrange acknowledged repair and continue independent work. '
                                    'Do not create implementation teams yourself, invent busywork, overwrite drafts or bypass quotas. '
                                    'Reply with task IDs, accepted owners, first evidence, blocked reasons and next check; update TASKS.json with ownership. '
                                    'Tasks: ' + ', '.join(f"{t['id']} ({t.get('status','unknown')}, {t.get('owner_tag','unowned')})" for t in selected))
                            # Inbox first, then existing-ID delivery after independent fresh snapshots.
                            receipt = recorded_send(BINARY,tag,f'{event_key}-{tag}',body,PRIVATE,identity['id'],supports_key)
                            atomic(PRIVATE / f'receipt-{event_key}-{tag}.json', receipt)
                            if receipt.get('delivery') == 'send-uncertain':
                                # Frozen ambiguity: retain UNKNOWN outcome in the report, degraded cycle.
                                report['degraded'] = True
                                report['uncertain_outcome'] = {'outcome': 'UNKNOWN', 'class': 'send-uncertain', 'principal': tag, 'event_key': event_key, 'reason': receipt.get('reason')}
                            envelope = receipt.get('message', receipt)
                            pending = {'id': envelope.get('id', receipt.get('id')), 'sender_id':identity['id'], 'event': event_key,
                                       'delivery':receipt.get('delivery','inbox'), 'created_at': now()}
                            item['sent_event'] = event_key
                            item['cooldown_until'] = time.time() + (1800 if tag == 'claude-principal' else 300)
                            event('request-recorded', principal=tag, message_id=pending['id'], event_key=event_key)
                else:
                    item['sent_event'] = old.get('sent_event')
                    item['cooldown_until'] = cooldown

                if pending and pending.get('sender_id') != identity['id']:
                    item['pending_reason'] = 'original sender changed; original recipient ACK/reply required'
                if may_deliver(pending,identity['id']) and count >= 2:
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
                        # Fail-closed safety: no fallback to binaries lacking composer draft detection (sb-reviewer-sup B1 blocker).
                        # Refusal from reviewed binary is preserved verbatim in delivery audit evidence.
                        atomic(PRIVATE / f"delivery-{pending['id']}.json", outcome)
                        status = outcome.get('status', outcome.get('delivery', 'delivery-uncertain'))
                        pending['delivery'] = status
                        event('delivery-attempt', principal=tag, message_id=pending['id'], outcome=status)
                        if status == 'recipient-acked':
                            item['last_request'] = pending
                            pending = None
                        # Submitted stays pending until genuine reply/read ACK, not repeated on timer.
                        # Unknown/uncertain outcomes prohibit automatic retry.
                if pending:
                    is_beyond, dur, slo_limit, block_reason = check_pending_slo(pending, tag, item, time.time())
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
                else:
                    item['status'] = 'ok'
                item['pending'] = pending
                report['principals'][tag] = item
                memory[tag] = item
            atomic(statepath, memory)
            # Bounded operational receipts; retain every currently unresolved/uncertain request.
            protected = {x.get('pending', {}).get('id') for x in memory.values() if x.get('pending')}
            protected |= {x.get('pending', {}).get('event') for x in memory.values() if x.get('pending')}
            archived_count = archive_operational(PRIVATE,protected)
            if archived_count:
                event('operational-archive', archived_files=archived_count, retained_live_newest=2048, unresolved_preserved=True)
        except StorageFull as exc:
            report['storage'] = {**storage_guard(PRIVATE),'state':'paused-hard-limit','reason':str(exc)}
            record_cycle_failure(report, exc)
            # Preserve evidence; only overwrite bounded current status, never trim old archives.
        except Exception as exc:
            # Any failed cycle (busy, uncertain mutation, unexpected error) is degraded;
            # empty principals here are a missed observation, never a valid all-clear snapshot.
            record_cycle_failure(report, exc)
            event('error', error=str(exc), degraded=True, observation=report.get('observation'))
        atomic(PRIVATE / 'status.json', report)
        print(json.dumps({'timestamp': now(), 'degraded': report['degraded'], 'principals': {tag: x.get('reason') for tag,x in report['principals'].items()}, 'errors': report['errors']}), flush=True)
        for _ in range(60):
            if (PRIVATE / 'stop').exists():
                return
            time.sleep(1)

if __name__ == '__main__':
    run()
