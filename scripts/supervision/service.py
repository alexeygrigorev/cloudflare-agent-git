#!/usr/bin/env python3
"""Principal event watchdog. Never implements work or fabricates session readiness."""
import argparse, datetime, fcntl, hashlib, json, os, pathlib, re, subprocess, time
from retention import StorageFull, archive_operational, archive_verified, read_archived, storage_guard

ROOT = pathlib.Path('/home/alexey/git/cloudflare-agent-git')
PRIVATE = ROOT / '.local/supervision'
BINARY = os.environ.get('SUPERVISION_APLEXER_BINARY', '/home/alexey/git/cloudflare-aplexer-protocol/target/debug/aplexer')
PRINCIPALS = ('codex-principal', 'claude-principal')

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def atomic(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2))
    tmp.replace(path)

def command(args, timeout=20):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'command failed: {args[1:3]} rc={result.returncode}')
    return result.stdout

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
    atomic(PRIVATE / 'binary-manifest.json', {'path':BINARY, 'sha256':expected_hash, 'selected_at':now(),
           'authority':'root-approved immutable copy of installed production CLI; no all-engine readiness guarantee',
           'supports_idempotency_key':supports_key, 'send_recovery':'native key when available; otherwise crash-safe local intent, ambiguous sends frozen'})
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
        report = {'timestamp': now(), 'identity': identity['id'], 'principals': {}, 'errors': [], 'actions': []}
        try:
            report['storage'] = storage_guard(PRIVATE)
            if report['storage']['state'] == 'paused-hard-limit':
                raise StorageFull('storage hard limit reached; native messages and ACKs paused; evidence preserved')
            teams = records(ROOT / 'coordination/TEAM-REGISTRY.json', 'teams')
            tasks = records(ROOT / 'coordination/TASKS.json', 'tasks')
            active, digest, counts = task_event(tasks)
            report['task_counts'] = counts
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
                tags = [tag for tag in PRINCIPALS if sender.get('tag') == tag]
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
            for tag in PRINCIPALS:
                match = [x for x in sessions if x.get('tag') == tag]
                old = memory.get(tag, {})
                item = {'event_key': digest, 'ready_snapshot_count': 0}
                if len(match) != 1:
                    item['reason'] = 'missing-or-ambiguous-principal'
                    report['principals'][tag] = item
                    continue
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
                # At most one envelope per task revision, sparse Claude min 30m; no hourly busywork.
                cooldown = old.get('cooldown_until', 0)
                if active and not pending and (old.get('sent_event') != event_key) and time.time() >= cooldown:
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
                        result = subprocess.run([BINARY, 'message', 'deliver', pending['id'], '--workspace', str(ROOT), '--json'], capture_output=True, text=True, timeout=20)
                        try:
                            outcome = json.loads(result.stdout)
                        except json.JSONDecodeError:
                            outcome = {'status': 'delivery-uncertain', 'returncode': result.returncode}
                        atomic(PRIVATE / f"delivery-{pending['id']}.json", outcome)
                        status = outcome.get('status', outcome.get('delivery', 'delivery-uncertain'))
                        pending['delivery'] = status
                        event('delivery-attempt', principal=tag, message_id=pending['id'], outcome=status)
                        if status == 'recipient-acked':
                            item['last_request'] = pending
                            pending = None
                        # Submitted stays pending until genuine reply/read ACK, not repeated on timer.
                        # Unknown/uncertain outcomes prohibit automatic retry.
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
            report['errors'].append(str(exc))
            report['storage'] = {**storage_guard(PRIVATE),'state':'paused-hard-limit','reason':str(exc)}
            # Preserve evidence; only overwrite bounded current status, never trim old archives.
        except Exception as exc:
            report['errors'].append(str(exc))
            event('error', error=str(exc))
        atomic(PRIVATE / 'status.json', report)
        print(json.dumps({'timestamp': now(), 'principals': {tag: x.get('reason') for tag,x in report['principals'].items()}, 'errors': report['errors']}), flush=True)
        for _ in range(60):
            if (PRIVATE / 'stop').exists():
                return
            time.sleep(1)

if __name__ == '__main__':
    run()
